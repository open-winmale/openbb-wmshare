"""Keep the documentation in step with what the provider actually serves.

The coverage table is the user-facing promise; these tests fail when code and
docs drift apart, which is cheaper than learning about it from a bug report.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openbb_wmshare import wmshare_provider

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "docs" / "COVERAGE.md"
GAPS = ROOT / "docs" / "GAPS.md"

UNSUPPORTED_MODELS: set[str] = set()
"""Models registered but not actually served.

Empty today: ``IndexHistorical`` was the last one and it now resolves aliases
through ``utils/index_canon.py`` and returns real bars. Keep the set so the
market-consistency check below stays correct if another model is ever parked.
"""

MARKET_ORDER = ("cn", "hk", "us")


def _coverage_rows() -> dict[str, tuple[list[str], str]]:
    """Parse the command tables into ``{command: (per-market cells, note)}``."""
    rows: dict[str, tuple[list[str], str]] = {}
    for line in COVERAGE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `") or "---" in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        rows[cells[0].strip("`")] = (cells[2:5], cells[5] if len(cells) > 5 else "")
    return rows


def _documented_commands() -> set[str]:
    return set(_coverage_rows())


def test_coverage_table_is_parsed():
    """Guard the parser itself, so a table reformat does not silently disable these tests."""
    rows = _coverage_rows()
    assert "equity.price.historical" in rows
    assert "index.constituents" in rows
    assert len(rows) >= 15


@pytest.mark.parametrize("model_name", sorted(wmshare_provider.fetcher_dict))
def test_every_registered_model_is_documented(model_name):
    """Adding a fetcher without a docs row must fail the build."""
    documented = " ".join(_documented_commands()).lower()
    assert model_name.lower() in documented or _alias(model_name) in documented, (
        f"{model_name} is registered but missing from docs/COVERAGE.md"
    )


def test_coverage_marks_index_historical_served_for_cn():
    """A-share index bars are served; HK/US have no index bar store at all."""
    status, note = _coverage_rows()["index.price.historical"]
    assert status[MARKET_ORDER.index("cn")] == "✅", status
    assert status[MARKET_ORDER.index("hk")] == "⛔", status
    assert status[MARKET_ORDER.index("us")] == "⛔", status
    assert "别名" in note or "GAPS" in note


def test_gaps_documents_index_alias_trap():
    """The alias trap is permanent knowledge; it must survive doc edits."""
    text = GAPS.read_text(encoding="utf-8")
    assert "399300.INDEX" in text
    assert "000300.INDEX" in text  # the trap: intuitive code is a different index
    assert "index.hs300" in text
    assert "探测脚本" in text


@pytest.mark.parametrize(
    "model_name",
    sorted(name for name in wmshare_provider.fetcher_dict if name not in UNSUPPORTED_MODELS),
)
def test_documented_markets_match_allowed_market_choices(model_name):
    """A market marked available in the docs must be one the query model accepts."""
    fetcher = wmshare_provider.fetcher_dict[model_name]
    market_field = fetcher.query_params_type.model_fields.get("market")
    if market_field is None:
        pytest.skip(f"{model_name} has no market selector")

    allowed = {market for market in MARKET_ORDER if f"'{market}'" in str(market_field.annotation)}
    assert allowed, f"market field on {model_name} is not a Literal: {market_field.annotation}"

    command = _command_for(model_name)
    status, _ = _coverage_rows()[command]
    marked = {
        market for market, cell in zip(MARKET_ORDER, status, strict=True) if cell.startswith("✅")
    }
    assert marked <= allowed, (
        f"{command} documents {sorted(marked)} as available but the query model "
        f"only accepts {sorted(allowed)}"
    )


def _command_for(model_name: str) -> str:
    """The coverage-table command path for a standard model name."""
    return {
        "EquityHistorical": "equity.price.historical",
        "EquityQuote": "equity.price.quote",
        "EquitySearch": "equity.search",
        "EquityInfo": "equity.profile",
        "IncomeStatement": "equity.fundamental.income",
        "BalanceSheet": "equity.fundamental.balance",
        "CashFlowStatement": "equity.fundamental.cash",
        "KeyMetrics": "equity.fundamental.metrics",
        "FinancialRatios": "equity.fundamental.ratios",
        "HistoricalDividends": "equity.fundamental.dividends",
        "CalendarDividend": "equity.calendar.dividend",
        "IndexHistorical": "index.price.historical",
        "IndexConstituents": "index.constituents",
        "IndexSearch": "index.search",
        "AvailableIndices": "index.available",
        "IndexSnapshots": "index.snapshots",
        "EquityGainers": "equity.discovery.gainers",
        "EquityLosers": "equity.discovery.losers",
        "TrailingDividendYield": "equity.fundamental.trailing_dividend_yield",
        "CompanyFilings": "equity.fundamental.filings",
        "KeyExecutives": "equity.fundamental.management",
        "ShareStatistics": "equity.ownership.share_statistics",
        "InstitutionalOwnership": "equity.ownership.institutional",
        "InsiderTrading": "equity.ownership.insider_trading",
        "RevenueBusinessLine": "equity.fundamental.revenue_per_segment",
        "RevenueGeographic": "equity.fundamental.revenue_per_geography",
        "CalendarEarnings": "equity.calendar.earnings",
        "ForwardEpsEstimates": "equity.estimates.forward_eps",
        "ForwardPeEstimates": "equity.estimates.forward_pe",
        "IncomeStatementGrowth": "equity.fundamental.income_growth",
        "BalanceSheetGrowth": "equity.fundamental.balance_growth",
        "CashFlowStatementGrowth": "equity.fundamental.cash_growth",
        "WmshareScreener": "wmshare.screener",
        "WmshareIndexValuationTrend": "wmshare.index_valuation_trend",
        "WmshareMoneyflow": "wmshare.moneyflow",
        "WmshareMargin": "wmshare.margin",
        "WmshareCbondBoard": "wmshare.cbond_board",
    }[model_name]


def _alias(model_name: str) -> str:
    """Fallback search term: the last path segment of the matching command."""
    return _command_for(model_name).rsplit(".", 1)[-1]
