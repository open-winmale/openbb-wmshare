"""wmshare Income Statement model."""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.income_statement import (
    IncomeStatementData,
    IncomeStatementQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.models._statements import WmshareStatementQueryParams, fetch_statement
from openbb_wmshare.utils import split_symbols


class WmshareIncomeStatementQueryParams(WmshareStatementQueryParams, IncomeStatementQueryParams):
    """wmshare Income Statement Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareIncomeStatementData(IncomeStatementData):
    """wmshare Income Statement Data.

    Line items use wmshare's snake_case statement codes, which already align
    with OpenBB's English field names.
    """

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    total_revenue: float | None = Field(default=None, description="Total revenue.")
    operating_revenue: float | None = Field(default=None, description="Operating revenue.")
    operating_cost: float | None = Field(default=None, description="Operating cost.")
    total_operating_cost: float | None = Field(default=None, description="Total operating cost.")
    tax_and_surtax: float | None = Field(default=None, description="Taxes and surcharges.")
    selling_expense: float | None = Field(default=None, description="Selling expense.")
    admin_expense: float | None = Field(default=None, description="Administrative expense.")
    rd_expense: float | None = Field(default=None, description="Research and development expense.")
    finance_expense: float | None = Field(default=None, description="Finance expense.")
    operating_profit: float | None = Field(default=None, description="Operating profit.")
    total_profit: float | None = Field(default=None, description="Total profit.")
    income_tax: float | None = Field(default=None, description="Income tax expense.")
    net_profit: float | None = Field(default=None, description="Net profit.")
    np_parent: float | None = Field(default=None, description="Net profit attributable to parent.")
    minority_interest: float | None = Field(default=None, description="Minority interest.")
    eps_basic: float | None = Field(default=None, description="Basic earnings per share.")


class WmshareIncomeStatementFetcher(
    Fetcher[WmshareIncomeStatementQueryParams, list[WmshareIncomeStatementData]]
):
    """wmshare Income Statement Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIncomeStatementQueryParams:
        """Pass the query through unchanged."""
        return WmshareIncomeStatementQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareIncomeStatementQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the income statement for every requested symbol."""
        rows: list[dict] = []
        for symbol in split_symbols(query.symbol):
            rows.extend(
                await fetch_statement(
                    "income",
                    symbol,
                    limit=query.limit,
                    market=query.market,
                    period=query.period,
                    credentials=credentials,
                )
            )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareIncomeStatementQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIncomeStatementData]:
        """Validate the statement rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareIncomeStatementData.model_validate(row) for row in data]
