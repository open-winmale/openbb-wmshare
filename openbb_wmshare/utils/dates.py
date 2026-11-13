"""Date handling for wmshare's hard request limits.

Two upstream limits shape every historical query:

* A single ``begin``/``end`` range may not exceed 1825 days (5 years); see
  ``MAX_RANGE_DAYS`` in the SDK's ``api/__init__.py``.
* A single request returns at most 10,000 rows, and the client defaults to
  ``max_limit=500`` rows per call.

So a long OpenBB range has to be split into windows and stitched back together.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import NamedTuple

MAX_RANGE_DAYS = 1825
"""Largest span wmshare accepts for one ``begin``/``end`` pair."""

DEFAULT_LOOKBACK_DAYS = 365
"""Default window when the caller supplies no ``start_date``."""


class DateRange(NamedTuple):
    """A half-open-by-day inclusive window that fits wmshare's limits."""

    start: date
    end: date


def to_date(value: object) -> date | None:
    """Coerce OpenBB's date-ish inputs (``date``/``datetime``/ISO string) to a date."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Invalid date {value!r}; expected YYYY-MM-DD.") from exc


def resolve_range(
    start_date: object = None,
    end_date: object = None,
    *,
    today: date | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> DateRange:
    """Fill in defaults and validate ordering.

    Mirrors openbb-tushare's default of a one-year trailing window so that a
    bare ``historical(symbol=...)`` does not silently pull decades of data.
    """
    current = today or date.today()
    start = to_date(start_date)
    end = to_date(end_date)

    if start is None and end is None:
        return DateRange(current - timedelta(days=lookback_days), current)
    if start is None:
        return DateRange(end - timedelta(days=lookback_days), end)  # type: ignore[operator]
    if end is None:
        return DateRange(start, max(start, current))
    if start > end:
        raise ValueError(f"start_date {start} must not be later than end_date {end}.")
    return DateRange(start, end)


def chunk_range(window: DateRange, max_days: int = MAX_RANGE_DAYS) -> Iterator[DateRange]:
    """Yield consecutive windows of at most ``max_days`` days, inclusive of both ends.

    ``max_days`` counts the span between the endpoints, matching wmshare's
    ``(end - begin).days`` check, so a chunk is safe when ``end - start <= max_days``.
    """
    if max_days < 1:
        raise ValueError("max_days must be positive.")
    if window.start > window.end:
        raise ValueError("window.start must not be later than window.end.")

    cursor = window.start
    while cursor <= window.end:
        chunk_end = min(cursor + timedelta(days=max_days), window.end)
        yield DateRange(cursor, chunk_end)
        if chunk_end == window.end:
            return
        cursor = chunk_end + timedelta(days=1)


def lookback_days(window: str | int) -> int:
    """Translate wmshare window tokens (``"3y"``, ``"6m"``, ``90``) into days."""
    if isinstance(window, int) or str(window).isdigit():
        return int(window)
    token = str(window).strip().lower()
    table = {
        "1w": 7,
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "1y": 365,
        "2y": 730,
        "3y": 1095,
        "5y": 1825,
    }
    try:
        return table[token]
    except KeyError:
        raise ValueError(f"Unsupported window {window!r}.") from None
