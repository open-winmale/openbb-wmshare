"""wmshare Cash Flow Statement model."""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.cash_flow import (
    CashFlowStatementData,
    CashFlowStatementQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.models._statements import WmshareStatementQueryParams, fetch_statement
from openbb_wmshare.utils import split_symbols


class WmshareCashFlowStatementQueryParams(
    WmshareStatementQueryParams, CashFlowStatementQueryParams
):
    """wmshare Cash Flow Statement Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareCashFlowStatementData(CashFlowStatementData):
    """wmshare Cash Flow Statement Data."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    net_cash_operating: float | None = Field(
        default=None, description="Net cash from operating activities."
    )
    net_cash_investing: float | None = Field(
        default=None, description="Net cash from investing activities."
    )
    net_cash_financing: float | None = Field(
        default=None, description="Net cash from financing activities."
    )
    net_cash_increase: float | None = Field(
        default=None, description="Net increase in cash and equivalents."
    )
    cash_end: float | None = Field(default=None, description="Cash and equivalents at period end.")
    cash_from_sales: float | None = Field(
        default=None, description="Cash received from sales of goods and services."
    )
    taxes_paid: float | None = Field(default=None, description="Taxes paid.")
    cash_paid_to_employees: float | None = Field(
        default=None, description="Cash paid to and on behalf of employees."
    )
    capex_cash: float | None = Field(default=None, description="Cash paid for capital expenditure.")
    cash_dividend_paid: float | None = Field(default=None, description="Cash dividends paid.")


class WmshareCashFlowStatementFetcher(
    Fetcher[WmshareCashFlowStatementQueryParams, list[WmshareCashFlowStatementData]]
):
    """wmshare Cash Flow Statement Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareCashFlowStatementQueryParams:
        """Pass the query through unchanged."""
        return WmshareCashFlowStatementQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareCashFlowStatementQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the cash flow statement for every requested symbol."""
        rows: list[dict] = []
        for symbol in split_symbols(query.symbol):
            rows.extend(
                await fetch_statement(
                    "cashflow",
                    symbol,
                    limit=query.limit,
                    scope=query.scope,
                    market=query.market,
                    period=query.period,
                    credentials=credentials,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareCashFlowStatementQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareCashFlowStatementData]:
        """Validate the statement rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareCashFlowStatementData.model_validate(row) for row in data]
