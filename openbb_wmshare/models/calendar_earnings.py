"""wmshare Calendar Earnings model.

wmshare's disclosure history is per-symbol (`forecast.disclosure_rows`, no
market-wide calendar upstream), so `symbol` is a required provider parameter
even though the standard model only takes a date range — the same pattern as
`WmshareCalendarDividendQueryParams`.

The standard `report_date` is the *calendar* date the earnings event lands on
(最新预约披露日, falling back to the actual date); the upstream fiscal period
end passes through as `fiscal_period_end`. wmshare discloses no EPS values in
this endpoint, so `eps_previous` / `eps_consensus` stay unset.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.calendar_earnings import (
    CalendarEarningsData,
    CalendarEarningsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareCalendarEarningsQueryParams(CalendarEarningsQueryParams):
    """wmshare Calendar Earnings Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(
        description="Symbol(s) to build the earnings calendar for; wmshare has no "
        "market-wide disclosure calendar."
    )
    limit: int = Field(default=8, description="Disclosure rows per symbol.", ge=1, le=50)
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. Disclosure calendars cover A-shares only."
    )


class WmshareCalendarEarningsData(CalendarEarningsData):
    """wmshare Calendar Earnings Data."""

    fiscal_period_end: str | None = Field(
        default=None, description="Fiscal period the report covers (e.g. 2026-09-30)."
    )
    actual_publish_date: str | None = Field(default=None, description="Actual disclosure date.")
    first_appoint_date: str | None = Field(default=None, description="Originally appointed date.")
    change_count: int | None = Field(default=None, description="Times the appointment changed.")
    report_type_name: str | None = Field(default=None, description="Report kind (e.g. 三季报).")
    is_publish: str | None = Field(default=None, description="Upstream published flag.")


class WmshareCalendarEarningsFetcher(
    Fetcher[WmshareCalendarEarningsQueryParams, list[WmshareCalendarEarningsData]]
):
    """wmshare Calendar Earnings Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareCalendarEarningsQueryParams:
        """Pass the query through unchanged."""
        return WmshareCalendarEarningsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareCalendarEarningsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch disclosure rows per symbol, filtered to the window."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            history = await call(
                client.forecast.disclosure_history,
                parsed.code,
                limit=query.limit,
                context=f"forecast.disclosure_history({parsed.canonical})",
            )
            for row in history or []:
                if not isinstance(row, dict):
                    continue
                # Calendar date: the appointment, falling back to the actual date.
                calendar_date = row.get("latest_appoint_date") or row.get("actual_publish_date")
                if not calendar_date:
                    continue
                mapped = {
                    "symbol": parsed.canonical,
                    "report_date": calendar_date,
                    "name": row.get("report_type_name"),
                    "fiscal_period_end": row.get("report_date"),
                    "actual_publish_date": row.get("actual_publish_date"),
                    "first_appoint_date": row.get("first_appoint_date"),
                    "change_count": row.get("change_count"),
                    "report_type_name": row.get("report_type_name"),
                    "is_publish": row.get("is_publish"),
                }
                if _in_window(mapped["report_date"], query):
                    rows.append(mapped)
        return rows

    @staticmethod
    def transform_data(
        query: WmshareCalendarEarningsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareCalendarEarningsData]:
        """Validate the calendar rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareCalendarEarningsData.model_validate(row) for row in data]


def _in_window(calendar_date: Any, query: Any) -> bool:
    """Check the calendar date against the optional start/end window."""
    from datetime import date

    if not calendar_date:
        return False
    try:
        value = date.fromisoformat(str(calendar_date)[:10])
    except ValueError:
        return False
    start = getattr(query, "start_date", None)
    end = getattr(query, "end_date", None)
    after_start = start is None or value >= start
    before_end = end is None or value <= end
    return after_start and before_end
