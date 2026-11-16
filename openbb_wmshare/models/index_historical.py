"""wmshare Index Historical model.

wmshare does publish index price history, but two upstream quirks make the
naive call wrong (both verified 2026-11-13):

1. **Alias -> canonical code.** The bar store is keyed by canonical codes and
   the alias mapping is *not* the intuitive one: ``index.hs300`` is
   ``399300.INDEX``, **not** ``000300.INDEX`` — the latter is a different index
   whose series is stale. Passing ``index.hs300`` straight to ``kline.bars``
   returns ``[]``. Aliases resolve through
   :mod:`openbb_wmshare.utils.index_canon`.

2. **Equity-shaped volume guard.** Index bars report ``volume`` in a unit that
   trips the SDK's ``volume_amount`` invariant (volume*close/amount ~= 217,
   outside the equity band of [0.4, 2.5]). ``kline.query_at_anchor`` declares no
   such check, so it is used here; it returns raw store rows carrying epoch
   seconds in ``samplingTs`` rather than a ``date`` string, which this module
   normalises.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_historical import (
    IndexHistoricalData,
    IndexHistoricalQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError, OpenBBError
from pydantic import Field, field_validator

from openbb_wmshare.utils import (
    call,
    get_client,
    normalize_index_key,
    resolve_index_canonical,
    resolve_range,
    split_symbols,
)

# ``query_at_anchor`` takes a row count, not a date range, so a long window is
# walked backwards one anchor at a time. One page is capped well below the
# client's 500-row default guard to keep the loop bounded.
PAGE_SIZE = 500
MAX_PAGES = 20
"""20 pages * 500 rows ~= 40 years of trading days; a hard stop against loops."""


class WmshareIndexHistoricalQueryParams(IndexHistoricalQueryParams):
    """wmshare Index Historical Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        "interval": {"choices": ["1d", "1D", "d", "day", "daily"]},
        "market": {"choices": ["cn"]},
    }

    interval: str = Field(
        default="1d",
        description="Time interval of the data. wmshare publishes index bars at daily "
        "frequency only; weekly and monthly index series do not exist upstream, so any "
        "other value is rejected rather than silently served as daily. Accepts "
        "'1d' / '1D' / 'd' / 'day' / 'daily'.",
    )
    market: Literal["cn"] = Field(
        default="cn",
        description="Market segment. wmshare index bar history covers A-share indices only.",
    )

    @field_validator("interval", mode="before", check_fields=False)
    @classmethod
    def _normalize_interval(cls, v: object) -> object:
        """Collapse the daily spellings to '1d'; reject everything else loudly.

        The field is ``str`` rather than ``Literal["1d"]`` on purpose: a Literal
        would reject 'daily'/'D' inside pydantic before this validator runs, so the
        accepted spellings live here and in ``__json_schema_extra__["interval"]``.
        """
        if v is None:
            return "1d"
        if isinstance(v, str):
            token = v.strip().lower()
            if token in {"1d", "d", "day", "daily"}:
                return "1d"
            raise ValueError(
                f"interval {v!r} is not supported: wmshare index bars are daily only "
                "(use '1d'), because upstream publishes no weekly or monthly index series."
            )
        return v


class WmshareIndexHistoricalData(IndexHistoricalData):
    """wmshare Index Historical Data."""

    change_percent: float | None = Field(
        default=None,
        description="Change from the previous close, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    amount: float | None = Field(default=None, description="Turnover (notional value traded).")


class WmshareIndexHistoricalFetcher(
    Fetcher[WmshareIndexHistoricalQueryParams, list[WmshareIndexHistoricalData]]
):
    """wmshare Index Historical Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIndexHistoricalQueryParams:
        """Validate the query and resolve the default window."""
        transformed = dict(params)
        window = resolve_range(transformed.get("start_date"), transformed.get("end_date"))
        transformed["start_date"] = window.start
        transformed["end_date"] = window.end
        return WmshareIndexHistoricalQueryParams(**transformed)

    @staticmethod
    async def aextract_data(
        query: WmshareIndexHistoricalQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch bars per index key, walking backwards from ``end_date``."""
        keys = split_symbols(query.symbol)
        if not keys:
            raise EmptyDataError("No index keys supplied.")

        client = get_client("cn", credentials)
        rows: list[dict] = []
        for raw in keys:
            key = normalize_index_key(raw)
            canonical = resolve_index_canonical(key)
            if canonical is None:
                raise OpenBBError(
                    f"Unknown index key {key!r}: it has no canonical bar-series code. "
                    "Run `obb.index.available(provider='wmshare')` to list resolvable "
                    "keys; industry valuation keys such as 'industry.S11' have no bar "
                    "history."
                )
            rows.extend(
                await _fetch_key(
                    client,
                    key=key,
                    canonical=canonical,
                    start=query.start_date,
                    end=query.end_date,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareIndexHistoricalQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIndexHistoricalData]:
        """Dedupe overlapping pages and validate the rows."""
        if not data:
            raise EmptyDataError()
        seen: set[tuple[str, str]] = set()
        output: list[WmshareIndexHistoricalData] = []
        for row in data:
            key = (str(row.get("symbol") or ""), str(row.get("date")))
            if key in seen:
                continue
            seen.add(key)
            output.append(WmshareIndexHistoricalData.model_validate(row))
        output.sort(key=lambda bar: (str(bar.symbol), str(bar.date)), reverse=False)
        return output


async def _fetch_key(
    client: Any,
    *,
    key: str,
    canonical: str,
    start: dt.date,
    end: dt.date,
) -> list[dict]:
    """Collect bars for one index between ``start`` and ``end``, newest first.

    ``query_at_anchor`` returns the ``limit`` bars ending at (and including) the
    anchor date, so the window is walked backwards: each page's oldest date
    becomes the next anchor, stopping once ``start`` is covered or a page comes
    back empty.
    """
    rows: list[dict] = []
    anchor = end

    for _ in range(MAX_PAGES):
        page = await call(
            client.call,
            "kline.query_at_anchor",
            sym=canonical,
            limit=PAGE_SIZE,
            anchor_date=anchor.isoformat(),
            context=f"kline.query_at_anchor({key})",
        )
        if not page or not isinstance(page, list):
            break

        normalised = [row for row in (_to_bar(item, key) for item in page) if row]
        if not normalised:
            break

        rows.extend(normalised)
        oldest = min(dt.date.fromisoformat(row["date"]) for row in normalised)

        if oldest <= start or len(normalised) < PAGE_SIZE:
            break
        anchor = oldest - dt.timedelta(days=1)

    return [row for row in rows if start <= dt.date.fromisoformat(row["date"]) <= end]


def _to_bar(item: Any, key: str) -> dict | None:
    """Normalise one raw ``index_quote`` row onto OpenBB's schema.

    Two unit differences from equity bars, both verified live against
    ``399300.INDEX``:

    * **``date``** — raw rows carry ``samplingTs`` (epoch seconds) rather than a
      date string.
    * **``percent``** — the index quote store reports a *percentage number*
      (``-0.7798`` means -0.78%), while OpenBB expects a normalized decimal
      (``-0.007798``). Equities already report decimals, so this divide-by-100
      applies to index bars only — do not copy it into the equity fetchers.
    """
    if not isinstance(item, dict):
        return None
    stamp = item.get("samplingTs")
    if not isinstance(stamp, (int, float)):
        return None
    day = dt.datetime.fromtimestamp(stamp, tz=dt.UTC).date()

    percent = item.get("percent")
    change_percent = percent / 100 if isinstance(percent, (int, float)) else None

    # Verify the percentage reading against the price series. If it disagrees
    # the store changed convention; better a null than a 100x-wrong number.
    close, previous = item.get("close"), item.get("prev_close")
    if (
        change_percent is not None
        and isinstance(close, (int, float))
        and isinstance(previous, (int, float))
        and previous
    ):
        expected = close / previous - 1
        if abs(change_percent - expected) > 0.02:
            change_percent = None

    return {
        "symbol": key,
        "date": day.isoformat(),
        "open": item.get("open"),
        "high": item.get("high"),
        "low": item.get("low"),
        "close": item.get("close"),
        "volume": item.get("volume"),
        "amount": item.get("amount"),
        "change_percent": change_percent,
    }
