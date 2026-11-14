"""wmshare index valuation trend — provider-exclusive command.

Weekly whole-building PE/PB series (~14 years) with the platform's own
multi-window percentiles — server-precomputed, not derivable from constituent
prices. Exposed as `obb.wmshare.index_valuation_trend` because no OpenBB
standard model carries index valuation quantiles.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, index_name, normalize_index_key


class WmshareIndexValuationTrendQueryParams(QueryParams):
    """wmshare Index Valuation Trend Query.

    Source: https://github.com/open-winmale/wmshare
    """

    key: str = Field(description="Index key, e.g. index.hs300 (see obb.index.available).")
    window: Literal["3y", "5y", "10y"] = Field(
        default="5y", description="Percentile window; the series itself spans ~14 years."
    )
    limit: int = Field(default=250, description="Max points returned (newest first).", ge=1)


class WmshareIndexValuationTrendData(Data):
    """wmshare Index Valuation Trend Data (weekly whole-building PE/PB points).

    `pe_pct_window` is the percentile over the requested window; the rows carry
    it repeated so a single DataFrame is self-contained.
    """

    symbol: str = Field(description="Index key the point belongs to.")
    name: str | None = Field(default=None, description="Index display name.")
    date: str = Field(description="Week-end date of the point.")
    pe: float | None = Field(default=None, description="Whole-building PE.")
    pb: float | None = Field(default=None, description="Whole-building PB.")
    pe_pct_window: float | None = Field(
        default=None,
        description="PE percentile over the requested window, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    pb_pct_window: float | None = Field(
        default=None,
        description="PB percentile over the requested window, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    window: str | None = Field(default=None, description="Percentile window requested.")
    density: str | None = Field(default=None, description="Series density (weekly).")
    asof: str | None = Field(default=None, description="Snapshot timestamp.")


class WmshareIndexValuationTrendFetcher(
    Fetcher[WmshareIndexValuationTrendQueryParams, list[WmshareIndexValuationTrendData]]
):
    """wmshare Index Valuation Trend Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIndexValuationTrendQueryParams:
        """Validate the key against the index namespace."""
        transformed = dict(params)
        transformed["key"] = normalize_index_key(transformed.get("key"))
        return WmshareIndexValuationTrendQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: WmshareIndexValuationTrendQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the trend bundle and pick the requested window's percentiles."""
        client = get_client("cn", credentials)
        trend = await call(
            client.index.trend,
            query.key,
            window=query.window,
            context=f"index.trend({query.key})",
        )
        if not isinstance(trend, dict) or not trend.get("ok", True):
            raise EmptyDataError(f"No trend series for {query.key}.")

        pct = trend.get("pct") or {}
        pe_pct = (pct.get("pe") or {}).get(f"p{query.window[0]}") or trend.get("pe_pct")
        pb_pct = (pct.get("pb") or {}).get(f"p{query.window[0]}") or trend.get("pb_pct")

        rows: list[dict] = []
        for point in (trend.get("points") or [])[: query.limit]:
            if not isinstance(point, dict) or not point.get("date"):
                continue
            rows.append(
                {
                    "symbol": query.key,
                    "name": index_name(query.key),
                    "date": point.get("date"),
                    "pe": point.get("pe"),
                    "pb": point.get("pb"),
                    "pe_pct_window": pe_pct,
                    "pb_pct_window": pb_pct,
                    "window": query.window,
                    "density": trend.get("density"),
                    "asof": trend.get("as_of"),
                }
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareIndexValuationTrendQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIndexValuationTrendData]:
        """Validate the trend points."""
        if not data:
            raise EmptyDataError()
        return [WmshareIndexValuationTrendData.model_validate(row) for row in data]
