"""Live provider tests against the real wmshare API.

Skipped when no credentials are configured, so the default test run stays
offline and deterministic.
"""

from __future__ import annotations

import pytest
from openbb_core.provider.utils.errors import EmptyDataError, OpenBBError

pytestmark = pytest.mark.integration


def _has_credentials() -> bool:
    """Detect credentials the way the SDK does: env vars or the credentials file."""
    try:
        import wmshare

        wmshare.Client.from_env()
        return True
    except Exception:
        return False


requires_credentials = pytest.mark.skipif(
    not _has_credentials(), reason="wmshare credentials not configured"
)


def call(model: str, **params):
    """Invoke a provider model through OpenBB's real query pipeline."""
    from openbb import obb

    command = {
        "EquityHistorical": obb.equity.price.historical,
        "EquityQuote": obb.equity.price.quote,
        "EquitySearch": obb.equity.search,
        "EquityInfo": obb.equity.profile,
        "IncomeStatement": obb.equity.fundamental.income,
        "BalanceSheet": obb.equity.fundamental.balance,
        "CashFlowStatement": obb.equity.fundamental.cash,
        "KeyMetrics": obb.equity.fundamental.metrics,
        "FinancialRatios": obb.equity.fundamental.ratios,
        "HistoricalDividends": obb.equity.fundamental.dividends,
        "CalendarDividend": obb.equity.calendar.dividend,
        "IndexConstituents": obb.index.constituents,
        "IndexHistorical": obb.index.price.historical,
        "IndexSearch": obb.index.search,
        "AvailableIndices": obb.index.available,
        "IndexSnapshots": obb.index.snapshots,
        "EquityGainers": obb.equity.discovery.gainers,
        "EquityLosers": obb.equity.discovery.losers,
        "TrailingDividendYield": obb.equity.fundamental.trailing_dividend_yield,
        "CompanyFilings": obb.equity.fundamental.filings,
        "KeyExecutives": obb.equity.fundamental.management,
        "ShareStatistics": obb.equity.ownership.share_statistics,
        "InstitutionalOwnership": obb.equity.ownership.institutional,
        "InsiderTrading": obb.equity.ownership.insider_trading,
        "RevenueBusinessLine": obb.equity.fundamental.revenue_per_segment,
        "RevenueGeographic": obb.equity.fundamental.revenue_per_geography,
        "CalendarEarnings": obb.equity.calendar.earnings,
        "ForwardEpsEstimates": obb.equity.estimates.forward_eps,
        "ForwardPeEstimates": obb.equity.estimates.forward_pe,
        "IncomeStatementGrowth": obb.equity.fundamental.income_growth,
        "BalanceSheetGrowth": obb.equity.fundamental.balance_growth,
        "CashFlowStatementGrowth": obb.equity.fundamental.cash_growth,
    }[model]
    return command(**params, provider="wmshare")


@requires_credentials
@pytest.mark.parametrize(
    ("symbol", "market"),
    [("600519.SH", "cn"), ("00700.HK", "hk"), ("AAPL", "us")],
)
def test_historical_across_markets(symbol, market):
    result = call(
        "EquityHistorical", symbol=symbol, start_date="2026-10-01", end_date="2026-10-30"
    ).results

    assert result, f"no bars for {symbol}"
    assert result[0].open > 0
    assert result[0].date is not None


@requires_credentials
def test_historical_adjustment_changes_earlier_prices():
    """Forward adjustment is anchored on the latest bar, so only history moves.

    Comparing the newest bar would be wrong: qfq leaves today's price untouched
    and rescales everything before it.
    """
    raw = call(
        "EquityHistorical",
        symbol="600519.SH",
        start_date="2026-01-05",
        end_date="2026-10-30",
        adjust="none",
    ).results
    adjusted = call(
        "EquityHistorical",
        symbol="600519.SH",
        start_date="2026-01-05",
        end_date="2026-10-30",
        adjust="qfq",
    ).results

    assert raw and adjusted
    assert len(raw) == len(adjusted)

    by_date = {row.date: row.close for row in adjusted}
    differing = [
        row for row in raw if by_date.get(row.date) is not None and by_date[row.date] != row.close
    ]
    assert differing, "qfq returned prices identical to unadjusted across the whole range"


@requires_credentials
def test_quote_derives_previous_close():
    quote = call("EquityQuote", symbol="600519.SH").results[0]

    assert quote.last_price
    assert quote.prev_close
    assert quote.change == pytest.approx(quote.last_price - quote.prev_close, abs=1e-3)


@requires_credentials
def test_income_statement_has_annual_periods():
    result = call("IncomeStatement", symbol="600519.SH", limit=3).results

    assert len(result) == 3
    assert all(row.fiscal_period == "FY" for row in result)
    assert all(row.total_revenue for row in result)


@requires_credentials
def test_ratios_stay_in_decimal_space():
    result = call("FinancialRatios", symbol="600519.SH", limit=2).results

    for row in result:
        for name in ("gross_margin", "net_margin", "debt_to_assets", "return_on_assets"):
            value = getattr(row, name)
            assert value is None or abs(value) <= 100, f"{name} looks like a percentage"


@requires_credentials
def test_metrics_align_with_ratios():
    """Both endpoints describe the same company, so ROE direction must agree."""
    metrics = call("KeyMetrics", symbol="600519.SH").results[0]
    ratios = call("FinancialRatios", symbol="600519.SH", limit=1).results[0]

    if metrics.roe_ttm is not None and ratios.return_on_equity is not None:
        assert metrics.roe_ttm > 0 and ratios.return_on_equity > 0


@requires_credentials
def test_hk_dividends_are_returned():
    result = call("HistoricalDividends", symbol="00700.HK").results
    assert result
    assert all(row.symbol == "00700.HK" for row in result)


def _unified_deployed() -> bool:
    """One-shot probe: does the gateway's statement entry serve hk/us yet?

    The script-repo commit that turns ``rptdom.statement`` into the all-market
    entry (hk/us wide-table pivot + quarter mode) is local until the deploy
    gate; these tests skip (rather than fail) until then.
    """
    try:
        import wmshare

        hk = wmshare.Client.from_env(market="hk")
        rows = hk.statements.income("00700", years=1)
        return bool(rows)
    except Exception:
        return False


_unified_ready = pytest.mark.skipif(
    not _unified_deployed(),
    reason="script repo unified statement entry not deployed yet (deploy gate)",
)


@_unified_ready
@pytest.mark.parametrize(
    ("symbol", "kind"),
    [("AAPL", "income"), ("00700.HK", "income"), ("AAPL", "balance"), ("AAPL", "cash")],
)
def test_hk_us_statements_via_unified_entry(symbol, kind):
    result = call(
        {"income": "IncomeStatement", "balance": "BalanceSheet", "cash": "CashFlowStatement"}[kind],
        symbol=symbol,
        limit=2,
    ).results

    assert result
    latest = result[0]
    assert latest.period_ending is not None
    assert latest.fiscal_year >= 2024
    assert latest.currency in ("USD", "HKD")


@_unified_ready
def test_cn_quarterly_reports():
    """period=quarter serves quarterly reports (annual stays the default)."""
    result = call("IncomeStatement", symbol="600519.SH", limit=4, period="quarter").results

    assert result
    assert any(row.fiscal_period in ("Q1", "Q2", "Q3", "Q4") for row in result)


@requires_credentials
def test_index_constituents_carry_weights():
    result = call("IndexConstituents", symbol="index.hs300").results

    assert result
    weighted = [row for row in result if row.weight is not None]
    assert weighted, "no constituent carried a weight"
    assert all(0 < row.weight <= 1 for row in weighted)


def test_equity_search_needs_no_credentials():
    """The offline symbol table works even with no credentials configured."""
    result = call("EquitySearch", query="茅台").results
    assert any(row.symbol == "600519.SH" for row in result)


def test_index_available_needs_no_credentials():
    result = call("AvailableIndices").results
    assert result
    assert all(row.symbol.startswith("index.") for row in result)


def test_index_historical_serves_real_bars():
    """The alias key must resolve to a fresh, non-empty series."""
    result = call(
        "IndexHistorical",
        symbol="index.hs300",
        start_date="2026-09-01",
        end_date="2026-11-13",
    ).results
    assert result, "index history returned nothing"
    assert all(row.symbol == "index.hs300" for row in result)
    assert all(row.close and row.close > 0 for row in result)
    # Newest bar must be recent; a stale series here means the alias resolved to
    # the wrong index (000300.INDEX is stale since 2024-12-06).
    latest = max(row.date for row in result)
    assert str(latest) >= "2026-09-01"


def test_index_bars_are_reachable_via_canonical_code():
    """Upstream proof for the alias mapping, independent of the provider.

    ``index.hs300`` maps to ``399300.INDEX`` (NOT ``000300.INDEX``, which is a
    different index with a stale series).
    """
    from wmshare import Client  # lazy: keeps the module importable without wmshare

    client = Client.from_env(market="cn")
    bars = client.kline.bars("399300.INDEX", n=5, _raw=True)
    assert bars, "index history disappeared upstream; update docs/GAPS.md"
    assert all("close" in bar for bar in bars)


def test_us_profile_does_not_fail_on_missing_style_industry():
    """``$STYLE_INDUSTRY`` is undefined for US listings.

    The SDK's ``info.profile`` bundles all five codes into one eval, so that one
    missing code used to fail the request with HTTP 400. The fetcher must omit
    it and still return the rest of the profile.
    """
    result = call("EquityInfo", symbol="AAPL", market="us").results
    assert result
    profile = result[0]
    assert profile.name
    assert profile.style_industry is None


def test_missing_credentials_surface_as_auth_error(monkeypatch):
    """Without credentials the SDK's AuthError must reach the caller."""
    for key in (
        "WMSHARE_CLIENT_ID",
        "WMSHARE_CLIENT_SECRET",
        "OPEN_PLATFORM_CLIENT_ID",
        "OPEN_PLATFORM_CLIENT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WMSHARE_CREDENTIALS", "/nonexistent/credentials.env")

    from openbb_wmshare.utils.client import clear_client_cache

    clear_client_cache()
    try:
        with pytest.raises((OpenBBError, EmptyDataError)):
            call("EquityQuote", symbol="600519.SH")
    finally:
        clear_client_cache()


# ---------------------------------------------------------------- phase-1 batch


@requires_credentials
def test_trailing_dividend_yield_is_live_value():
    result = call("TrailingDividendYield", symbol="600519.SH").results

    assert len(result) == 1
    row = result[0]
    assert row.symbol == "600519.SH"
    assert 0 < row.trailing_dividend_yield < 1
    assert row.date is not None


@requires_credentials
def test_index_snapshots_cover_the_universe():
    result = call("IndexSnapshots").results

    assert len(result) >= 10
    symbols = {row.symbol for row in result}
    assert "index.hs300" in symbols
    hs300 = next(row for row in result if row.symbol == "index.hs300")
    assert hs300.close and hs300.close > 0
    assert hs300.currency == "CNY"
    # prev_close is derived from close - change in the provider.
    if hs300.change is not None:
        assert hs300.prev_close == pytest.approx(hs300.close - hs300.change, abs=1e-3)


@requires_credentials
def test_gainers_descend_and_losers_ascend():
    gainers = call("EquityGainers", limit=5).results
    losers = call("EquityLosers", limit=5).results

    assert len(gainers) == 5 and len(losers) == 5
    assert gainers[0].change_percent >= gainers[-1].change_percent
    assert losers[0].change_percent <= losers[-1].change_percent
    assert gainers[0].change_percent > 0 > losers[0].change_percent
    # Upstream ranking carries percent only; provider must leave price/change unset.
    assert gainers[0].price is None and gainers[0].change is None


@requires_credentials
def test_profile_resolves_industry_name_for_us_and_cn():
    """$INDUSTRY_CUR works on US Y-codes; the name comes from industry_members."""
    cn = call("EquityInfo", symbol="600519.SH").results[0]
    assert cn.industry_name, "cn industry_name missing"

    us = call("EquityInfo", symbol="AAPL").results[0]
    assert us.industry_category == "industry.Y100103"
    assert us.industry_name == "Consumer Electronics"


# ---------------------------------------------------------------- batch 1a


@requires_credentials
def test_filings_carry_report_urls():
    result = call("CompanyFilings", symbol="600519.SH", limit=10).results

    assert result
    assert all(row.report_url for row in result), "url-less rows must be skipped"
    assert any(row.report_type == "年报" for row in result)


@requires_credentials
def test_key_executives_roster():
    result = call("KeyExecutives", symbol="600519.SH").results

    assert len(result) >= 5
    assert all(row.name and row.title for row in result)


@requires_credentials
def test_share_statistics_free_float_is_fraction():
    row = call("ShareStatistics", symbol="600519.SH").results[0]

    assert row.outstanding_shares and row.outstanding_shares > 0
    assert row.free_float is None or 0 < row.free_float <= 1


@requires_credentials
def test_institutional_ownership_rows_dated():
    result = call("InstitutionalOwnership", symbol="600519.SH", limit=10).results

    assert result
    assert all(row.date is not None for row in result)


@requires_credentials
def test_insider_trading_latest_row_only():
    result = call("InsiderTrading", symbol="600519.SH").results

    assert len(result) <= 1


# ---------------------------------------------------------------- batch 1b


@requires_credentials
def test_revenue_per_segment_business_dim():
    result = call("RevenueBusinessLine", symbol="600519.SH", dim="business").results

    assert result
    assert all(row.revenue > 0 for row in result)
    assert all(row.period_ending is not None for row in result)


@requires_credentials
def test_revenue_per_geography_two_buckets():
    result = call("RevenueGeographic", symbol="600519.SH").results

    regions = {row.region for row in result}
    assert regions == {"domestic", "overseas"}
    assert all(row.revenue > 0 for row in result)


@requires_credentials
def test_calendar_earnings_maps_appointments():
    result = call("CalendarEarnings", symbol="600519.SH").results

    assert result
    assert all(row.report_date is not None for row in result)
    assert all(row.fiscal_period_end for row in result)


@requires_credentials
def test_forward_eps_rows_carry_year_series():
    result = call("ForwardEpsEstimates", symbol="600519.SH", limit=3).results

    assert result
    first = result[0]
    assert first.date is not None
    assert first.mean is not None  # year-1 estimate
    assert first.low_estimate is None  # no distribution upstream


@requires_credentials
def test_forward_pe_year_series():
    result = call("ForwardPeEstimates", symbol="600519.SH", limit=3).results

    assert result
    assert all(row.year1 is not None for row in result)
    assert all(row.year5 is None for row in result)


# ---------------------------------------------------------------- batch 1c


@requires_credentials
@pytest.mark.parametrize(
    ("model", "command_check"),
    [
        ("IncomeStatementGrowth", "total_revenue_growth"),
        ("BalanceSheetGrowth", "total_assets_growth"),
        ("CashFlowStatementGrowth", "net_cash_operating_growth"),
    ],
)
def test_growth_models_are_decimals_with_none_bases(model, command_check):
    result = call(model, symbol="600519.SH", limit=3).results

    assert result
    for row in result:
        value = getattr(row, command_check)
        assert value is None or abs(value) < 50, f"{command_check} out of decimal space"


@requires_credentials
def test_income_growth_matches_statement_levels():
    """Growth direction must agree with the level series it derives from."""
    growth = call("IncomeStatementGrowth", symbol="600519.SH", limit=3).results
    levels = call("IncomeStatement", symbol="600519.SH", limit=4).results

    by_year = {row.period_ending.year: row.total_revenue for row in levels}
    for row in growth:
        year = row.period_ending.year
        prior = by_year.get(year - 1)
        if row.total_revenue_growth is not None and prior:
            current = by_year.get(year)
            if current:
                assert row.total_revenue_growth == pytest.approx(current / prior - 1, rel=1e-6)


# ---------------------------------------------------------------- batch 1d


@requires_credentials
def test_screener_expression_scan():
    df = obb_helper().wmshare.screener(where="$ROE_TTM_LAST > 0.15", provider="wmshare").to_df()

    assert len(df) > 0
    assert "$ROE_TTM_LAST" in df.columns
    assert (df["$ROE_TTM_LAST"] > 0.15).all()


@requires_credentials
def test_index_valuation_trend_points():
    df = (
        obb_helper()
        .wmshare.index_valuation_trend(key="index.hs300", window="5y", provider="wmshare")
        .to_df()
    )

    assert len(df) >= 100
    assert df["pe_pct_window"].iloc[0] is not None
    assert 0 <= df["pe_pct_window"].iloc[0] <= 1


@requires_credentials
def test_moneyflow_margin_cbond_live():
    mf = obb_helper().wmshare.moneyflow(symbol="600519.SH", provider="wmshare").to_df()
    assert len(mf) > 0 and "net_mf" in mf.columns

    mg = obb_helper().wmshare.margin(symbol="600519.SH", provider="wmshare").to_df()
    assert len(mg) > 0 and "fin_balance" in mg.columns

    cb = obb_helper().wmshare.cbond_board(provider="wmshare").to_df()
    assert len(cb) > 100 and "bond_code" in cb.columns


def obb_helper():
    from openbb import obb

    return obb
