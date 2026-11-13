"""Tests for range resolution and chunking against wmshare's 5-year cap."""

import itertools
from datetime import date, timedelta

import pytest

from openbb_wmshare.utils.dates import (
    DEFAULT_LOOKBACK_DAYS,
    MAX_RANGE_DAYS,
    DateRange,
    chunk_range,
    lookback_days,
    resolve_range,
    to_date,
)

TODAY = date(2026, 11, 13)


def test_defaults_to_trailing_year():
    window = resolve_range(today=TODAY)
    assert window.end == TODAY
    assert window.start == TODAY - timedelta(days=DEFAULT_LOOKBACK_DAYS)


def test_only_start_given_extends_to_today():
    window = resolve_range(date(2020, 1, 1), today=TODAY)
    assert window == DateRange(date(2020, 1, 1), TODAY)


def test_only_end_given_looks_back_one_year():
    window = resolve_range(None, date(2020, 6, 30), today=TODAY)
    assert window == DateRange(date(2019, 7, 1), date(2020, 6, 30))


def test_reversed_range_is_rejected():
    with pytest.raises(ValueError, match="must not be later"):
        resolve_range(date(2024, 1, 1), date(2023, 1, 1), today=TODAY)


def test_iso_strings_are_accepted():
    window = resolve_range("2024-01-01", "2024-12-31", today=TODAY)
    assert window == DateRange(date(2024, 1, 1), date(2024, 12, 31))


def test_invalid_date_raises():
    with pytest.raises(ValueError):
        to_date("not-a-date")


def test_chunks_never_exceed_the_upstream_cap():
    window = DateRange(date(2010, 1, 1), date(2026, 1, 1))
    chunks = list(chunk_range(window))
    assert chunks[0].start == window.start
    assert chunks[-1].end == window.end
    for chunk in chunks:
        assert (chunk.end - chunk.start).days <= MAX_RANGE_DAYS
    # Windows must tile the range without gaps or overlaps.
    for previous, following in itertools.pairwise(chunks):
        assert following.start == previous.end + timedelta(days=1)


def test_chunk_returns_single_window_when_within_limit():
    window = DateRange(date(2025, 1, 1), date(2025, 6, 1))
    assert list(chunk_range(window)) == [window]


def test_single_day_range_yields_one_chunk():
    window = DateRange(date(2025, 1, 1), date(2025, 1, 1))
    assert list(chunk_range(window)) == [window]


@pytest.mark.parametrize(("token", "days"), [("3y", 1095), ("6m", 180), ("90", 90), (30, 30)])
def test_lookback_days(token, days):
    assert lookback_days(token) == days


def test_lookback_days_rejects_unknown_token():
    with pytest.raises(ValueError):
        lookback_days("42y")
