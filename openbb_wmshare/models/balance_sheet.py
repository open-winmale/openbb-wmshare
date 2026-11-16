"""wmshare Balance Sheet model."""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.balance_sheet import (
    BalanceSheetData,
    BalanceSheetQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.models._statements import WmshareStatementQueryParams, fetch_statement
from openbb_wmshare.utils import split_symbols


class WmshareBalanceSheetQueryParams(WmshareStatementQueryParams, BalanceSheetQueryParams):
    """wmshare Balance Sheet Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareBalanceSheetData(BalanceSheetData):
    """wmshare Balance Sheet Data."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    total_assets: float | None = Field(default=None, description="Total assets.")
    total_current_assets: float | None = Field(default=None, description="Total current assets.")
    total_noncurrent_assets: float | None = Field(
        default=None, description="Total non-current assets."
    )
    monetary_funds: float | None = Field(default=None, description="Cash and equivalents.")
    accounts_receivable: float | None = Field(default=None, description="Accounts receivable.")
    notes_receivable: float | None = Field(default=None, description="Notes receivable.")
    inventories: float | None = Field(default=None, description="Inventories.")
    prepayments: float | None = Field(default=None, description="Prepayments.")
    fixed_assets: float | None = Field(default=None, description="Fixed assets.")
    cip: float | None = Field(default=None, description="Construction in progress.")
    intangible_assets: float | None = Field(default=None, description="Intangible assets.")
    goodwill: float | None = Field(default=None, description="Goodwill.")
    long_term_equity_investment: float | None = Field(
        default=None, description="Long-term equity investments."
    )
    total_liabilities: float | None = Field(default=None, description="Total liabilities.")
    total_current_liabilities: float | None = Field(
        default=None, description="Total current liabilities."
    )
    total_noncurrent_liabilities: float | None = Field(
        default=None, description="Total non-current liabilities."
    )
    short_term_loans: float | None = Field(default=None, description="Short-term borrowings.")
    long_term_loans: float | None = Field(default=None, description="Long-term borrowings.")
    bonds_payable: float | None = Field(default=None, description="Bonds payable.")
    accounts_payable: float | None = Field(default=None, description="Accounts payable.")
    contract_assets: float | None = Field(default=None, description="Contract assets.")
    total_equity: float | None = Field(default=None, description="Total equity.")
    total_parent_equity: float | None = Field(
        default=None, description="Equity attributable to owners of the parent."
    )
    share_capital: float | None = Field(default=None, description="Share capital.")
    retained_earnings: float | None = Field(default=None, description="Retained earnings.")


class WmshareBalanceSheetFetcher(
    Fetcher[WmshareBalanceSheetQueryParams, list[WmshareBalanceSheetData]]
):
    """wmshare Balance Sheet Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareBalanceSheetQueryParams:
        """Pass the query through unchanged."""
        return WmshareBalanceSheetQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareBalanceSheetQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the balance sheet for every requested symbol."""
        rows: list[dict] = []
        for symbol in split_symbols(query.symbol):
            rows.extend(
                await fetch_statement(
                    "balance",
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
        query: WmshareBalanceSheetQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareBalanceSheetData]:
        """Validate the statement rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareBalanceSheetData.model_validate(row) for row in data]
