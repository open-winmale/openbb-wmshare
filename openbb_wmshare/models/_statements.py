"""Shared plumbing for the three wmshare statement models.

One upstream path for every market: the SDK's public ``cli.statements``
facade (``client.statements.<kind>``). Upstream serves cn via the LIST
projection (line-item codes / CN names, derived + source rows) and hk/us via
the cross-market wide tables pivoted server-side into the same line-item
shape (native subject names, original currency). This module depends only on
the facade signature — never on internal catalog function names — so the
upstream can swap backing stores without touching the provider.

Both markets converge on the same one-record-per-period layout with
``period_ending`` / ``fiscal_year`` / ``fiscal_period``.
"""

from __future__ import annotations

from typing import Literal

from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol
from openbb_wmshare.utils.statements import mkt_row_keys, pivot

Scope = Literal["consolidated", "parent"]
Period = Literal["annual", "quarter"]

_SCOPE_LABEL: dict[str, str] = {"consolidated": "合并", "parent": "母公司"}

_MARKET_CURRENCY: dict[str, str] = {"us": "USD", "hk": "HKD"}


class WmshareStatementQueryParams(QueryParams):
    """Query fields shared by the income, balance sheet and cash flow models.

    This is a real ``QueryParams`` subclass, not a bare mixin: OpenBB's registry
    walks a fetcher's query model family and reads ``model_fields`` off every
    class in the MRO, so a plain mixin would crash the build.
    """

    __json_schema_extra__ = {
        "market": {"choices": ["cn", "hk", "us"]},
        "scope": {"choices": ["consolidated", "parent"]},
        "period": {"choices": ["annual", "quarter"]},
    }

    market: Literal["cn", "hk", "us"] = Field(
        default="cn",
        description="Market segment: cn (A-share), hk (Hong Kong) or us.",
    )
    scope: Scope = Field(
        default="consolidated",
        description="'consolidated' (合并报表) or 'parent' (母公司报表). cn only — "
        "hk/us wide tables have no parent-company basis.",
    )
    period: Period = Field(
        default="annual",
        description="'annual' = annual reports (default); 'quarter' = quarterly "
        "reports Q1..Q4 interleaved (period keys like '2026:Q1').",
    )


async def fetch_statement(
    kind: str,
    symbol: str,
    *,
    limit: int | None,
    scope: str = "consolidated",
    market: str = "cn",
    period: str = "annual",
    credentials: dict[str, str] | None = None,
) -> list[dict]:
    """Fetch and normalize one statement for one symbol, newest period first."""
    parsed = parse_symbol(symbol, default_market=market)
    client = get_client(parsed.market, credentials)
    rows = await call(
        getattr(client.statements, kind),
        symbol=parsed.code,
        years=int(limit or 5),
        scope=_SCOPE_LABEL.get(scope, "合并"),
        period=period,
        context=f"statements.{kind}({parsed.canonical})",
    )
    if parsed.market != "cn":
        rows = mkt_row_keys(rows or [], parsed.market, kind)
    records = pivot(rows or [])
    if not records:
        raise EmptyDataError(f"No statement data returned for {parsed.canonical}.")
    for record in records:
        record["symbol"] = parsed.canonical
        if parsed.market != "cn":
            record["currency"] = _MARKET_CURRENCY.get(parsed.market)
    return records[: int(limit)] if limit else records
