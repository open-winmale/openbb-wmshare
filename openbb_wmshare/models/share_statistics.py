"""wmshare Share Statistics model.

`equity.query_capital_change` returns the latest `{total_shares, free_shares}`
snapshot. `free_float` (the standard model's normalized 0-1 share) is the
trivial ratio of the two upstream fields — computed here because wmshare has
no dedicated code for it; both inputs come from the catalog function.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.share_statistics import (
    ShareStatisticsData,
    ShareStatisticsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareShareStatisticsQueryParams(ShareStatisticsQueryParams):
    """wmshare Share Statistics Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="Symbol to get share statistics for.")
    market: Literal["cn"] = Field(
        default="cn",
        description="Market segment. Capital-change data covers A-shares only.",
    )


class WmshareShareStatisticsData(ShareStatisticsData):
    """wmshare Share Statistics Data."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")


class WmshareShareStatisticsFetcher(
    Fetcher[WmshareShareStatisticsQueryParams, list[WmshareShareStatisticsData]]
):
    """wmshare Share Statistics Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareShareStatisticsQueryParams:
        """Pass the query through unchanged."""
        return WmshareShareStatisticsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareShareStatisticsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the latest capital snapshot per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            capital = await call(
                client.equity.query_capital_change,
                parsed.code,
                context=f"equity.query_capital_change({parsed.canonical})",
            )
            if not isinstance(capital, dict):
                continue
            total = capital.get("total_shares")
            free = capital.get("free_shares")
            free_float = (
                free / total
                if isinstance(total, int | float) and isinstance(free, int | float) and total > 0
                else None
            )
            rows.append(
                {
                    "symbol": parsed.canonical,
                    "outstanding_shares": total,
                    "float_shares": free,
                    "free_float": free_float,
                }
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareShareStatisticsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareShareStatisticsData]:
        """Validate the rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareShareStatisticsData.model_validate(row) for row in data]
