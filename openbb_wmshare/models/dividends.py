"""wmshare dividend models.

Two standard models are served from the same source:

* ``HistoricalDividends`` — one symbol's dividend history; the natural fit.
* ``CalendarDividend`` — the same rows re-shaped as a date-range calendar,
  because some OpenBB consumers (and the charting layer) use that command.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.calendar_dividend import (
    CalendarDividendData,
    CalendarDividendQueryParams,
)
from openbb_core.provider.standard_models.historical_dividends import (
    HistoricalDividendsData,
    HistoricalDividendsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import (
    call,
    get_client,
    parse_symbol,
    resolve_range,
    split_symbols,
)

MAX_HISTORY_ROWS = 500
"""Rows per dividend-history request.

The SDK client defaults to ``max_limit=500`` and rejects anything larger before
the request is sent, so asking for 10,000 fails outright. A-share companies have
at most a few dozen dividend events, so one page covers a full history.
"""


def _dividend_fields(row: dict, symbol: str) -> dict:
    """Map a wmshare dividend row onto OpenBB's dividend field names."""
    return {
        "symbol": symbol,
        "ex_dividend_date": row.get("ex_date") or row.get("ex_div"),
        "amount": row.get("dps"),
        "payment_date": row.get("pay"),
        "declaration_date": row.get("announce"),
        "currency": row.get("ccy"),
        "frequency": row.get("sas"),
        "total_amount": row.get("total"),
        "payout_ratio": row.get("payout_ratio") or None,
    }


class WmshareHistoricalDividendsQueryParams(HistoricalDividendsQueryParams):
    """wmshare Historical Dividends Query.

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


class WmshareHistoricalDividendsData(HistoricalDividendsData):
    """wmshare Historical Dividends Data."""

    payment_date: date | None = Field(default=None, description="Payment date.")
    declaration_date: date | None = Field(default=None, description="Announcement date.")
    currency: str | None = Field(default=None, description="Dividend currency.")
    frequency: str | None = Field(
        default=None, description="Fiscal period the dividend belongs to (e.g. 2025:Q4)."
    )
    total_amount: float | None = Field(
        default=None, description="Total cash distributed across all shares."
    )
    payout_ratio: float | None = Field(
        default=None,
        description="Dividend as a share of net profit, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareHistoricalDividendsFetcher(
    Fetcher[WmshareHistoricalDividendsQueryParams, list[WmshareHistoricalDividendsData]]
):
    """wmshare Historical Dividends Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareHistoricalDividendsQueryParams:
        """Pass the query through unchanged."""
        return WmshareHistoricalDividendsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareHistoricalDividendsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch dividend history per symbol, filtered to the requested range."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)

            history = await call(
                client.dividend.history,
                parsed.code,
                limit=MAX_HISTORY_ROWS,
                context=f"dividend.history({parsed.canonical})",
            )
            for row in history or []:
                if not isinstance(row, dict):
                    continue
                mapped = _dividend_fields(row, parsed.canonical)
                if not _in_range(mapped.get("ex_dividend_date"), query):
                    continue
                if mapped.get("amount") is None:
                    continue
                rows.append(mapped)
        return rows

    @staticmethod
    def transform_data(
        query: WmshareHistoricalDividendsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareHistoricalDividendsData]:
        """Validate the dividend rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareHistoricalDividendsData.model_validate(row) for row in data]


class WmshareCalendarDividendQueryParams(CalendarDividendQueryParams):
    """wmshare Calendar Dividend Query.

    ``symbol`` is required despite being absent from the standard model:
    wmshare has no cross-market dividend calendar, so a calendar can only be
    produced for a known set of symbols.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        "market": {"choices": ["cn", "hk", "us"]},
    }

    symbol: str = Field(description="Symbol(s) to build the dividend calendar for.")
    market: Literal["cn", "hk", "us"] = Field(
        default="cn",
        description="Market segment used when a symbol carries no exchange suffix.",
    )


class WmshareCalendarDividendData(CalendarDividendData):
    """wmshare Calendar Dividend Data."""

    currency: str | None = Field(default=None, description="Dividend currency.")
    fiscal_period: str | None = Field(
        default=None, description="Fiscal period the dividend belongs to (e.g. 2025:Q4)."
    )


class WmshareCalendarDividendFetcher(
    Fetcher[WmshareCalendarDividendQueryParams, list[WmshareCalendarDividendData]]
):
    """wmshare Calendar Dividend Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareCalendarDividendQueryParams:
        """Default the calendar window to the trailing year."""
        transformed = dict(params)
        if transformed.get("start_date") is None and transformed.get("end_date") is None:
            window = resolve_range(None, None)
            transformed["start_date"] = window.start
            transformed["end_date"] = window.end
        return WmshareCalendarDividendQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: WmshareCalendarDividendQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the dividend events that fall inside the window."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            history = await call(
                client.dividend.history,
                parsed.code,
                limit=MAX_HISTORY_ROWS,
                context=f"dividend.history({parsed.canonical})",
            )
            for row in history or []:
                if not isinstance(row, dict):
                    continue
                mapped = _dividend_fields(row, parsed.canonical)
                if not _in_range(mapped.get("ex_dividend_date"), query):
                    continue
                rows.append(
                    {
                        "symbol": parsed.canonical,
                        "ex_dividend_date": mapped["ex_dividend_date"],
                        "amount": mapped.get("amount"),
                        "payment_date": mapped.get("payment_date"),
                        "declaration_date": mapped.get("declaration_date"),
                        "currency": mapped.get("currency"),
                        "fiscal_period": mapped.get("frequency"),
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareCalendarDividendQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareCalendarDividendData]:
        """Validate the calendar rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareCalendarDividendData.model_validate(row) for row in data]


def _in_range(ex_date: Any, query: Any) -> bool:
    """Check an ex-dividend date against the query window, tolerating missing bounds."""
    if ex_date is None:
        return False
    text = str(ex_date)[:10]
    try:
        value = date.fromisoformat(text)
    except ValueError:
        return False
    start = getattr(query, "start_date", None)
    end = getattr(query, "end_date", None)
    after_start = start is None or value >= start
    before_end = end is None or value <= end
    return after_start and before_end
