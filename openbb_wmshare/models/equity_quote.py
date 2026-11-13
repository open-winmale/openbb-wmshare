"""wmshare Equity Quote model."""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_quote import (
    EquityQuoteData,
    EquityQuoteQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import (
    call,
    get_client,
    parse_symbol,
    require_rows,
    split_symbols,
)


class WmshareEquityQuoteQueryParams(EquityQuoteQueryParams):
    """wmshare Equity Quote Query.

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


class WmshareEquityQuoteData(EquityQuoteData):
    """wmshare Equity Quote Data."""

    prev_close: float | None = Field(default=None, description="Previous closing price.")
    year_high: float | None = Field(default=None, description="52-week high.")
    year_low: float | None = Field(default=None, description="52-week low.")
    ma_20: float | None = Field(default=None, description="20-period simple moving average.")
    ma_60: float | None = Field(default=None, description="60-period simple moving average.")
    ma_120: float | None = Field(default=None, description="120-period simple moving average.")
    market_cap: float | None = Field(default=None, description="Market capitalisation.")
    free_float_market_cap: float | None = Field(
        default=None, description="Free-float market capitalisation."
    )
    change_5d: float | None = Field(
        default=None,
        description="Price change over 5 trading days, as a normalized percent.",
    )
    change_20d: float | None = Field(
        default=None,
        description="Price change over 20 trading days, as a normalized percent.",
    )
    change_90d: float | None = Field(
        default=None,
        description="Price change over 90 trading days, as a normalized percent.",
    )
    year_return: float | None = Field(
        default=None,
        description="Trailing one-year return, as a normalized percent.",
    )


class WmshareEquityQuoteFetcher(
    Fetcher[WmshareEquityQuoteQueryParams, list[WmshareEquityQuoteData]]
):
    """wmshare Equity Quote Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareEquityQuoteQueryParams:
        """Pass the query through unchanged."""
        return WmshareEquityQuoteQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareEquityQuoteQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the latest snapshot per symbol.

        wmshare exposes one request per symbol here; the snapshot already
        carries the moving averages and multi-window returns, so no extra
        historical call is needed.
        """
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)  # type: ignore[arg-type]
            client = get_client(parsed.market, credentials)
            snapshot = await call(
                client.kline.snapshot,
                parsed.code,
                context=f"kline.snapshot({parsed.canonical})",
            )
            row = require_rows(snapshot, context=f"kline.snapshot({parsed.canonical})")[0]
            rows.append(_to_quote_row(row, parsed.canonical))
        return rows

    @staticmethod
    def transform_data(
        query: WmshareEquityQuoteQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareEquityQuoteData]:
        """Validate the quote rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareEquityQuoteData.model_validate(row) for row in data]


def _to_quote_row(snapshot: dict, symbol: str) -> dict:
    """Map a wmshare snapshot onto OpenBB's quote fields.

    wmshare returns the session close as ``close`` plus the day's percent
    change; ``prev_close`` is derived from those two so downstream consumers
    do not have to reverse the arithmetic themselves.
    """
    row: dict[str, Any] = {
        "symbol": symbol,
        "name": snapshot.get("name"),
        # ``snapshot["industry"]`` is an industry key (``industry.S34``), not a
        # venue; the venue has to be derived from the code.
        "exchange": _exchange_for_symbol(symbol),
        "last_price": snapshot.get("close"),
        "close": snapshot.get("close"),
        "volume": snapshot.get("volume"),
        "change_percent": snapshot.get("percent"),
        "market_cap": snapshot.get("mv"),
        "free_float_market_cap": snapshot.get("mv_free"),
        "ma_20": snapshot.get("ma20"),
        "ma_60": snapshot.get("ma60"),
        "ma_120": snapshot.get("ma120"),
        "change_5d": snapshot.get("chg_5d"),
        "change_20d": snapshot.get("chg_20d"),
        "change_90d": snapshot.get("chg_90d"),
        "year_return": snapshot.get("roi_1y"),
        "asset_type": "equity",
    }

    close = snapshot.get("close")
    percent = snapshot.get("percent")
    if isinstance(close, int | float) and isinstance(percent, int | float) and percent != -1:
        previous = close / (1 + percent)
        row["prev_close"] = round(previous, 6)
        row["change"] = round(close - previous, 6)

    if snapshot.get("kline_date"):
        row["last_timestamp"] = f"{snapshot['kline_date']}T00:00:00"
    return row


def _exchange_for_symbol(canonical: str) -> str | None:
    """Derive the listing venue from a canonical symbol."""
    text = str(canonical or "").strip().upper()
    if text.endswith(".HK"):
        return "HKEX"
    if text.endswith((".SH", ".SS")):
        return "SSE"
    if text.endswith(".SZ"):
        return "SZSE"
    if text.endswith(".BJ"):
        return "BSE"
    return "US" if text else None
