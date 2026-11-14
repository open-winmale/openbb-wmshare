"""wmshare market movers (gainers / losers) models.

Both commands map onto the same upstream call — ``screener.index_top_movers``
is a server-side precomputed ranking of the whole market by the day's percent
change, so gainers and losers differ only in sort direction.

The upstream rows carry just ``{symbol, name, percent}``: there is no price or
absolute change, so the standard model's required ``price`` / ``change``
fields are relaxed to optional rather than filled with fabrications.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.market_movers import (
    MarketMoversData,
    MarketMoversQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client
from openbb_wmshare.utils.symbols import ParsedSymbol


class _WmshareMarketMoversQueryParams(MarketMoversQueryParams):
    """Shared query for gainers / losers."""

    limit: int = Field(
        default=20,
        description="Number of ranked symbols to return.",
        ge=1,
        le=100,
    )


class WmshareMarketMoversData(MarketMoversData):
    """wmshare Market Movers Data.

    ``price`` and ``change`` are relaxed to optional: the upstream ranking
    publishes the percent change only.
    """

    price: float | None = Field(default=None, description="Last price.")
    change: float | None = Field(default=None, description="Absolute change from prior close.")


async def _extract(
    query: _WmshareMarketMoversQueryParams,
    credentials: dict[str, str] | None,
    *,
    desc: bool,
) -> list[dict]:
    """Fetch one ranking (single request, whole market, server-precomputed)."""
    client = get_client("cn", credentials)
    rows = await call(
        client.screener.index_top_movers,
        limit=query.limit,
        desc=desc,
        context="screener.index_top_movers",
    )
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        out.append(
            {
                "symbol": ParsedSymbol("cn", str(row["symbol"]).zfill(6)).canonical,
                "name": row.get("name"),
                "change_percent": row.get("percent"),
            }
        )
    return out


class WmshareEquityGainersQueryParams(_WmshareMarketMoversQueryParams):
    """wmshare Equity Gainers Query.

    Source: https://github.com/open-winmale/wmshare
    """

    market: Literal["cn"] = Field(
        default="cn", description="Market. wmshare market movers cover A-shares only."
    )


class WmshareEquityGainersFetcher(
    Fetcher[WmshareEquityGainersQueryParams, list[WmshareMarketMoversData]]
):
    """wmshare Equity Gainers Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareEquityGainersQueryParams:
        """Pass the query through unchanged."""
        return WmshareEquityGainersQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareEquityGainersQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the day's biggest gainers."""
        return await _extract(query, credentials, desc=True)

    @staticmethod
    def transform_data(
        query: WmshareEquityGainersQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareMarketMoversData]:
        """Validate the ranking rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareMarketMoversData.model_validate(row) for row in data]


class WmshareEquityLosersQueryParams(_WmshareMarketMoversQueryParams):
    """wmshare Equity Losers Query.

    Source: https://github.com/open-winmale/wmshare
    """

    market: Literal["cn"] = Field(
        default="cn", description="Market. wmshare market movers cover A-shares only."
    )


class WmshareEquityLosersFetcher(
    Fetcher[WmshareEquityLosersQueryParams, list[WmshareMarketMoversData]]
):
    """wmshare Equity Losers Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareEquityLosersQueryParams:
        """Pass the query through unchanged."""
        return WmshareEquityLosersQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareEquityLosersQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the day's biggest losers."""
        return await _extract(query, credentials, desc=False)

    @staticmethod
    def transform_data(
        query: WmshareEquityLosersQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareMarketMoversData]:
        """Validate the ranking rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareMarketMoversData.model_validate(row) for row in data]
