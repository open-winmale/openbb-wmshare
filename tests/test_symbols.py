"""Tests for symbol parsing across OpenBB and wmshare conventions."""

import pytest

from openbb_wmshare.utils.symbols import (
    normalize_index_key,
    parse_symbol,
    resolve_market,
    split_symbols,
)


@pytest.mark.parametrize(
    ("raw", "market", "code", "canonical"),
    [
        ("600519", "cn", "600519", "600519.SH"),
        ("600519.SH", "cn", "600519", "600519.SH"),
        ("600519.SS", "cn", "600519", "600519.SH"),
        ("sh.600519", "cn", "600519", "600519.SH"),
        ("000001.SZ", "cn", "000001", "000001.SZ"),
        ("300750.sz", "cn", "300750", "300750.SZ"),
        ("430047.BJ", "cn", "430047", "430047.BJ"),
        ("688981", "cn", "688981", "688981.SH"),
        ("00700.HK", "hk", "00700", "00700.HK"),
        ("700.HK", "hk", "00700", "00700.HK"),
        ("09988.hk", "hk", "09988", "09988.HK"),
        ("AAPL", "us", "AAPL", "AAPL"),
        ("aapl", "us", "AAPL", "AAPL"),
        ("AAPL.US", "us", "AAPL", "AAPL"),
        ("AAPL.O", "us", "AAPL", "AAPL"),
        ("BRK.B", "us", "BRK_B", "BRK_B"),
    ],
)
def test_parse_symbol(raw, market, code, canonical):
    parsed = parse_symbol(raw)
    assert parsed.market == market
    assert parsed.code == code
    assert parsed.canonical == canonical


def test_bare_numeric_code_uses_shape_then_default_market():
    """A 6-digit code is A-share and 1-5 digits is HK; the default is only a fallback."""
    assert parse_symbol("600519", default_market="hk").market == "cn"
    assert parse_symbol("00700", default_market="cn").market == "hk"
    assert parse_symbol("00700.HK", default_market="cn").market == "hk"


def test_hk_codes_are_zero_padded_to_five_digits():
    assert parse_symbol("700.HK").code == "00700"
    assert parse_symbol("5.HK").code == "00005"


@pytest.mark.parametrize("raw", ["", "   ", "600519.XX", "index.hs300"])
def test_parse_symbol_rejects_bad_input(raw):
    with pytest.raises(ValueError):
        parse_symbol(raw)


def test_resolve_market_matches_parse():
    assert resolve_market("00700.HK") == "hk"
    assert resolve_market("AAPL.US") == "us"


def test_split_symbols_handles_multiple_and_blank_entries():
    assert split_symbols("600519, 000001 ,, AAPL") == ["600519", "000001", "AAPL"]
    assert split_symbols("") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("hs300", "index.hs300"),
        ("HS300", "index.hs300"),
        ("index.hs300", "index.hs300"),
        ("industry.S11", "industry.S11"),
    ],
)
def test_normalize_index_key(raw, expected):
    assert normalize_index_key(raw) == expected
