"""wmshare revenue-segmentation models (business lines + geography).

wmshare's segments domain exposes three dims (product / business / region).
`segments.periods` supplies the fiscal period of the disclosure (`clean_last`,
e.g. "2026:Q3" → 2026-09-30), stamped onto every row since the upstream rows
themselves carry no period.

Rows whose `tr` (revenue) is missing are skipped: the standard models require
`revenue`. The region dim uses the clean MAP (`domestic` / `overseas` buckets
with tr/pct/margin/yoy); the raw detail view adds nothing those lack.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.standard_models.revenue_business_line import (
    RevenueBusinessLineData,
    RevenueBusinessLineQueryParams,
)
from openbb_core.provider.standard_models.revenue_geographic import (
    RevenueGeographicData,
    RevenueGeographicQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols
from openbb_wmshare.utils.statements import parse_period


class _WmshareSegmentsQueryParams(QueryParams):
    """Shared query fields for the two segment models.

    A real ``QueryParams`` subclass, not a bare mixin: OpenBB's registry map
    walks the fetcher's query-model family and reads ``model_fields`` off
    every class in the MRO.
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="Symbol to get revenue segments for.")
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. Segment disclosures cover A-shares only."
    )


async def _fetch_period(client: Any, code: str, context: str) -> Any:
    """Latest disclosure period of the segments domain ("2026:Q3" → date)."""
    periods = await call(client.segments.periods, code, context=context)
    if isinstance(periods, dict):
        return parse_period(str(periods.get("clean_last") or ""))[2]
    return None


async def _segment_rows(client: Any, code: str, rows: Any, period_ending: Any) -> list[dict]:
    """Normalize segment rows, dropping revenue-less entries."""
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        tr = row.get("tr")
        if not name or not isinstance(tr, int | float):
            continue
        out.append(
            {
                "business_line": name,
                "region": name,
                "revenue": tr,
                "period_ending": period_ending,
                "cost": row.get("cost") or None,
                "margin": row.get("margin"),
                "share_ratio": row.get("ratio") or None,
                "tr_text": row.get("tr_text"),
            }
        )
    return out


class WmshareRevenueBusinessLineQueryParams(
    _WmshareSegmentsQueryParams, RevenueBusinessLineQueryParams
):
    """wmshare Revenue per Segment Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        **_WmshareSegmentsQueryParams.__json_schema_extra__,
        "dim": {"choices": ["product", "business"]},
    }

    dim: Literal["product", "business"] = Field(
        default="product",
        description="Segmentation dim: product (分产品) or business (分业务).",
    )


class WmshareRevenueBusinessLineData(RevenueBusinessLineData):
    """wmshare Revenue per Segment Data."""

    cost: float | None = Field(default=None, description="Segment cost, in CNY.")
    margin: float | None = Field(
        default=None,
        description="Segment gross margin, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    share_ratio: float | None = Field(
        default=None,
        description="Segment share of total revenue, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    tr_text: str | None = Field(default=None, description="Upstream display string for revenue.")


class WmshareRevenueBusinessLineFetcher(
    Fetcher[WmshareRevenueBusinessLineQueryParams, list[WmshareRevenueBusinessLineData]]
):
    """wmshare Revenue per Segment Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareRevenueBusinessLineQueryParams:
        """Pass the query through unchanged."""
        return WmshareRevenueBusinessLineQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareRevenueBusinessLineQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch product/business rows and stamp the disclosure period."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            period_ending = await _fetch_period(
                client, parsed.code, context=f"segments.periods({parsed.canonical})"
            )
            if query.dim == "product":
                segment_rows = await call(
                    client.segments.products,
                    parsed.code,
                    limit=50,
                    context=f"segments.products({parsed.canonical})",
                )
            else:
                segment_rows = await call(
                    client.segments.business,
                    parsed.code,
                    limit=50,
                    context=f"segments.business({parsed.canonical})",
                )
            rows.extend(await _segment_rows(client, parsed.code, segment_rows, period_ending))
        return rows

    @staticmethod
    def transform_data(
        query: WmshareRevenueBusinessLineQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareRevenueBusinessLineData]:
        """Validate the segment rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareRevenueBusinessLineData.model_validate(row) for row in data]


class WmshareRevenueGeographicQueryParams(
    _WmshareSegmentsQueryParams, RevenueGeographicQueryParams
):
    """wmshare Revenue per Geography Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = dict(_WmshareSegmentsQueryParams.__json_schema_extra__)


class WmshareRevenueGeographicData(RevenueGeographicData):
    """wmshare Revenue per Geography Data."""

    margin: float | None = Field(
        default=None,
        description="Region gross margin, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    yoy: float | None = Field(
        default=None,
        description="Revenue growth YoY, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    pct: float | None = Field(
        default=None,
        description="Region share of total revenue, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareRevenueGeographicFetcher(
    Fetcher[WmshareRevenueGeographicQueryParams, list[WmshareRevenueGeographicData]]
):
    """wmshare Revenue per Geography Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareRevenueGeographicQueryParams:
        """Pass the query through unchanged."""
        return WmshareRevenueGeographicQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareRevenueGeographicQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the clean domestic/overseas buckets per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            region = await call(
                client.segments.region,
                parsed.code,
                context=f"segments.region({parsed.canonical})",
            )
            if not isinstance(region, dict) or "domestic" not in region:
                continue
            period_ending = parse_period(str(region.get("report_sas") or ""))[2]
            for bucket in ("domestic", "overseas"):
                entry = region.get(bucket)
                if not isinstance(entry, dict):
                    continue
                tr = entry.get("tr")
                if not isinstance(tr, int | float):
                    continue
                rows.append(
                    {
                        "region": bucket,
                        "revenue": tr,
                        "period_ending": period_ending,
                        "margin": entry.get("margin") or None,
                        "yoy": entry.get("yoy"),
                        "pct": entry.get("pct"),
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareRevenueGeographicQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareRevenueGeographicData]:
        """Validate the region rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareRevenueGeographicData.model_validate(row) for row in data]
