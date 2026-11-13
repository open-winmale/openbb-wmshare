"""Reshape wmshare statement rows into OpenBB's one-row-per-period layout.

wmshare returns statements transposed: one row per line item, with periods as
columns.

    [{"k": "total_revenue", "cn": "营业收入", "vals": {"2025": 1.68e11, "2024": 1.70e11}}]

OpenBB wants the opposite: one record per fiscal period, with line items as
fields, plus ``period_ending`` / ``fiscal_year`` / ``fiscal_period``.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

DERIVED_PREFIX = "__"
"""wmshare marks computed ratio rows (``__gm``, ``__debt_ratio``) with a prefix.

Those belong to the tree view, not the raw statements, and mixing them in would
put un-converted percentages next to report-currency amounts.
"""

_PERIOD_RE = re.compile(r"^(?P<year>\d{4})(?:[-:](?P<tag>Q[1-4]|H[12]|FY|M\d{2}|D\d{3}))?$")


def parse_period(token: str) -> tuple[int | None, str | None, date | None]:
    """Parse a wmshare period column header into ``(year, fiscal_period, period_end)``.

    Handles ``"2025"``, ``"2025-Q4"``, ``"2025:Q4"``, ``"2025-H1"`` and full
    dates such as ``"2025-12-31"``.
    """
    text = str(token or "").strip()
    if not text:
        return None, None, None

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        parsed = date.fromisoformat(text)
        return parsed.year, "FY", parsed

    match = _PERIOD_RE.match(text)
    if not match:
        return None, None, None

    year = int(match.group("year"))
    tag = match.group("tag")
    if tag is None:
        # A bare year is the annual report in wmshare's statement API.
        return year, "FY", date(year, 12, 31)
    if tag == "FY":
        return year, "FY", date(year, 12, 31)
    if tag.startswith("Q"):
        quarter = int(tag[1])
        month, day = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[quarter]
        return year, tag, date(year, month, day)
    if tag.startswith("H"):
        half = int(tag[1])
        month, day = (6, 30) if half == 1 else (12, 31)
        return year, tag, date(year, month, day)
    return year, tag, None


def pivot(rows: list[dict[str, Any]], *, drop_derived: bool = True) -> list[dict[str, Any]]:
    """Transpose wmshare's line-item rows into one record per fiscal period.

    Periods are returned newest first, matching wmshare's own ordering.
    """
    periods: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.get("vals") or {}:
            if key not in seen:
                seen.add(key)
                periods.append(str(key))

    records: list[dict[str, Any]] = []
    for period in periods:
        year, fiscal_period, period_end = parse_period(period)
        record: dict[str, Any] = {
            "fiscal_year": year,
            "fiscal_period": fiscal_period,
            "period_ending": period_end,
        }
        for row in rows:
            key = str(row.get("k") or "").strip()
            if not key or (drop_derived and key.startswith(DERIVED_PREFIX)):
                continue
            values = row.get("vals") or {}
            if period in values:
                record[key] = values[period]
        records.append(record)

    records.sort(key=lambda r: str(r.get("period_ending") or ""), reverse=True)
    return records


def collect(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Index statement rows as ``{item_code: {period: value}}``.

    Used by the ratio calculator, which needs to align two statements on the
    same period.
    """
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        key = str(row.get("k") or "").strip()
        if not key or key.startswith(DERIVED_PREFIX):
            continue
        values = row.get("vals") or {}
        out[key] = {
            period: float(value)
            for period, value in values.items()
            if isinstance(value, int | float)
        }
    return out


def _safe_div(numerator: Any, denominator: Any) -> float | None:
    """Divide, returning ``None`` when either side is missing or the divisor is zero."""
    if numerator is None or denominator is None:
        return None
    if not isinstance(numerator, int | float) or not isinstance(denominator, int | float):
        return None
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _avg(balance: dict[str, float], period: str, item: str) -> float | None:
    """Average opening and closing balance for a period.

    Balance-sheet items are point-in-time while income items are flows, so ROE
    and ROA need the mean of this period and the one before it. Falls back to
    the closing balance when no prior period is available.
    """
    values = balance.get(item, {})
    current = values.get(period)
    if current is None:
        return None
    prior_key = _prior_period(values, period)
    if prior_key is None:
        return float(current)
    return (float(current) + float(values[prior_key])) / 2


def _prior_period(values: dict[str, float], period: str) -> str | None:
    """Return the nearest earlier period key present in ``values``."""
    year, _, period_end = parse_period(period)
    if year is None or period_end is None:
        return None
    candidates = []
    for key in values:
        other_year, _, other_end = parse_period(key)
        if other_year is None or other_end is None:
            continue
        if other_end < period_end:
            candidates.append((other_end, key))
    if not candidates:
        return None
    return max(candidates)[1]


def compute_ratios(
    income_rows: list[dict[str, Any]],
    balance_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive OpenBB ``FinancialRatios`` rows from the two raw statements.

    Values are normalised decimals (0.32 = 32%), matching OpenBB's convention.
    Computed here rather than in ``statement_tree`` because that view emits
    native percentages for its ``pct`` rows, which would corrupt any downstream
    arithmetic.
    """
    income = collect(income_rows)
    balance = collect(balance_rows)

    periods: list[str] = []
    for source in (income, balance):
        for values in source.values():
            for period in values:
                if period not in periods:
                    periods.append(period)

    records: list[dict[str, Any]] = []
    for period in periods:
        year, fiscal_period, period_end = parse_period(period)

        def inc(item: str, _period: str = period) -> float | None:
            return income.get(item, {}).get(_period)

        def bal(item: str, _period: str = period) -> float | None:
            return balance.get(item, {}).get(_period)

        revenue = inc("total_revenue") or inc("operating_revenue")
        operating_cost = inc("operating_cost") or inc("total_operating_cost")
        gross_profit = inc("gross_profit")
        if gross_profit is None and revenue is not None and operating_cost is not None:
            gross_profit = revenue - operating_cost

        operating_profit = inc("operating_profit")
        total_profit = inc("total_profit")
        net_profit = inc("net_profit")
        parent_net_profit = inc("np_parent")

        total_assets = bal("total_assets")
        total_liabilities = bal("total_liabilities")
        total_equity = bal("total_equity")

        records.append(
            {
                "period_ending": period_end,
                "fiscal_year": year,
                "fiscal_period": fiscal_period,
                "gross_margin": _safe_div(gross_profit, revenue),
                "operating_margin": _safe_div(operating_profit, revenue),
                "pretax_margin": _safe_div(total_profit, revenue),
                "net_margin": _safe_div(net_profit, revenue),
                "return_on_assets": _safe_div(net_profit, _avg(balance, period, "total_assets")),
                "return_on_equity": _safe_div(
                    parent_net_profit if parent_net_profit is not None else net_profit,
                    _avg(balance, period, "total_parent_equity")
                    or _avg(balance, period, "total_equity"),
                ),
                "debt_to_assets": _safe_div(total_liabilities, total_assets),
                "equity_to_assets": _safe_div(total_equity, total_assets),
                "current_ratio": _safe_div(
                    bal("total_current_assets"), bal("total_current_liabilities")
                ),
                "quick_ratio": _safe_div(
                    None
                    if bal("total_current_assets") is None or bal("inventories") is None
                    else bal("total_current_assets") - bal("inventories"),
                    bal("total_current_liabilities"),
                ),
                "cash_ratio": _safe_div(bal("monetary_funds"), bal("total_current_liabilities")),
                "asset_turnover": _safe_div(revenue, _avg(balance, period, "total_assets")),
                "inventory_turnover": _safe_div(
                    operating_cost, _avg(balance, period, "inventories")
                ),
                "receivables_turnover": _safe_div(
                    revenue, _avg(balance, period, "accounts_receivable")
                ),
                "payout_ratio": None,
                "total_revenue": revenue,
                "net_income": net_profit,
                "total_assets": total_assets,
                "total_liabilities": total_liabilities,
                "total_equity": total_equity,
            }
        )

    records.sort(key=lambda r: str(r.get("period_ending") or ""), reverse=True)
    return records
