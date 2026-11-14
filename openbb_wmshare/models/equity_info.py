"""wmshare Equity Info (company profile) model.

wmshare's profile is deliberately shallow: name, industry classification,
organisation type and listing date. Fields OpenBB declares but wmshare does not
carry (CIK, ISIN, CEO, employees, ...) stay ``None`` rather than being invented.

Profile fields are read through ``indicator.metrics`` rather than the SDK's
``info.profile`` helper. That helper sends all five codes in one eval, and
``$STYLE_INDUSTRY`` is undefined for US listings — so one missing code failed
the whole request with ``HTTP 400: undefined variable "$STYLE_INDUSTRY"``.
Requesting the codes that exist for the market keeps the other four usable.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_info import (
    EquityInfoData,
    EquityInfoQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols

PROFILE_CODES: dict[str, str] = {
    "name": "$NAME",
    "industry": "$INDUSTRY_CUR",
    "style_industry": "$STYLE_INDUSTRY",
    "org_type": "$ORG_ORGTYPE",
    "listing_date": "$ORG_LISTINGDATE",
}
"""OpenBB field -> wmshare metric code for the profile bundle."""

MARKET_PROFILE_EXCLUSIONS: dict[str, frozenset[str]] = {
    # $STYLE_INDUSTRY has no definition on the US dataset; asking for it makes
    # the whole batch eval fail rather than returning a null.
    "us": frozenset({"style_industry"}),
}
"""Fields to omit per market, keyed by the OpenBB field name."""


class WmshareEquityInfoQueryParams(EquityInfoQueryParams):
    """wmshare Equity Info Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        "market": {"choices": ["cn", "hk", "us"]},
    }

    market: Literal["cn", "hk", "us"] = Field(
        default="cn",
        description="Market segment used when a symbol carries no exchange suffix.",
    )


class WmshareEquityInfoData(EquityInfoData):
    """wmshare Equity Info Data."""

    industry: str | None = Field(
        default=None, description="Industry classification key (e.g. industry.S340501)."
    )
    industry_name: str | None = Field(
        default=None,
        description="Human-readable industry name. wmshare returns the industry key "
        "rather than a label here; resolve it via `obb.equity.search` or the "
        "`industry_name` field of wmshare's stock list.",
    )
    style_industry: str | None = Field(
        default=None, description="wmshare's higher-level style classification."
    )
    org_type: int | None = Field(default=None, description="Organisation type code.")
    listing_date: date | None = Field(default=None, description="Listing date.")
    currency: str | None = Field(default=None, description="Reporting currency of the market.")


class WmshareEquityInfoFetcher(Fetcher[WmshareEquityInfoQueryParams, list[WmshareEquityInfoData]]):
    """wmshare Equity Info Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareEquityInfoQueryParams:
        """Pass the query through unchanged."""
        return WmshareEquityInfoQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareEquityInfoQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the profile bundle for each symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            excluded = MARKET_PROFILE_EXCLUSIONS.get(parsed.market, frozenset())
            codes = [code for field, code in PROFILE_CODES.items() if field not in excluded]

            values = await call(
                client.indicator.metrics,
                parsed.code,
                codes,
                context=f"indicator.metrics({parsed.canonical})",
            )
            if not values:
                continue
            industry_key = values.get("$INDUSTRY_CUR")
            rows.append(
                _to_info_row(
                    values,
                    parsed.canonical,
                    parsed.market,
                    parsed.code,
                    industry_name=await _resolve_industry_name(client, industry_key),
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareEquityInfoQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareEquityInfoData]:
        """Validate the profile rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareEquityInfoData.model_validate(row) for row in data]


_CURRENCY_BY_MARKET = {"cn": "CNY", "hk": "HKD", "us": "USD"}


def _to_info_row(
    values: dict,
    symbol: str,
    market: str,
    code: str,
    *,
    industry_name: str | None = None,
) -> dict:
    """Map a wmshare metric bundle onto OpenBB's ``EquityInfo`` fields."""
    return {
        "symbol": symbol,
        "name": values.get("$NAME"),
        "stock_exchange": _exchange_for(code, market),
        "industry_category": values.get("$INDUSTRY_CUR"),
        "industry_name": industry_name,
        # Not requested for markets where the code is undefined, so this stays
        # None there instead of failing the whole row.
        "style_industry": values.get("$STYLE_INDUSTRY"),
        "org_type": values.get("$ORG_ORGTYPE"),
        "listing_date": values.get("$ORG_LISTINGDATE") or None,
        "currency": _CURRENCY_BY_MARKET.get(market),
        "entity_status": "active",
    }


async def _resolve_industry_name(client: Any, industry_key: str | None) -> str | None:
    """Resolve an industry key (``industry.S340501``) to its display name.

    One cheap request via ``stocks.industry_members`` — verified live for
    A-share SW codes and US Y-codes (2026-11-14, "Consumer Electronics" for
    ``industry.Y100103``). The full-table alternative is off the table: US
    ``stocks.query_list`` costs ~851k EC per call (BUGS.md D-3). A miss is a
    valid outcome for a display name, so an empty result yields ``None``.
    """
    if not industry_key:
        return None
    members = await call(
        client.call,
        "stocks.industry_members",
        ind=industry_key,
        context=f"stocks.industry_members({industry_key})",
    )
    for row in members or []:
        if isinstance(row, dict) and row.get("industry_name"):
            return str(row["industry_name"])
    return None


def _exchange_for(code: str, market: str) -> str | None:
    """Derive the listing venue from the code, which is the only signal available."""
    if market == "hk":
        return "HKEX"
    if market == "us":
        return "US"
    if code.startswith(("5", "6", "9")):
        return "SSE"
    if code.startswith(("4", "8")):
        return "BSE"
    return "SZSE"
