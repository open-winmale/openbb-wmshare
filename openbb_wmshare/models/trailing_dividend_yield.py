"""wmshare Trailing Dividend Yield model.

Point-in-time: wmshare's ``bonus.snapshot_yield_ttm`` is a single TTM reading
with no history, so ``limit`` (the standard model's lookback window) has
nothing to page through — one row per symbol is the complete, honest answer.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.trailing_dividend_yield import (
    TrailingDivYieldData,
    TrailingDivYieldQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareTrailingDivYieldQueryParams(TrailingDivYieldQueryParams):
    """wmshare Trailing Dividend Yield Query.

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


class WmshareTrailingDivYieldData(TrailingDivYieldData):
    """wmshare Trailing Dividend Yield Data."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    currency: str | None = Field(default=None, description="Dividend currency of the market.")


class WmshareTrailingDivYieldFetcher(
    Fetcher[WmshareTrailingDivYieldQueryParams, list[WmshareTrailingDivYieldData]]
):
    """wmshare Trailing Dividend Yield Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareTrailingDivYieldQueryParams:
        """Pass the query through unchanged.

        ``limit`` is accepted for interface compatibility but carries no
        meaning here: wmshare publishes only the current TTM value, not a
        series, so overriding it would fabricate history.
        """
        return WmshareTrailingDivYieldQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareTrailingDivYieldQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the TTM dividend yield per symbol."""
        today = date.today().isoformat()
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            value = await call(
                client.dividend.yield_ttm,
                parsed.code,
                context=f"dividend.yield_ttm({parsed.canonical})",
            )
            if value is None:
                continue
            rows.append(
                {
                    "symbol": parsed.canonical,
                    "date": today,
                    "trailing_dividend_yield": value,
                    "currency": _CURRENCY_BY_MARKET.get(parsed.market),
                }
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareTrailingDivYieldQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareTrailingDivYieldData]:
        """Validate the yield rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareTrailingDivYieldData.model_validate(row) for row in data]


_CURRENCY_BY_MARKET = {"cn": "CNY", "hk": "HKD", "us": "USD"}
