"""wmshare Equity Historical model."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.equity_historical import (
    EquityHistoricalData,
    EquityHistoricalQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field, field_validator

from openbb_wmshare.utils import (
    ParsedSymbol,
    call,
    chunk_range,
    get_client,
    parse_symbol,
    resolve_range,
    split_symbols,
)


class WmshareEquityHistoricalQueryParams(EquityHistoricalQueryParams):
    """wmshare Equity Historical Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        "interval": {"choices": ["1d", "1W", "1M"]},
        "adjust": {"choices": ["none", "qfq", "hfq"]},
        "market": {"choices": ["cn", "hk", "us"]},
    }

    interval: Literal["1d", "1W", "1M"] = Field(
        default="1d",
        description="Time interval of the data. wmshare serves daily bars natively; "
        "weekly and monthly bars are pre-aggregated upstream.",
    )
    adjust: Literal["none", "qfq", "hfq"] = Field(
        default="none",
        description="Price adjustment: 'none' (as traded), 'qfq' (forward-adjusted) "
        "or 'hfq' (backward-adjusted).",
    )
    market: Literal["cn", "hk", "us"] = Field(
        default="cn",
        description="Market segment used when a symbol carries no exchange suffix. "
        "Suffixed symbols (600519.SH, 00700.HK) always override this.",
    )

    @field_validator("interval", mode="before", check_fields=False)
    @classmethod
    def _normalize_interval(cls, v: object) -> object:
        """Accept the interval spellings users commonly type."""
        if v is None:
            return "1d"
        if isinstance(v, str):
            token = v.strip().lower()
            mapping = {
                "1d": "1d",
                "d": "1d",
                "day": "1d",
                "daily": "1d",
                "1w": "1W",
                "w": "1W",
                "week": "1W",
                "weekly": "1W",
                "1m": "1M",
                "month": "1M",
                "monthly": "1M",
            }
            if token in mapping:
                return mapping[token]
        return v


class WmshareEquityHistoricalData(EquityHistoricalData):
    """wmshare Equity Historical Data."""

    __alias_dict__ = {"date": "date"}

    change_percent: float | None = Field(
        default=None,
        description="Change from the previous close, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    amount: float | None = Field(
        default=None, description="Turnover (notional value traded) in the listing currency."
    )
    change: float | None = Field(
        default=None, description="Absolute change in price from the previous close."
    )


class WmshareEquityHistoricalFetcher(
    Fetcher[WmshareEquityHistoricalQueryParams, list[WmshareEquityHistoricalData]]
):
    """wmshare Equity Historical Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareEquityHistoricalQueryParams:
        """Validate the query and resolve the default lookback window."""
        transformed = dict(params)
        window = resolve_range(transformed.get("start_date"), transformed.get("end_date"))
        transformed["start_date"] = window.start
        transformed["end_date"] = window.end
        return WmshareEquityHistoricalQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: WmshareEquityHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch bars for every requested symbol, splitting long ranges."""
        symbols = split_symbols(query.symbol)
        if not symbols:
            raise EmptyDataError("No symbols supplied.")

        rows: list[dict] = []
        for raw in symbols:
            parsed = parse_symbol(raw, default_market=query.market)
            rows.extend(
                await _fetch_symbol(
                    parsed,
                    query.start_date,
                    query.end_date,
                    interval=query.interval,
                    adjust=query.adjust,
                    credentials=credentials,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareEquityHistoricalQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareEquityHistoricalData]:
        """Validate the rows and stamp the canonical symbol onto each one."""
        if not data:
            raise EmptyDataError()
        seen: set[tuple[str, str]] = set()
        output: list[WmshareEquityHistoricalData] = []
        for row in data:
            symbol = str(row.get("symbol") or "")
            key = (symbol, str(row.get("date")))
            if key in seen:
                continue
            seen.add(key)
            output.append(WmshareEquityHistoricalData.model_validate(row))
        return output


async def _fetch_symbol(
    parsed: ParsedSymbol,
    start_date: date | None,
    end_date: date | None,
    *,
    interval: str,
    adjust: str,
    credentials: dict[str, str] | None,
) -> list[dict]:
    """Pull one symbol's bars, chunked to respect wmshare's 5-year range cap."""
    window = resolve_range(start_date, end_date)
    client = get_client(parsed.market, credentials)
    adjacency = None if adjust == "none" else adjust
    freq = None if interval == "1d" else interval[1]

    rows: list[dict] = []
    for chunk in chunk_range(window):
        bars = await call(
            client.kline.bars,
            parsed.code,
            adj=adjacency,
            freq=freq,
            begin=chunk.start.isoformat(),
            end=chunk.end.isoformat(),
            context=f"kline.bars({parsed.canonical})",
        )
        rows.extend(_with_symbol(bars, parsed))
    return rows


def _with_symbol(bars: Any, parsed: ParsedSymbol) -> list[dict]:
    """Attach the canonical symbol and normalise field names to OpenBB's schema."""
    if not bars:
        return []
    out: list[dict] = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        row = dict(bar)
        row["symbol"] = parsed.canonical
        if "percent" in row:
            row["change_percent"] = row.pop("percent")
        close = row.get("close")
        change_percent = row.get("change_percent")
        if isinstance(close, int | float) and isinstance(change_percent, int | float):
            previous = close / (1 + change_percent) if change_percent != -1 else None
            if previous is not None:
                row.setdefault("change", round(close - previous, 6))
        out.append(row)
    return out
