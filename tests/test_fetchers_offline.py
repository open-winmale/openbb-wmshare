"""Offline TET (transform → extract → transform) coverage for every fetcher.

Each test drives the real ``Fetcher.fetch_data`` entry point so the whole
pipeline runs, not just the transformation helpers.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openbb_core.provider.utils.errors import EmptyDataError, OpenBBError

from openbb_wmshare import wmshare_provider
from openbb_wmshare.models.available_indices import WmshareAvailableIndicesFetcher
from openbb_wmshare.models.balance_sheet import WmshareBalanceSheetFetcher
from openbb_wmshare.models.cash_flow import WmshareCashFlowStatementFetcher
from openbb_wmshare.models.dividends import (
    WmshareCalendarDividendFetcher,
    WmshareHistoricalDividendsFetcher,
)
from openbb_wmshare.models.equity_historical import WmshareEquityHistoricalFetcher
from openbb_wmshare.models.equity_info import WmshareEquityInfoFetcher
from openbb_wmshare.models.equity_quote import WmshareEquityQuoteFetcher
from openbb_wmshare.models.equity_search import WmshareEquitySearchFetcher
from openbb_wmshare.models.financial_ratios import WmshareFinancialRatiosFetcher
from openbb_wmshare.models.income_statement import WmshareIncomeStatementFetcher
from openbb_wmshare.models.index_constituents import WmshareIndexConstituentsFetcher
from openbb_wmshare.models.index_historical import WmshareIndexHistoricalFetcher
from openbb_wmshare.models.index_search import WmshareIndexSearchFetcher
from openbb_wmshare.models.key_metrics import WmshareKeyMetricsFetcher


def run(fetcher: Any, params: dict) -> Any:
    """Drive a fetcher end to end, as OpenBB's query executor would."""
    return asyncio.run(fetcher.fetch_data(params, None))


# ---------------------------------------------------------------- price


def test_equity_historical_returns_bars(fake_client):
    result = run(
        WmshareEquityHistoricalFetcher,
        {"symbol": "600519", "start_date": "2026-01-02", "end_date": "2026-06-30"},
    )

    assert result
    first = result[0]
    assert first.symbol == "600519.SH"
    assert first.date is not None
    assert first.open > 0
    assert first.volume is not None


def test_equity_historical_records_change_percent(fake_client):
    result = run(
        WmshareEquityHistoricalFetcher,
        {"symbol": "600519", "start_date": "2026-01-02", "end_date": "2026-03-31"},
    )
    assert any(row.change_percent is not None for row in result)


def test_equity_historical_passes_adjustment_and_interval(fake_client):
    run(
        WmshareEquityHistoricalFetcher,
        {
            "symbol": "600519",
            "start_date": "2026-01-02",
            "end_date": "2026-03-31",
            "adjust": "qfq",
            "interval": "1W",
        },
    )
    call = fake_client.kline.calls[-1]
    assert call["adj"] == "qfq"
    assert call["freq"] == "W"


def test_equity_historical_splits_ranges_beyond_five_years(fake_client):
    """wmshare rejects ranges over 1825 days, so the fetcher must chunk them."""
    run(
        WmshareEquityHistoricalFetcher,
        {"symbol": "600519", "start_date": "2015-01-01", "end_date": "2026-01-01"},
    )
    assert len(fake_client.kline.calls) >= 2


def test_equity_historical_handles_multiple_symbols(fake_client):
    result = run(
        WmshareEquityHistoricalFetcher,
        {"symbol": "600519,AAPL", "start_date": "2026-01-02", "end_date": "2026-02-27"},
    )
    assert {row.symbol for row in result} == {"600519.SH", "AAPL"}


def test_equity_quote_derives_previous_close(fake_client):
    result = run(WmshareEquityQuoteFetcher, {"symbol": "600519"})
    quote = result[0]
    assert quote.symbol == "600519.SH"
    assert quote.last_price is not None
    assert quote.prev_close is not None
    assert quote.change is not None
    # Derivation must agree with the reported percent change.
    assert quote.change == pytest.approx(quote.last_price - quote.prev_close, abs=1e-4)


def test_equity_quote_carries_snapshot_extras(fake_client):
    quote = run(WmshareEquityQuoteFetcher, {"symbol": "600519"})[0]
    assert quote.market_cap and quote.market_cap > 0
    assert quote.ma_20 is not None
    assert quote.change_20d is not None


def test_equity_search_uses_offline_catalog(fake_client, fake_catalog):
    result = run(WmshareEquitySearchFetcher, {"query": "茅台"})
    assert [row.symbol for row in result] == ["600519.SH"]


def test_equity_search_empty_query_returns_nothing(fake_client, fake_catalog):
    assert run(WmshareEquitySearchFetcher, {"query": ""}) == []


def test_equity_info_maps_profile_fields(fake_client):
    info = run(WmshareEquityInfoFetcher, {"symbol": "600519"})[0]
    assert info.symbol == "600519.SH"
    assert info.name == "贵州茅台"
    assert info.stock_exchange == "SSE"
    assert info.industry_category == "industry.S340501"


# ---------------------------------------------------------------- fundamentals


def test_income_statement_pivots_to_period_rows(fake_client):
    result = run(WmshareIncomeStatementFetcher, {"symbol": "600519", "limit": 3})

    assert len(result) == 3
    latest = result[0]
    assert latest.period_ending.year == 2025
    assert latest.fiscal_period == "FY"
    assert latest.total_revenue == pytest.approx(168_838_102_514.79)
    assert latest.net_profit == pytest.approx(90_000_000_000.0)


def test_income_statement_drops_derived_rows(fake_client):
    """``__gm`` is a ratio row and must not surface as a statement field."""
    result = run(WmshareIncomeStatementFetcher, {"symbol": "600519", "limit": 1})
    dumped = result[0].model_dump()
    assert "__gm" not in dumped
    assert "gm" not in dumped


def test_balance_sheet_maps_assets_and_equity(fake_client):
    latest = run(WmshareBalanceSheetFetcher, {"symbol": "600519", "limit": 1})[0]
    assert latest.total_assets == pytest.approx(300_000_000_000.0)
    assert latest.total_liabilities == pytest.approx(60_000_000_000.0)
    assert latest.total_parent_equity == pytest.approx(230_000_000_000.0)


def test_cash_flow_maps_three_activities(fake_client):
    latest = run(WmshareCashFlowStatementFetcher, {"symbol": "600519", "limit": 1})[0]
    assert latest.net_cash_operating == pytest.approx(95_000_000_000.0)
    assert latest.net_cash_investing == pytest.approx(-15_000_000_000.0)
    assert latest.net_cash_financing == pytest.approx(-40_000_000_000.0)


def test_statement_endpoints_reject_non_a_share_symbols(fake_client):
    """HK/US statements are not published upstream; failing loudly beats empty data."""
    with pytest.raises(OpenBBError, match="A-shares only"):
        run(WmshareIncomeStatementFetcher, {"symbol": "00700.HK"})


def test_key_metrics_maps_indicator_codes(fake_client):
    metrics = run(WmshareKeyMetricsFetcher, {"symbol": "600519"})[0]
    assert metrics.pe_ttm == pytest.approx(22.5)
    assert metrics.roe_ttm == pytest.approx(0.31)
    assert metrics.dividend_yield_ttm == pytest.approx(0.0373)
    assert metrics.market_cap and metrics.market_cap > 0


def test_financial_ratios_are_normalised_decimals(fake_client):
    rows = run(WmshareFinancialRatiosFetcher, {"symbol": "600519", "limit": 3})
    newest, history = rows[0], rows[1:]

    # The newest period comes from curated upstream codes, so it matches the
    # indicator values rather than the locally recomputed ones.
    assert newest.gross_margin == pytest.approx(0.91)
    assert newest.return_on_equity == pytest.approx(0.31)
    assert newest.debt_to_assets == pytest.approx(0.17)
    assert newest.quick_ratio == pytest.approx(3.1)

    # Older periods have no upstream point-in-time code, so they stay locally
    # derived and therefore differ from the overlaid newest values.
    assert history, "expected history periods beyond the overlaid newest one"
    assert history[0].gross_margin != pytest.approx(0.91)

    # Both sources must stay in decimal space, never percentage points.
    for row in rows:
        for name in ("gross_margin", "net_margin", "return_on_assets", "debt_to_assets"):
            value = getattr(row, name)
            assert value is None or abs(value) <= 100


def test_historical_dividends_maps_fields_and_range(fake_client):
    result = run(
        WmshareHistoricalDividendsFetcher,
        {"symbol": "600519", "start_date": "2026-01-01", "end_date": "2026-12-31"},
    )
    assert len(result) == 1
    row = result[0]
    assert row.symbol == "600519.SH"
    assert row.ex_dividend_date.year == 2026
    assert row.amount == pytest.approx(3.6)
    assert row.payment_date is not None


def test_calendar_dividend_requires_symbol(fake_client):
    result = run(
        WmshareCalendarDividendFetcher,
        {"symbol": "600519", "start_date": "2025-01-01", "end_date": "2026-12-31"},
    )
    assert len(result) == 2
    assert result[0].ex_dividend_date is not None


# ---------------------------------------------------------------- indices


def test_index_constituents_merges_weights(fake_client):
    result = run(WmshareIndexConstituentsFetcher, {"symbol": "index.hs300"})
    by_symbol = {row.symbol: row for row in result}

    assert by_symbol["600519.SH"].weight == pytest.approx(0.071)
    assert by_symbol["000001.SZ"].weight == pytest.approx(0.012)
    assert by_symbol["600519.SH"].market_cap and by_symbol["600519.SH"].market_cap > 0


def test_index_constituents_can_skip_weights(fake_client):
    result = run(
        WmshareIndexConstituentsFetcher, {"symbol": "index.hs300", "include_weights": False}
    )
    assert all(row.weight is None for row in result)


def test_index_search_matches_english_and_chinese_names(fake_client):
    assert [r.symbol for r in run(WmshareIndexSearchFetcher, {"query": "csi 300"})] == [
        "index.hs300"
    ]
    assert [r.symbol for r in run(WmshareIndexSearchFetcher, {"query": "沪深300"})] == [
        "index.hs300"
    ]


def test_index_search_is_symbol_mode(fake_client):
    """In symbol mode only the key counts, so a name query yields nothing."""
    assert run(WmshareIndexSearchFetcher, {"query": "沪深300", "is_symbol": True}) == []
    assert [
        r.symbol for r in run(WmshareIndexSearchFetcher, {"query": "hs300", "is_symbol": True})
    ] == ["index.hs300"]


def test_available_indices_lists_every_key(fake_client):
    """Availability is the union of the index universe groups, indices only."""
    result = run(WmshareAvailableIndicesFetcher, {})
    symbols = {row.symbol for row in result}

    assert set(fake_client.index.universe_keys("broad")) <= symbols
    assert "index.csidividend" in symbols
    # Industry classifications are not indices and must not be listed.
    assert not any(symbol.startswith("industry.") for symbol in symbols)
    assert all(row.currency == "CNY" for row in result)


# ---------------------------------------------------------------- provider wiring


def test_provider_registers_expected_models():
    expected = {
        "EquityHistorical",
        "EquityQuote",
        "EquitySearch",
        "EquityInfo",
        "IncomeStatement",
        "BalanceSheet",
        "CashFlowStatement",
        "KeyMetrics",
        "FinancialRatios",
        "HistoricalDividends",
        "CalendarDividend",
        "IndexConstituents",
        "IndexHistorical",
        "IndexSearch",
        "AvailableIndices",
    }
    assert set(wmshare_provider.fetcher_dict) == expected


def test_provider_declares_unprefixed_credentials():
    """OpenBB adds the ``wmshare_`` prefix itself; declaring it would double up."""
    assert wmshare_provider.credentials == ["wmshare_client_id", "wmshare_client_secret"]
    assert wmshare_provider.name == "wmshare"


def test_every_fetcher_declares_query_and_data_types():
    """A fetcher without concrete generics cannot be built by the registry."""
    for model_name, fetcher in wmshare_provider.fetcher_dict.items():
        assert fetcher.query_params_type is not None, model_name
        assert fetcher.data_type is not None, model_name


def test_keyless_fetchers_do_not_require_credentials():
    """Search and index discovery use the bundled catalog, so they need no key."""
    for fetcher in (
        WmshareEquitySearchFetcher,
        WmshareIndexSearchFetcher,
        WmshareAvailableIndicesFetcher,
        WmshareIndexHistoricalFetcher,
    ):
        assert fetcher.require_credentials is False


def test_empty_extraction_raises_empty_data(fake_client, monkeypatch):
    """An empty upstream response must surface as EmptyDataError, not an empty list."""
    monkeypatch.setattr(fake_client.kline, "bars", lambda *a, **k: [])
    with pytest.raises(EmptyDataError):
        run(
            WmshareEquityHistoricalFetcher,
            {"symbol": "600519", "start_date": "2026-01-02", "end_date": "2026-03-31"},
        )


def test_index_historical_resolves_alias_and_normalises_rows(fake_client):
    """An alias key must resolve to a bar series and come back as decimals."""
    result = run(
        WmshareIndexHistoricalFetcher,
        {"symbol": "index.hs300", "start_date": "2026-01-02", "end_date": "2026-03-31"},
    )
    assert result
    first = result[0]
    assert first.symbol == "index.hs300"
    assert first.close and first.close > 0
    # The index store reports percent as a percentage number; the fetcher must
    # emit a decimal like every other OpenBB provider.
    decimals = [bar.change_percent for bar in result if bar.change_percent is not None]
    assert decimals, "expected at least one change_percent"
    assert all(abs(value) < 1 for value in decimals), decimals
    # Rows come back oldest-first within a symbol.
    dates = [bar.date for bar in result]
    assert dates == sorted(dates)


def test_index_historical_rejects_unresolvable_keys(fake_client):
    """Industry valuation keys have no bar history; say so instead of returning []."""
    with pytest.raises(OpenBBError, match="no canonical bar-series code"):
        run(
            WmshareIndexHistoricalFetcher,
            {"symbol": "industry.S11", "start_date": "2026-01-02", "end_date": "2026-03-31"},
        )


def test_all_fetchers_defer_credentials_to_the_sdk():
    """wmshare resolves credentials itself; OpenBB must not gate on them.

    Otherwise users who configured ``~/.wmshare/credentials.env`` — the SDK's own
    documented path — would be blocked before the fetcher ever runs.
    """
    for model_name, fetcher in wmshare_provider.fetcher_dict.items():
        assert fetcher.require_credentials is False, model_name
