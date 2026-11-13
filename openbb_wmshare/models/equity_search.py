"""wmshare Equity Search model.

Backed by wmshare's bundled offline symbol catalog, so this endpoint makes no
network request and needs no credentials.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_search import (
    EquitySearchData,
    EquitySearchQueryParams,
)
from pydantic import Field

_EXCHANGE_BY_MARKET = {"cn": None, "hk": "HKEX", "us": "US"}
"""Search rows carry no venue, so only the market-level venue can be stated."""


class WmshareEquitySearchQueryParams(EquitySearchQueryParams):
    """wmshare Equity Search Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"market": {"choices": ["cn", "hk", "us"]}}

    market: Literal["cn", "hk", "us"] = Field(
        default="cn",
        description="Market to search: cn (A-share), hk (Hong Kong) or us.",
    )


class WmshareEquitySearchData(EquitySearchData):
    """wmshare Equity Search Data."""

    market: str | None = Field(default=None, description="Market segment of the result.")
    exchange: str | None = Field(default=None, description="Listing exchange code.")


class WmshareEquitySearchFetcher(
    Fetcher[WmshareEquitySearchQueryParams, list[WmshareEquitySearchData]]
):
    """wmshare Equity Search Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareEquitySearchQueryParams:
        """Pass the query through unchanged."""
        return WmshareEquitySearchQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareEquitySearchQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Search the offline symbol table.

        An empty query returns nothing rather than the whole universe: dumping
        ~5,700 A-share rows is never what a caller wants, and the catalog search
        has no pagination.
        """
        term = str(query.query or "").strip()
        if not term:
            return []

        from wmshare import load

        catalog = load()
        matches = catalog.symbols_search(term, market=query.market)
        return [
            {
                "symbol": _canonical(row.get("code"), query.market),
                "name": row.get("name"),
                "market": query.market,
                "exchange": _exchange_for(row.get("code"), query.market),
            }
            for row in matches
            if row.get("code")
        ]

    @staticmethod
    def transform_data(
        query: WmshareEquitySearchQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareEquitySearchData]:
        """Validate the search rows.

        An empty result is a valid answer for a search, not an error.
        """
        return [WmshareEquitySearchData.model_validate(row) for row in data]


def _exchange_for(code: Any, market: str) -> str | None:
    """Resolve the venue: A-share from the code prefix, otherwise the market."""
    if market != "cn":
        return _EXCHANGE_BY_MARKET.get(market)
    text = str(code or "").strip().zfill(6)
    if text.startswith(("5", "6", "9")):
        return "SSE"
    if text.startswith(("4", "8")):
        return "BSE"
    return "SZSE"


def _canonical(code: Any, market: str) -> str:
    """Render the exchange suffix for the market.

    ``symbols_search`` returns bare codes; surfacing them as ``600519.SH`` /
    ``00700.HK`` keeps the output directly usable in the other endpoints.
    """
    text = str(code or "").strip()
    if market == "cn":
        from openbb_wmshare.utils.symbols import ParsedSymbol

        return ParsedSymbol("cn", text).canonical
    if market == "hk":
        return f"{text.zfill(5)}.HK"
    return text.upper()
