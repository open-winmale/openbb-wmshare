"""Shared plumbing for the three wmshare statement models.

``rptdom.statement`` returns line items per fiscal period, one row per item.
All three OpenBB statement models need the same fetch-then-pivot step, so it
lives here instead of being triplicated.
"""

from __future__ import annotations

from typing import Literal

from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError, OpenBBError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol
from openbb_wmshare.utils.statements import pivot

Scope = Literal["consolidated", "parent"]

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
        "market": {"choices": ["cn"]},
        "scope": {"choices": ["consolidated", "parent"]},
    }

    market: Literal["cn"] = Field(
        default="cn",
        description="Market segment. wmshare publishes statements for A-shares only.",
    )
    scope: Scope = Field(
        default="consolidated",
        description="'consolidated' (合并报表) or 'parent' (母公司报表).",
    )


async def fetch_statement(
    kind: str,
    symbol: str,
    *,
    limit: int | None,
    scope: str = "consolidated",
    market: str = "cn",
    credentials: dict[str, str] | None = None,
) -> list[dict]:
    """Fetch and pivot one statement for one symbol.

    ``limit`` maps to wmshare's ``years`` argument, which counts annual report
    periods. Quarterly statements are not published upstream, so ``fiscal_period``
    is always ``"FY"``.
    """
    parsed = parse_symbol(symbol, default_market=market)  # type: ignore[arg-type]
    if parsed.market != "cn":
        raise OpenBBError(
            f"wmshare publishes financial statements for A-shares only; "
            f"{parsed.canonical} is a {parsed.market.upper()} symbol. "
            "Use a different provider for HK/US fundamentals."
        )

    domain = DOMAINS[kind]
    client = get_client(parsed.market, credentials)
    rows = await call(
        client.call,
        "rptdom.statement",
        sym=parsed.code,
        domain=domain,
        opts={"scope": _SCOPE_LABEL.get(scope, "合并"), "n": int(limit or 5)},
        context=f"statements.{kind}({parsed.canonical})",
    )

    records = pivot(rows or [])
    if not records:
        raise EmptyDataError(f"No statement data returned for {parsed.canonical}.")
    for record in records:
        record["symbol"] = parsed.canonical
    return records[: int(limit)] if limit else records
