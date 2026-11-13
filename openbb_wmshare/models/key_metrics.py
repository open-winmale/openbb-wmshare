"""wmshare Key Metrics model.

wmshare's indicator layer returns server-precomputed metrics in one request per
symbol. The codes used here are the ones exercised by ``cli.indicator.basic``
and ``cli.indicator.financials``, plus valuation and yield codes from the
catalog.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.key_metrics import (
    KeyMetricsData,
    KeyMetricsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols

METRIC_CODES: dict[str, str] = {
    "pe_ttm": "$PE_TTM_LAST",
    "pb": "$PB",
    "ps_ttm": "$PS_TTM_LAST",
    # $MV_LAST is the per-symbol market cap. Do not use $ID_MV_LAST: the "ID_"
    # family is an industry-aggregate namespace and returns nil for one symbol.
    "market_cap": "$MV_LAST",
    "roe_ttm": "$ROE_TTM_LAST",
    "eps_ttm": "$EPS_DPPR_TTM_LAST",
    # $BONUS_RATE_TTM_LAST is the dividend *yield*; $BONUS_TTM_RATE_LAST is the
    # payout ratio (dividends / net profit) and is the wrong number here.
    "dividend_yield_ttm": "$BONUS_RATE_TTM_LAST",
    "total_revenue_ttm": "$TR_TTM_LAST",
    "net_profit_ttm": "$NP_TTM_LAST",
    "pe_percentile_10y": "$PCT_PE_TTM_10Y_LAST",
}
"""OpenBB field name → wmshare metric code, for one batched indicator request."""

_CURRENCY_BY_MARKET = {"cn": "CNY", "hk": "HKD", "us": "USD"}


class WmshareKeyMetricsQueryParams(KeyMetricsQueryParams):
    """wmshare Key Metrics Query.

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


class WmshareKeyMetricsData(KeyMetricsData):
    """wmshare Key Metrics Data.

    The indicator layer is point-in-time: every row describes the latest
    available reading, so ``period_ending`` is the request date rather than a
    fiscal period end.
    """

    pe_ttm: float | None = Field(default=None, description="Price-to-earnings ratio (TTM).")
    pb: float | None = Field(default=None, description="Price-to-book ratio.")
    ps_ttm: float | None = Field(default=None, description="Price-to-sales ratio (TTM).")
    roe_ttm: float | None = Field(
        default=None,
        description="Return on equity (TTM), as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    eps_ttm: float | None = Field(default=None, description="Earnings per share (TTM).")
    dividend_yield_ttm: float | None = Field(
        default=None,
        description="Trailing-twelve-month dividend yield, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    total_revenue_ttm: float | None = Field(
        default=None, description="Trailing-twelve-month total revenue."
    )
    net_profit_ttm: float | None = Field(
        default=None, description="Trailing-twelve-month net profit."
    )
    pe_percentile_10y: float | None = Field(
        default=None,
        description="Ten-year percentile rank of the PE ratio, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareKeyMetricsFetcher(Fetcher[WmshareKeyMetricsQueryParams, list[WmshareKeyMetricsData]]):
    """wmshare Key Metrics Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareKeyMetricsQueryParams:
        """Pass the query through unchanged."""
        return WmshareKeyMetricsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareKeyMetricsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch all metric codes for each symbol in a single request."""
        rows: list[dict] = []
        today = date.today().isoformat()
        codes = list(METRIC_CODES.values())

        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            values = await call(
                client.indicator.metrics,
                parsed.code,
                codes,
                context=f"indicator.metrics({parsed.canonical})",
            )
            if not values:
                continue

            row: dict[str, Any] = {
                "symbol": parsed.canonical,
                "period_ending": today,
                "currency": _CURRENCY_BY_MARKET.get(parsed.market),
            }
            for field_name, code in METRIC_CODES.items():
                row[field_name] = values.get(code)
            rows.append(row)
        return rows

    @staticmethod
    def transform_data(
        query: WmshareKeyMetricsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareKeyMetricsData]:
        """Validate the metric rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareKeyMetricsData.model_validate(row) for row in data]
