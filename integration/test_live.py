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


@requires_credentials
def test_statements_reject_non_a_share_symbols():
    with pytest.raises(OpenBBError, match="A-shares only"):
        call("IncomeStatement", symbol="00700.HK")


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
