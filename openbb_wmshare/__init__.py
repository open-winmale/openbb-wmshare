"""wmshare provider extension for the OpenBB Platform.

``fetcher_dict`` keys are OpenBB standard-model names, not command names — the
router in ``openbb-equity`` / ``openbb-index`` looks a fetcher up by model name.
Registering ``"EquityHistorical"`` is therefore all it takes for
``provider="wmshare"`` to appear in ``obb.equity.price.historical``.

Credentials are declared without the provider prefix: OpenBB expands
``["client_id", "client_secret"]`` into ``wmshare_client_id`` and
``wmshare_client_secret``.
"""

from __future__ import annotations

from openbb_core.provider.abstract.provider import Provider

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
from openbb_wmshare.models.index_historical import (
    WmshareIndexHistoricalFetcher,
)
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

wmshare_provider = Provider(
    name="wmshare",
    description=(
        "wmshare is a Python SDK for China A-share, Hong Kong and US market data: "
        "daily and aggregated K-lines, snapshots, financial statements, "
        "server-precomputed metrics, dividends, and A-share index membership."
    ),
    website="https://github.com/open-winmale/wmshare",
    credentials=["client_id", "client_secret"],
    fetcher_dict={
        "EquityHistorical": WmshareEquityHistoricalFetcher,
        "EquityQuote": WmshareEquityQuoteFetcher,
        "EquitySearch": WmshareEquitySearchFetcher,
        "EquityInfo": WmshareEquityInfoFetcher,
        "IncomeStatement": WmshareIncomeStatementFetcher,
        "BalanceSheet": WmshareBalanceSheetFetcher,
        "CashFlowStatement": WmshareCashFlowStatementFetcher,
        "KeyMetrics": WmshareKeyMetricsFetcher,
        "FinancialRatios": WmshareFinancialRatiosFetcher,
        "HistoricalDividends": WmshareHistoricalDividendsFetcher,
        "CalendarDividend": WmshareCalendarDividendFetcher,
        "IndexHistorical": WmshareIndexHistoricalFetcher,
        "IndexConstituents": WmshareIndexConstituentsFetcher,
        "IndexSearch": WmshareIndexSearchFetcher,
        "AvailableIndices": WmshareAvailableIndicesFetcher,
        "IndexSnapshots": WmshareIndexSnapshotsFetcher,
        "EquityGainers": WmshareEquityGainersFetcher,
        "EquityLosers": WmshareEquityLosersFetcher,
        "TrailingDividendYield": WmshareTrailingDivYieldFetcher,
        "CompanyFilings": WmshareCompanyFilingsFetcher,
        "KeyExecutives": WmshareKeyExecutivesFetcher,
        "ShareStatistics": WmshareShareStatisticsFetcher,
        "InstitutionalOwnership": WmshareInstitutionalOwnershipFetcher,
        "InsiderTrading": WmshareInsiderTradingFetcher,
        "RevenueBusinessLine": WmshareRevenueBusinessLineFetcher,
        "RevenueGeographic": WmshareRevenueGeographicFetcher,
        "CalendarEarnings": WmshareCalendarEarningsFetcher,
        "ForwardEpsEstimates": WmshareForwardEpsEstimatesFetcher,
        "ForwardPeEstimates": WmshareForwardPeEstimatesFetcher,
        "IncomeStatementGrowth": WmshareIncomeStatementGrowthFetcher,
        "BalanceSheetGrowth": WmshareBalanceSheetGrowthFetcher,
        "CashFlowStatementGrowth": WmshareCashFlowStatementGrowthFetcher,
        "WmshareScreener": WmshareScreenerFetcher,
        "WmshareIndexValuationTrend": WmshareIndexValuationTrendFetcher,
        "WmshareMoneyflow": WmshareMoneyflowFetcher,
        "WmshareMargin": WmshareMarginFetcher,
        "WmshareCbondBoard": WmshareCbondBoardFetcher,
    },
    repr_name="wmshare (A-share / Hong Kong / US)",
    instructions=(
        "Obtain an AppId and API Key from https://open.winmale.com (我的 → 开放平台 → 我的应用), "
        "then set wmshare_client_id / wmshare_client_secret in "
        "~/.openbb_platform/user_settings.json, or export "
        "WMSHARE_CLIENT_ID / WMSHARE_CLIENT_SECRET."
    ),
)
