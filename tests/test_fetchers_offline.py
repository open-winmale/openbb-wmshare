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
from openbb_wmshare.models.calendar_earnings import WmshareCalendarEarningsFetcher
from openbb_wmshare.models.cash_flow import WmshareCashFlowStatementFetcher
from openbb_wmshare.models.dividends import (
    WmshareCalendarDividendFetcher,
    WmshareHistoricalDividendsFetcher,
)
from openbb_wmshare.models.equity_historical import WmshareEquityHistoricalFetcher
from openbb_wmshare.models.equity_info import WmshareEquityInfoFetcher
from openbb_wmshare.models.equity_quote import WmshareEquityQuoteFetcher
from openbb_wmshare.models.equity_search import WmshareEquitySearchFetcher
from openbb_wmshare.models.estimates import (
    WmshareForwardEpsEstimatesFetcher,
    WmshareForwardPeEstimatesFetcher,
)
from openbb_wmshare.models.filings import WmshareCompanyFilingsFetcher
from openbb_wmshare.models.financial_ratios import WmshareFinancialRatiosFetcher
from openbb_wmshare.models.growth import (
    WmshareBalanceSheetGrowthFetcher,
    WmshareCashFlowStatementGrowthFetcher,
    WmshareIncomeStatementGrowthFetcher,
)
from openbb_wmshare.models.income_statement import WmshareIncomeStatementFetcher
from openbb_wmshare.models.index_constituents import WmshareIndexConstituentsFetcher
from openbb_wmshare.models.index_historical import WmshareIndexHistoricalFetcher
from openbb_wmshare.models.index_search import WmshareIndexSearchFetcher
from openbb_wmshare.models.index_snapshots import WmshareIndexSnapshotsFetcher
from openbb_wmshare.models.index_valuation_trend import WmshareIndexValuationTrendFetcher
from openbb_wmshare.models.insider_trading import WmshareInsiderTradingFetcher
from openbb_wmshare.models.institutional_ownership import WmshareInstitutionalOwnershipFetcher
from openbb_wmshare.models.key_executives import WmshareKeyExecutivesFetcher
from openbb_wmshare.models.key_metrics import WmshareKeyMetricsFetcher
from openbb_wmshare.models.market_extras import (
    WmshareCbondBoardFetcher,
    WmshareMarginFetcher,
    WmshareMoneyflowFetcher,
)
from openbb_wmshare.models.market_movers import (
    WmshareEquityGainersFetcher,
    WmshareEquityLosersFetcher,
)
from openbb_wmshare.models.screener_query import WmshareScreenerFetcher
from openbb_wmshare.models.segments_revenue import (
    WmshareRevenueBusinessLineFetcher,
    WmshareRevenueGeographicFetcher,
)
from openbb_wmshare.models.share_statistics import WmshareShareStatisticsFetcher
from openbb_wmshare.models.trailing_dividend_yield import WmshareTrailingDivYieldFetcher


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
        "IndexSnapshots",
        "EquityGainers",
        "EquityLosers",
        "TrailingDividendYield",
        "CompanyFilings",
        "KeyExecutives",
        "ShareStatistics",
        "InstitutionalOwnership",
        "InsiderTrading",
        "RevenueBusinessLine",
        "RevenueGeographic",
        "CalendarEarnings",
        "ForwardEpsEstimates",
        "ForwardPeEstimates",
        "IncomeStatementGrowth",
        "BalanceSheetGrowth",
        "CashFlowStatementGrowth",
        "WmshareScreener",
        "WmshareIndexValuationTrend",
        "WmshareMoneyflow",
        "WmshareMargin",
        "WmshareCbondBoard",
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


# ---------------------------------------------------------------- phase-1 batch


def test_trailing_dividend_yield_maps_ttm_value(fake_client):
    result = run(WmshareTrailingDivYieldFetcher, {"symbol": "600519"})

    row = result[0]
    assert row.symbol == "600519.SH"
    assert row.trailing_dividend_yield == pytest.approx(0.0373)
    assert row.date is not None
    assert row.currency == "CNY"


def test_trailing_dividend_yield_multiple_markets(fake_client):
    result = run(WmshareTrailingDivYieldFetcher, {"symbol": "600519,00700.HK"})
    assert {row.symbol for row in result} == {"600519.SH", "00700.HK"}


def test_index_snapshots_rekey_to_alias(fake_client):
    result = run(WmshareIndexSnapshotsFetcher, {})

    assert result
    by_symbol = {row.symbol: row for row in result}
    # The canon snapshot maps hs300 -> 399300.INDEX; output must speak the
    # user-facing key, not the upstream canonical code.
    assert "index.hs300" in by_symbol
    snap = by_symbol["index.hs300"]
    assert snap.close is not None
    assert snap.change is not None
    # prev_close derived from close - change so consumers need no arithmetic.
    assert snap.prev_close == pytest.approx(snap.close - snap.change, abs=1e-4)
    assert snap.turnover_rate is not None


def test_gainers_descending_and_losers_ascending(fake_client):
    gainers = run(WmshareEquityGainersFetcher, {"limit": 3})
    losers = run(WmshareEquityLosersFetcher, {"limit": 3})

    assert gainers[0].symbol == "300528.SZ"  # percent 0.2001, the largest
    assert losers[0].symbol == "000001.SZ"  # percent -0.0198, the smallest
    assert gainers[0].change_percent == pytest.approx(0.2001)
    # Upstream publishes percent only; price/change must stay unset, not invented.
    assert gainers[0].price is None
    assert gainers[0].change is None
    assert losers[0].change_percent == pytest.approx(-0.0198)


def test_movers_symbols_are_canonical(fake_client):
    result = run(WmshareEquityGainersFetcher, {"limit": 3})
    assert all("." in row.symbol for row in result)


def test_equity_info_resolves_industry_name(fake_client):
    info = run(WmshareEquityInfoFetcher, {"symbol": "600519"})[0]
    assert info.industry_category == "industry.S340501"
    assert info.industry_name == "白酒"


def test_equity_info_industry_name_missing_key_is_none(fake_client, monkeypatch):
    """No industry key → the name lookup makes no request and resolves to None."""
    real_call = fake_client.call

    def guarded(name, /, **kwargs):
        if name == "stocks.industry_members":
            raise AssertionError("industry_name lookup must not fire without a key")
        return real_call(name, **kwargs)

    monkeypatch.setattr(fake_client, "call", guarded)
    monkeypatch.setattr(
        fake_client.indicator,
        "metrics",
        lambda symbol, codes, fut_symbol=None: {"$NAME": "无名氏"},
    )
    info = run(WmshareEquityInfoFetcher, {"symbol": "600519"})[0]
    assert info.industry_category is None
    assert info.industry_name is None
    assert info.name == "无名氏"


# ---------------------------------------------------------------- batch 1a


def test_company_filings_maps_notice_and_url(fake_client):
    result = run(WmshareCompanyFilingsFetcher, {"symbol": "600519", "limit": 10})

    # The link-less row must be skipped: report_url is required upstream.
    assert len(result) == 1
    row = result[0]
    assert row.symbol == "600519.SH"
    assert row.report_type == "年报"
    assert row.report_url.startswith("https://")


def test_company_filings_kind_filter(fake_client):
    result = run(WmshareCompanyFilingsFetcher, {"symbol": "600519", "kind": "annual"})
    assert all(row.report_type == "年报" for row in result)


def test_key_executives_maps_roster(fake_client):
    result = run(WmshareKeyExecutivesFetcher, {"symbol": "600519"})

    assert len(result) == 2
    chair = result[0]
    assert chair.name == "陈华"
    assert "董事长" in chair.title
    assert chair.pay is None  # salary missing upstream, never invented
    assert chair.high_degree == "硕士"
    paid = result[1]
    assert paid.pay == 1200000.0
    assert paid.currency_pay == "CNY"


def test_share_statistics_derives_free_float(fake_client):
    row = run(WmshareShareStatisticsFetcher, {"symbol": "600519"})[0]

    assert row.symbol == "600519.SH"
    assert row.outstanding_shares == 1250081601
    assert row.float_shares == 1250081601
    assert row.free_float == pytest.approx(1.0)


def test_institutional_ownership_skips_rows_without_date(fake_client):
    result = run(WmshareInstitutionalOwnershipFetcher, {"symbol": "600519", "limit": 2})

    assert len(result) == 1  # the date-less fund row is skipped
    row = result[0]
    assert row.date is not None
    assert row.holder_name == "中国贵州茅台酒厂(集团)有限责任公司"
    assert row.shares == 681282935
    assert row.total_shares_ratio == pytest.approx(0.5449907706)


def test_insider_trading_maps_latest_change(fake_client):
    row = run(WmshareInsiderTradingFetcher, {"symbol": "600519"})[0]

    assert row.symbol == "600519.SH"
    assert row.owner_name == "万波"
    assert row.securities_transacted == -700
    # sign of change_num drives A/D, nothing else is inferred
    assert row.acquisition_or_disposition == "D"
    assert row.transaction_price == 725.92
    assert row.trade_way == "二级市场买卖"


# ---------------------------------------------------------------- batch 1b


def test_revenue_per_segment_stamps_disclosure_period(fake_client):
    result = run(WmshareRevenueBusinessLineFetcher, {"symbol": "600519", "dim": "product"})

    assert len(result) == 2
    top = result[0]
    assert top.business_line == "茅台酒"
    assert top.revenue == pytest.approx(125_000_000_000.0)
    # period comes from segments.periods().clean_last = 2026:Q3
    assert top.period_ending.year == 2026 and top.period_ending.month == 9
    assert top.margin == pytest.approx(0.88)


def test_revenue_per_geography_uses_clean_buckets(fake_client):
    result = run(WmshareRevenueGeographicFetcher, {"symbol": "600519"})

    by_region = {row.region: row for row in result}
    assert set(by_region) == {"domestic", "overseas"}
    assert by_region["domestic"].revenue == pytest.approx(129_252_586_100)
    assert by_region["overseas"].yoy == pytest.approx(-0.578)
    # period from the region payload's own report_sas (2026:Q3)
    assert by_region["domestic"].period_ending.month == 9


def test_calendar_earnings_maps_appointment_date(fake_client):
    result = run(WmshareCalendarEarningsFetcher, {"symbol": "600519"})

    assert len(result) == 2
    published = result[0]
    # calendar date is the appointment, falling back to the actual date
    assert str(published.report_date) == "2026-10-31"
    assert published.fiscal_period_end == "2026-09-30"
    upcoming = result[1]
    assert str(upcoming.report_date) == "2026-04-25"
    assert upcoming.actual_publish_date is None
    assert published.eps_previous is None and published.eps_consensus is None


def test_forward_eps_keeps_institutions_and_aggregate(fake_client):
    result = run(WmshareForwardEpsEstimatesFetcher, {"symbol": "600519"})

    assert len(result) == 2
    agg = result[0]
    assert agg.org_name == "近六月平均"
    assert agg.mean == pytest.approx(65.85)  # year-1 estimate
    assert agg.eps4 == pytest.approx(75.18)
    # no distribution upstream: low/high/median stay unset, never invented
    assert agg.low_estimate is None and agg.high_estimate is None
    assert result[1].rating == "买入"


def test_forward_pe_maps_year_series(fake_client):
    result = run(WmshareForwardPeEstimatesFetcher, {"symbol": "600519"})

    assert len(result) == 2
    agg = result[0]
    assert agg.year1 == pytest.approx(19.11)
    assert agg.year4 == pytest.approx(16.74)
    assert agg.year5 is None  # upstream publishes 4 predicted years only


# ---------------------------------------------------------------- batch 1c


def test_income_growth_yoy_against_prior_period(fake_client):
    result = run(WmshareIncomeStatementGrowthFetcher, {"symbol": "600519", "limit": 3})

    assert len(result) == 3
    latest = result[0]
    assert latest.period_ending.year == 2025
    # growth must equal the ratio implied by the canned statement fixture
    expected = 168_838_102_514.79 / 170_899_152_276.34 - 1
    assert latest.total_revenue_growth == pytest.approx(expected, rel=1e-9)
    assert latest.net_profit_growth == pytest.approx(
        90_000_000_000.0 / 88_000_000_000.0 - 1, rel=1e-9
    )


def test_income_growth_none_without_base(fake_client):
    """The oldest period has no prior year in the canned window → None, not 0."""
    result = run(WmshareIncomeStatementGrowthFetcher, {"symbol": "600519", "limit": 3})
    oldest = result[-1]
    assert oldest.total_revenue_growth is None


def test_balance_growth_fields(fake_client):
    result = run(WmshareBalanceSheetGrowthFetcher, {"symbol": "600519", "limit": 3})
    latest = result[0]
    assert latest.total_assets_growth is not None
    assert abs(latest.total_assets_growth) < 10  # decimal space


def test_cashflow_growth_fields(fake_client):
    result = run(WmshareCashFlowStatementGrowthFetcher, {"symbol": "600519", "limit": 2})
    latest = result[0]
    assert latest.net_cash_operating_growth is not None


# ---------------------------------------------------------------- batch 1d


def test_screener_rows_and_hit_count(fake_client):
    result = run(
        WmshareScreenerFetcher,
        {"where": "$BONUS_RATE_3Y_AVG_LAST > 0.03 && $ROE_TTM_LAST > 0.15"},
    )

    rows = result.result if hasattr(result, "result") else result
    assert rows[0].symbol == "900948.SH"
    assert rows[0].name == "伊泰B股"
    # $codes named in the expression ride along as extras
    dumped = rows[0].model_dump()
    assert dumped["$ROE_TTM_LAST"] == pytest.approx(0.1631)
    # the true whole-market hit count rides the metadata, not the row count
    if hasattr(result, "metadata"):
        assert result.metadata["count"] == 108


def test_index_valuation_trend_attaches_percentiles(fake_client):
    fake_client.index.trend = lambda key, window="5y": {
        "ok": True,
        "key": key,
        "as_of": "2026-11-12",
        "density": "weekly",
        "points": [
            {"date": "2026-11-12", "pe": 13.39, "pb": 1.24},
            {"date": "2026-11-05", "pe": 13.10, "pb": 1.21},
        ],
        "pe_pct": 0.7548,
        "pb_pct": 0.5204,
        "pct": {
            "pe": {"p3": 0.30, "p5": 0.7548, "p10": None},
            "pb": {"p3": 0.48, "p5": 0.5204, "p10": None},
        },
    }

    result = run(WmshareIndexValuationTrendFetcher, {"key": "index.hs300", "window": "5y"})

    assert len(result) == 2
    row = result[0]
    assert row.symbol == "index.hs300"
    assert row.pe == pytest.approx(13.39)
    assert row.pe_pct_window == pytest.approx(0.7548)  # p5 of the 5y window
    assert row.pb_pct_window == pytest.approx(0.5204)


def test_moneyflow_maps_tiers(fake_client):
    result = run(WmshareMoneyflowFetcher, {"symbol": "600519", "n": 2})

    row = result[0]
    assert row.symbol == "600519.SH"
    assert row.net_mf == pytest.approx(328_649_400)
    assert row.elg_net == pytest.approx(-7_507_400)


def test_margin_maps_balances_and_strips_display_fields(fake_client):
    row = run(WmshareMarginFetcher, {"symbol": "600519"})[0]

    assert row.symbol == "600519.SH"
    assert row.fin_balance == pytest.approx(15_214_545_810)
    assert row.loan_sell_vol == 7900
    dumped = row.model_dump()
    assert "secucode" not in dumped  # display-only upstream fields dropped


def test_cbond_board_maps_camel_keys(fake_client):
    result = run(WmshareCbondBoardFetcher, {})

    row = result[0]
    assert row.bond_code == "111027"
    assert row.bond_name == "百龙转债"
    assert row.convert_price == pytest.approx(19.42)
    assert row.stock_code == "000829"
