"""wmshare money-flow / margin / CBond board — provider-exclusive commands.

Three A-share-only surfaces with no OpenBB standard model: daily money-flow
tiers, margin trading balances, and the convertible-bond board snapshot.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols

# ---------------------------------------------------------------- moneyflow


class WmshareMoneyflowQueryParams(QueryParams):
    """wmshare Money Flow Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="A-share symbol(s).")
    n: int = Field(default=20, description="Rows per symbol.", ge=1, le=10000)
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. Money flow covers A-shares."
    )


class WmshareMoneyflowData(Data):
    """wmshare Money Flow Data (daily net inflow tiers, CNY)."""

    symbol: str = Field(description="A-share code, canonical form.")
    date: str = Field(description="Trading date.")
    net_mf: float | None = Field(default=None, description="Total net inflow, in CNY.")
    elg_net: float | None = Field(default=None, description="Extra-large order net inflow, CNY.")
    lg_net: float | None = Field(default=None, description="Large order net inflow, CNY.")
    md_net: float | None = Field(default=None, description="Medium order net inflow, CNY.")
    sm_net: float | None = Field(default=None, description="Small order net inflow, CNY.")


class WmshareMoneyflowFetcher(Fetcher[WmshareMoneyflowQueryParams, list[WmshareMoneyflowData]]):
    """wmshare Money Flow Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareMoneyflowQueryParams:
        """Pass the query through unchanged."""
        return WmshareMoneyflowQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareMoneyflowQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch money-flow bars per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            bars = await call(
                client.moneyflow.bars,
                parsed.code,
                n=query.n,
                context=f"moneyflow.bars({parsed.canonical})",
            )
            for bar in bars or []:
                if not isinstance(bar, dict) or not bar.get("date"):
                    continue
                rows.append({"symbol": parsed.canonical, **bar})
        return rows

    @staticmethod
    def transform_data(
        query: WmshareMoneyflowQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareMoneyflowData]:
        """Validate the flow rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareMoneyflowData.model_validate(row) for row in data]


# ---------------------------------------------------------------- margin


class WmshareMarginQueryParams(QueryParams):
    """wmshare Margin Query.

    Source: https://github.com/open-winmale/wmshare
    """

    symbol: str = Field(description="A-share symbol.")
    limit: int = Field(default=20, description="Rows to return.", ge=1, le=100)
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. Margin trading covers A-shares."
    )


class WmshareMarginData(Data):
    """wmshare Margin Data (daily financing/securities lending, CNY and shares)."""

    symbol: str = Field(description="A-share code, canonical form.")
    trade_date: str = Field(description="Trading date.")
    fin_buy_amt: float | None = Field(default=None, description="Financing buy amount, CNY.")
    fin_repay_amt: float | None = Field(default=None, description="Financing repayment, CNY.")
    fin_balance: float | None = Field(default=None, description="Financing balance, CNY.")
    loan_sell_vol: float | None = Field(default=None, description="Securities sold short, shares.")
    loan_repay_vol: float | None = Field(default=None, description="Securities repaid, shares.")
    loan_balance: float | None = Field(
        default=None, description="Securities lending balance, shares."
    )


class WmshareMarginFetcher(Fetcher[WmshareMarginQueryParams, list[WmshareMarginData]]):
    """wmshare Margin Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareMarginQueryParams:
        """Pass the query through unchanged."""
        return WmshareMarginQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareMarginQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch margin rows for the symbol."""
        parsed = parse_symbol(query.symbol, default_market=query.market)
        client = get_client(parsed.market, credentials)
        rows = await call(
            client.margin.query,
            parsed.code,
            limit=query.limit,
            context=f"margin.query({parsed.canonical})",
        )
        out: list[dict] = []
        for row in rows or []:
            if not isinstance(row, dict) or not row.get("trade_date"):
                continue
            entry = {
                k: v
                for k, v in row.items()
                if k not in ("secucode", "security_code", "security_name")
            }
            out.append({"symbol": parsed.canonical, **entry})
        return out

    @staticmethod
    def transform_data(
        query: WmshareMarginQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareMarginData]:
        """Validate the margin rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareMarginData.model_validate(row) for row in data]


# ---------------------------------------------------------------- CBond board


class WmshareCbondBoardQueryParams(QueryParams):
    """wmshare CBond Board Query.

    Source: https://github.com/open-winmale/wmshare
    """

    limit: int | None = Field(
        default=None,
        description="Rows to return; None = the whole board (~1000 rows).",
        ge=1,
    )
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. The CBond board covers A-share convertibles."
    )


class WmshareCbondBoardData(Data):
    """wmshare CBond Board Data (convertible-bond snapshot; upstream extras pass through)."""

    bond_code: str | None = Field(default=None, description="Convertible bond code.")
    bond_name: str | None = Field(default=None, description="Convertible bond name.")
    as_of: str | None = Field(default=None, description="Snapshot date.")
    stock_code: str | None = Field(default=None, description="Underlying stock code.")
    bond_price: float | None = Field(default=None, description="Bond price (par = 100).")
    convert_price: float | None = Field(default=None, description="Conversion price, CNY.")
    bond_rating: str | None = Field(default=None, description="Credit rating.")
    remain_size: float | None = Field(default=None, description="Outstanding size, in 亿元.")


class WmshareCbondBoardFetcher(Fetcher[WmshareCbondBoardQueryParams, list[WmshareCbondBoardData]]):
    """wmshare CBond Board Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareCbondBoardQueryParams:
        """Pass the query through unchanged."""
        return WmshareCbondBoardQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareCbondBoardQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the whole board in one server-precomputed call."""
        client = get_client(query.market, credentials)
        board = await call(client.cbond.board, context="cbond.board")
        rows: list[dict] = []
        for row in board or []:
            if not isinstance(row, dict):
                continue
            entry = dict(row)
            # upstream camelCase keys surface as extras via the alias generator
            entry.setdefault("bond_code", row.get("bondCode"))
            entry.setdefault("bond_name", row.get("bondName"))
            entry.setdefault("as_of", row.get("asOf"))
            entry.setdefault("stock_code", row.get("stockCode") or row.get("convCode"))
            entry.setdefault("bond_price", row.get("bondPrice"))
            entry.setdefault("convert_price", row.get("convertPrice"))
            entry.setdefault("bond_rating", row.get("bondRating"))
            entry.setdefault("remain_size", row.get("remainSize"))
            rows.append(entry)
        return rows[: query.limit] if query.limit else rows

    @staticmethod
    def transform_data(
        query: WmshareCbondBoardQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareCbondBoardData]:
        """Validate the board rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareCbondBoardData.model_validate(row) for row in data]
