"""wmshare analyst estimates models (forward EPS / forward PE).

`estimates.query_forecast` returns one row per forecasting institution plus an
aggregate "近六月平均" row (verified live 2026-11-14). Upstream publishes
per-year series (eps1..eps4 / pe1..pe4, year 1 = nearest fiscal year) but no
low/high/median/std-dev distribution, so those standard fields stay unset —
per-institution rows and the aggregate row pass through with their original
fields as extras. Nothing is aggregated locally.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.standard_models.forward_eps_estimates import (
    ForwardEpsEstimatesData,
    ForwardEpsEstimatesQueryParams,
)
from openbb_core.provider.standard_models.forward_pe_estimates import (
    ForwardPeEstimatesData,
    ForwardPeEstimatesQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class _WmshareEstimatesQueryParams(QueryParams):
    """Shared query fields for the two estimate models.

    Real ``QueryParams`` subclass — same registry-map reason as the segments
    models; a bare mixin crashes ``openbb-build``.
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="Symbol to get estimates for.")
    limit: int = Field(default=8, description="Forecast rows per symbol.", ge=1, le=50)
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. Analyst estimates cover A-shares only."
    )


class WmshareForwardEpsEstimatesQueryParams(
    _WmshareEstimatesQueryParams, ForwardEpsEstimatesQueryParams
):
    """wmshare Forward EPS Estimates Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = dict(_WmshareEstimatesQueryParams.__json_schema_extra__)


class WmshareForwardEpsEstimatesData(ForwardEpsEstimatesData):
    """wmshare Forward EPS Estimates Data.

    One row per institution (plus the upstream "近六月平均" aggregate). `mean`
    carries the year-1 (nearest fiscal year) EPS estimate; the full year series
    passes through as extras.
    """

    org_name: str | None = Field(default=None, description="Forecasting institution name.")
    org_code: str | None = Field(default=None, description="Forecasting institution code.")
    author: str | None = Field(default=None, description="Analyst name, when disclosed.")
    rating: str | None = Field(default=None, description="Institution rating text.")
    compre_rating: str | None = Field(default=None, description="Comprehensive rating text.")
    date_type: str | None = Field(
        default=None, description="Aggregate window (e.g. 1月内) on rating rows."
    )
    eps1: float | None = Field(default=None, description="Year-1 forecast EPS.")
    eps2: float | None = Field(default=None, description="Year-2 forecast EPS.")
    eps3: float | None = Field(default=None, description="Year-3 forecast EPS.")
    eps4: float | None = Field(default=None, description="Year-4 forecast EPS.")
    pe1: float | None = Field(default=None, description="Year-1 implied PE.")
    pe2: float | None = Field(default=None, description="Year-2 implied PE.")
    pe3: float | None = Field(default=None, description="Year-3 implied PE.")
    pe4: float | None = Field(default=None, description="Year-4 implied PE.")
    parent_netprofit1: float | None = Field(default=None, description="Year-1 forecast net profit.")
    parent_netprofit2: float | None = Field(default=None, description="Year-2 forecast net profit.")
    parent_netprofit3: float | None = Field(default=None, description="Year-3 forecast net profit.")
    parent_netprofit4: float | None = Field(default=None, description="Year-4 forecast net profit.")


class WmshareForwardEpsEstimatesFetcher(
    Fetcher[WmshareForwardEpsEstimatesQueryParams, list[WmshareForwardEpsEstimatesData]]
):
    """wmshare Forward EPS Estimates Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareForwardEpsEstimatesQueryParams:
        """Pass the query through unchanged."""
        return WmshareForwardEpsEstimatesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareForwardEpsEstimatesQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch forecast rows per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            forecasts = await call(
                client.estimates.query_forecast,
                parsed.code,
                limit=query.limit,
                context=f"estimates.query_forecast({parsed.canonical})",
            )
            for row in forecasts or []:
                if not isinstance(row, dict) or not row.get("publish_date"):
                    # `date` is required by the standard model.
                    continue
                entry = {"symbol": parsed.canonical, **row}
                entry["date"] = row["publish_date"]
                entry["mean"] = row.get("eps1")
                rows.append(entry)
        return rows

    @staticmethod
    def transform_data(
        query: WmshareForwardEpsEstimatesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareForwardEpsEstimatesData]:
        """Validate the forecast rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareForwardEpsEstimatesData.model_validate(row) for row in data]


class WmshareForwardPeEstimatesQueryParams(
    _WmshareEstimatesQueryParams, ForwardPeEstimatesQueryParams
):
    """wmshare Forward PE Estimates Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = dict(_WmshareEstimatesQueryParams.__json_schema_extra__)


class WmshareForwardPeEstimatesData(ForwardPeEstimatesData):
    """wmshare Forward PE Estimates Data.

    `year1..year4` map to the upstream PE1..PE4 series; wmshare publishes four
    predicted years, so `year5` stays unset.
    """

    org_name: str | None = Field(default=None, description="Forecasting institution name.")
    org_code: str | None = Field(default=None, description="Forecasting institution code.")
    publish_date: str | None = Field(default=None, description="Forecast publish date.")


class WmshareForwardPeEstimatesFetcher(
    Fetcher[WmshareForwardPeEstimatesQueryParams, list[WmshareForwardPeEstimatesData]]
):
    """wmshare Forward PE Estimates Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareForwardPeEstimatesQueryParams:
        """Pass the query through unchanged."""
        return WmshareForwardPeEstimatesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareForwardPeEstimatesQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch forecast rows per symbol, re-keyed to the year series."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            forecasts = await call(
                client.estimates.query_forecast,
                parsed.code,
                limit=query.limit,
                context=f"estimates.query_forecast({parsed.canonical})",
            )
            for row in forecasts or []:
                if not isinstance(row, dict) or not row.get("publish_date"):
                    continue
                rows.append(
                    {
                        "symbol": parsed.canonical,
                        "name": None,
                        "year1": row.get("pe1"),
                        "year2": row.get("pe2"),
                        "year3": row.get("pe3"),
                        "year4": row.get("pe4"),
                        "org_name": row.get("org_name"),
                        "org_code": row.get("org_code"),
                        "publish_date": row.get("publish_date"),
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareForwardPeEstimatesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareForwardPeEstimatesData]:
        """Validate the estimate rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareForwardPeEstimatesData.model_validate(row) for row in data]
