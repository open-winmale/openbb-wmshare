"""wmshare Insider Trading model.

`equity.query_exec_change` serves only the latest executive share-change row
(no paging upstream), so `limit` is accepted for interface compatibility and
the fetcher returns at most one row per symbol. Upstream labels this family
"待样本" (shape still settling); every field is therefore mapped as optional
and unknown keys are never invented.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.insider_trading import (
    InsiderTradingData,
    InsiderTradingQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareInsiderTradingQueryParams(InsiderTradingQueryParams):
    """wmshare Insider Trading Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="Symbol to get the latest insider change for.")
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. Executive changes cover A-shares only."
    )


class WmshareInsiderTradingData(InsiderTradingData):
    """wmshare Insider Trading Data."""

    executive_relation: str | None = Field(
        default=None, description="Relationship of the trader to the company."
    )
    trade_way: str | None = Field(default=None, description="Trading channel (e.g. 二级市场买卖).")
    change_after_holdnum: float | None = Field(
        default=None, description="Shares held after the change."
    )


class WmshareInsiderTradingFetcher(
    Fetcher[WmshareInsiderTradingQueryParams, list[WmshareInsiderTradingData]]
):
    """wmshare Insider Trading Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareInsiderTradingQueryParams:
        """Pass the query through unchanged.

        ``limit`` is accepted for interface compatibility; upstream serves a
        single latest row with no paging.
        """
        return WmshareInsiderTradingQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareInsiderTradingQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the latest executive share change per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            change = await call(
                client.equity.query_exec_change,
                parsed.code,
                context=f"equity.query_exec_change({parsed.canonical})",
            )
            if not isinstance(change, dict):
                continue
            rows.append(_to_row(change, parsed.canonical))
        return rows

    @staticmethod
    def transform_data(
        query: WmshareInsiderTradingQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareInsiderTradingData]:
        """Validate the change rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareInsiderTradingData.model_validate(row) for row in data]


def _to_row(change: dict, symbol: str) -> dict:
    """Map one upstream change record onto OpenBB's fields.

    `acquisition_or_disposition` is the sign of `change_num` itself (negative
    = disposed); nothing else is inferred.
    """
    change_num = change.get("change_num")
    disposition = None
    if isinstance(change_num, int | float) and change_num:
        disposition = "A" if change_num > 0 else "D"
    return {
        "symbol": symbol,
        "transaction_date": change.get("end_date"),
        "owner_name": change.get("executive_name") or change.get("holder_name"),
        "owner_title": change.get("position"),
        "acquisition_or_disposition": disposition,
        "securities_transacted": change_num,
        "transaction_price": change.get("average_price"),
        "executive_relation": change.get("executive_relation"),
        "trade_way": change.get("trade_way"),
        "change_after_holdnum": change.get("change_after_holdnum"),
    }
