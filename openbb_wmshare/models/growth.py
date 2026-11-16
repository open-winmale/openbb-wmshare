"""wmshare statement growth models (income / balance sheet / cash flow).

Growth is derived locally as period-over-period YoY from the same pivoted
statements the income/balance/cash models serve — upstream has no growth
catalog functions for line items (the ``$`` metric layer is point-in-time
only), so there is nothing to consume instead. Periods lacking a prior base,
or with a zero base, carry ``None`` rather than a fabricated 0%.
"""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.balance_sheet_growth import (
    BalanceSheetGrowthData,
    BalanceSheetGrowthQueryParams,
)
from openbb_core.provider.standard_models.cash_flow_growth import (
    CashFlowStatementGrowthData,
    CashFlowStatementGrowthQueryParams,
)
from openbb_core.provider.standard_models.income_statement_growth import (
    IncomeStatementGrowthData,
    IncomeStatementGrowthQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError, OpenBBError
from pydantic import Field

from openbb_wmshare.models._statements import WmshareStatementQueryParams
from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols
from openbb_wmshare.utils.statements import compute_growth, pivot

INCOME_ITEMS = [
    "total_revenue",
    "operating_cost",
    "operating_profit",
    "total_profit",
    "net_profit",
    "np_parent",
    "eps_basic",
]
BALANCE_ITEMS = [
    "total_assets",
    "total_liabilities",
    "total_equity",
    "total_parent_equity",
    "monetary_funds",
    "inventories",
]
CASHFLOW_ITEMS = [
    "net_cash_operating",
    "net_cash_investing",
    "net_cash_financing",
    "cash_end",
]


class _WmshareGrowthQueryParams(WmshareStatementQueryParams):
    """Base query for the three growth models (already a QueryParams subclass)."""

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


async def _fetch_growth_rows(
    kind: str,
    symbol: str,
    *,
    limit: int | None,
    scope: str,
    market: str,
    credentials: dict[str, str] | None,
    items: list[str],
) -> list[dict]:
    """Fetch one statement and attach YoY growth for the requested items."""
    parsed = parse_symbol(symbol, default_market=market)
    if parsed.market != "cn":
        raise OpenBBError(
            "wmshare publishes statement growth for A-shares only; "
            f"{parsed.canonical} is a {parsed.market.upper()} symbol."
        )
    client = get_client(parsed.market, credentials)
    rows = await call(
        getattr(client.statements, kind),
        symbol=parsed.code,
        years=int(limit or 5),
        scope="合并",
        context=f"statements.{kind}({parsed.canonical})",
    )
    records = compute_growth(pivot(rows or []), items)
    if not records:
        raise EmptyDataError(f"No statement data returned for {parsed.canonical}.")
    for record in records:
        record["symbol"] = parsed.canonical
    return records[: int(limit)] if limit else records


class WmshareIncomeStatementGrowthQueryParams(
    _WmshareGrowthQueryParams, IncomeStatementGrowthQueryParams
):
    """wmshare Income Statement Growth Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareIncomeStatementGrowthData(IncomeStatementGrowthData):
    """wmshare Income Statement Growth Data (YoY, decimals)."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    total_revenue_growth: float | None = Field(
        default=None,
        description="Total revenue growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    operating_cost_growth: float | None = Field(
        default=None,
        description="Operating cost growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    operating_profit_growth: float | None = Field(
        default=None,
        description="Operating profit growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    total_profit_growth: float | None = Field(
        default=None,
        description="Total profit growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    net_profit_growth: float | None = Field(
        default=None,
        description="Net profit growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    np_parent_growth: float | None = Field(
        default=None,
        description="Net profit attributable to parent, growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    eps_basic_growth: float | None = Field(
        default=None,
        description="Basic EPS growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareIncomeStatementGrowthFetcher(
    Fetcher[WmshareIncomeStatementGrowthQueryParams, list[WmshareIncomeStatementGrowthData]]
):
    """wmshare Income Statement Growth Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIncomeStatementGrowthQueryParams:
        """Pass the query through unchanged."""
        return WmshareIncomeStatementGrowthQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareIncomeStatementGrowthQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch income rows and attach YoY growth."""
        rows: list[dict] = []
        for symbol in split_symbols(query.symbol):
            rows.extend(
                await _fetch_growth_rows(
                    "income",
                    symbol,
                    limit=query.limit,
                    scope=query.scope,
                    market=query.market,
                    credentials=credentials,
                    items=INCOME_ITEMS,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareIncomeStatementGrowthQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIncomeStatementGrowthData]:
        """Validate the growth rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareIncomeStatementGrowthData.model_validate(row) for row in data]


class WmshareBalanceSheetGrowthQueryParams(
    _WmshareGrowthQueryParams, BalanceSheetGrowthQueryParams
):
    """wmshare Balance Sheet Growth Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareBalanceSheetGrowthData(BalanceSheetGrowthData):
    """wmshare Balance Sheet Growth Data (YoY, decimals)."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    total_assets_growth: float | None = Field(
        default=None,
        description="Total assets growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    total_liabilities_growth: float | None = Field(
        default=None,
        description="Total liabilities growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    total_equity_growth: float | None = Field(
        default=None,
        description="Total equity growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    total_parent_equity_growth: float | None = Field(
        default=None,
        description="Equity attributable to parent, growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    monetary_funds_growth: float | None = Field(
        default=None,
        description="Cash and equivalents growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    inventories_growth: float | None = Field(
        default=None,
        description="Inventories growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareBalanceSheetGrowthFetcher(
    Fetcher[WmshareBalanceSheetGrowthQueryParams, list[WmshareBalanceSheetGrowthData]]
):
    """wmshare Balance Sheet Growth Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareBalanceSheetGrowthQueryParams:
        """Pass the query through unchanged."""
        return WmshareBalanceSheetGrowthQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareBalanceSheetGrowthQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch balance rows and attach YoY growth."""
        rows: list[dict] = []
        for symbol in split_symbols(query.symbol):
            rows.extend(
                await _fetch_growth_rows(
                    "balance",
                    symbol,
                    limit=query.limit,
                    scope=query.scope,
                    market=query.market,
                    credentials=credentials,
                    items=BALANCE_ITEMS,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareBalanceSheetGrowthQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareBalanceSheetGrowthData]:
        """Validate the growth rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareBalanceSheetGrowthData.model_validate(row) for row in data]


class WmshareCashFlowStatementGrowthQueryParams(
    _WmshareGrowthQueryParams, CashFlowStatementGrowthQueryParams
):
    """wmshare Cash Flow Statement Growth Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareCashFlowStatementGrowthData(CashFlowStatementGrowthData):
    """wmshare Cash Flow Statement Growth Data (YoY, decimals)."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    net_cash_operating_growth: float | None = Field(
        default=None,
        description="Operating cash flow growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    net_cash_investing_growth: float | None = Field(
        default=None,
        description="Investing cash flow growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    net_cash_financing_growth: float | None = Field(
        default=None,
        description="Financing cash flow growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    cash_end_growth: float | None = Field(
        default=None,
        description="Period-end cash growth YoY.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareCashFlowStatementGrowthFetcher(
    Fetcher[WmshareCashFlowStatementGrowthQueryParams, list[WmshareCashFlowStatementGrowthData]]
):
    """wmshare Cash Flow Statement Growth Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareCashFlowStatementGrowthQueryParams:
        """Pass the query through unchanged."""
        return WmshareCashFlowStatementGrowthQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareCashFlowStatementGrowthQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch cash-flow rows and attach YoY growth."""
        rows: list[dict] = []
        for symbol in split_symbols(query.symbol):
            rows.extend(
                await _fetch_growth_rows(
                    "cashflow",
                    symbol,
                    limit=query.limit,
                    scope=query.scope,
                    market=query.market,
                    credentials=credentials,
                    items=CASHFLOW_ITEMS,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareCashFlowStatementGrowthQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareCashFlowStatementGrowthData]:
        """Validate the growth rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareCashFlowStatementGrowthData.model_validate(row) for row in data]
