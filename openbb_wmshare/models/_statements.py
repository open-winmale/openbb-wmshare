"""Shared plumbing for the three wmshare statement models.

Two upstream paths, selected by the symbol's market:

* **cn** — ``rptdom.statement`` (alt.bssaa 投影): line-item rows x period
  columns, normalized by :func:`pivot`.
* **hk / us** — ``rptdom.mkt_latest`` / ``rptdom.mkt_get`` (跨市场宽表,
  quarterly, original currency): wide MAP docs normalized by
  :func:`mkt_normalize`.

Both converge on the same one-record-per-period layout with
``period_ending`` / ``fiscal_year`` / ``fiscal_period``.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol
from openbb_wmshare.utils.statements import mkt_normalize, pivot
from openbb_wmshare.utils.symbols import ParsedSymbol

Scope = Literal["consolidated", "parent"]
Sampling = Literal["Q1", "Q2", "Q3", "Q4"]

_SCOPE_LABEL: dict[str, str] = {"consolidated": "合并", "parent": "母公司"}

DOMAINS: dict[str, str] = {
    "income": "fin.income_statement",
    "balance": "fin.balance_sheet",
    "cashflow": "fin.cashflow_statement",
}


class WmshareStatementQueryParams(QueryParams):
    """Query fields shared by the income, balance sheet and cash flow models.

    This is a real ``QueryParams`` subclass, not a bare mixin: OpenBB's registry
    walks a fetcher's query model family and reads ``model_fields`` off every
    class in the MRO, so a plain mixin would crash the build.
    """

    __json_schema_extra__ = {
        "market": {"choices": ["cn", "hk", "us"]},
        "scope": {"choices": ["consolidated", "parent"]},
        "sampling": {"choices": ["Q1", "Q2", "Q3", "Q4"]},
    }

    market: Literal["cn", "hk", "us"] = Field(
        default="cn",
        description="Market segment: cn (A-share), hk (Hong Kong) or us.",
    )
    scope: Scope = Field(
        default="consolidated",
        description="'consolidated' (合并报表) or 'parent' (母公司报表). cn only.",
    )
    sampling: Sampling = Field(
        default="Q4",
        description="Fiscal quarter: Q4 = annual report (default). hk/us wide tables "
        "carry quarterly docs natively; cn quarterly reports require the A2 "
        "upstream change (GAPS A2) and currently return Q4 only.",
    )


async def fetch_statement(
    kind: str,
    symbol: str,
    *,
    limit: int | None,
    scope: str = "consolidated",
    market: str = "cn",
    sampling: str = "Q4",
    credentials: dict[str, str] | None = None,
) -> list[dict]:
    """Fetch and normalize one statement for one symbol, newest period first."""
    parsed = parse_symbol(symbol, default_market=market)
    domain = DOMAINS[kind]
    client = get_client(parsed.market, credentials)

    if parsed.market == "cn":
        return await _fetch_cn(
            client, parsed, kind, domain, limit=limit, scope=scope, sampling=sampling
        )
    return await _fetch_mkt(client, parsed, kind, domain, limit=limit, sampling=sampling)


async def _fetch_cn(
    client: Any,
    parsed: ParsedSymbol,
    kind: str,
    domain: str,
    *,
    limit: int | None,
    scope: str,
    sampling: str,
) -> list[dict]:
    """A-share path: rptdom.statement + pivot (sampling 档, 缺省 Q4 年报)."""
    rows = await call(
        client.call,
        "rptdom.statement",
        sym=parsed.code,
        domain=domain,
        opts={"scope": _SCOPE_LABEL.get(scope, "合并"), "n": int(limit or 5), "sampling": sampling},
        context=f"statements.{kind}({parsed.canonical})",
    )
    records = pivot(rows or [])
    if not records:
        raise EmptyDataError(f"No statement data returned for {parsed.canonical}.")
    for record in records:
        record["symbol"] = parsed.canonical
    return records[: int(limit)] if limit else records


async def _fetch_mkt(
    client: Any,
    parsed: ParsedSymbol,
    kind: str,
    domain: str,
    *,
    limit: int | None,
    sampling: str,
) -> list[dict]:
    """hk/us path: anchor on mkt_latest, then explicit mkt_get per period.

    The wide-table store has no period listing (provider GAPS), so the anchor
    doc's ``annual`` field drives a newest-first walk of `limit` annual
    periods at the requested sampling; missing periods are skipped (upstream
    may not publish every quarter for every year).
    """
    latest = await call(
        client.call,
        "rptdom.mkt_latest",
        sym=parsed.code,
        domain=domain,
        context=f"statements.{kind}.latest({parsed.canonical})",
    )
    if not isinstance(latest, dict) or latest.get("annual") is None:
        raise EmptyDataError(f"No statement data returned for {parsed.canonical}.")

    anchor_year = int(latest["annual"])
    wanted = int(limit or 5)
    # 缺档容忍窗口: the anchor year may not have this sampling published yet
    # (e.g. the 2026 annual report lands in 2027-03), so walk up to 3 extra
    # years back until `wanted` periods are collected.
    max_years = wanted + 3
    records: list[dict] = []
    for offset in range(max_years):
        annual = anchor_year - offset
        doc = await call(
            client.call,
            "rptdom.mkt_get",
            sym=parsed.code,
            domain=domain,
            annual=annual,
            sampling=sampling,
            context=f"statements.{kind}({parsed.canonical} {annual}{sampling})",
        )
        if not isinstance(doc, dict) or not doc:
            # 缺期 nil is normal (not every year/quarter is published).
            continue
        record = mkt_normalize(doc, parsed.market, kind)
        record["symbol"] = parsed.canonical
        # wide-table currency column is often an empty string; fall back per market
        record["currency"] = record.get("currency") or {"us": "USD", "hk": "HKD"}.get(parsed.market)
        records.append(record)
        if len(records) >= wanted:
            break
    if not records:
        raise EmptyDataError(f"No statement data returned for {parsed.canonical}.")
    return records
