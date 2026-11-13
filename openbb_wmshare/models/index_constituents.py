"""wmshare Index Constituents model."""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_constituents import (
    IndexConstituentsData,
    IndexConstituentsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, normalize_index_key, split_symbols
from openbb_wmshare.utils.symbols import ParsedSymbol


class WmshareIndexConstituentsQueryParams(IndexConstituentsQueryParams):
    """wmshare Index Constituents Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"market": {"choices": ["cn"]}}

    market: Literal["cn"] = Field(
        default="cn", description="Market segment. wmshare index data covers A-shares only."
    )
    include_weights: bool = Field(
        default=True,
        description="Also fetch published index weights, at the cost of one extra request.",
    )


class WmshareIndexConstituentsData(IndexConstituentsData):
    """wmshare Index Constituents Data."""

    index: str | None = Field(default=None, description="Index key the member belongs to.")
    weight: float | None = Field(
        default=None,
        description="Index weight, as a normalized percent (0.071 = 7.1%).",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    market_cap: float | None = Field(default=None, description="Market capitalisation.")
    pe_ttm: float | None = Field(default=None, description="Price-to-earnings ratio (TTM).")
    pb: float | None = Field(default=None, description="Price-to-book ratio.")
    roe_ttm: float | None = Field(default=None, description="Return on equity (TTM).")


class WmshareIndexConstituentsFetcher(
    Fetcher[WmshareIndexConstituentsQueryParams, list[WmshareIndexConstituentsData]]
):
    """wmshare Index Constituents Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIndexConstituentsQueryParams:
        """Pass the query through unchanged."""
        return WmshareIndexConstituentsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareIndexConstituentsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch members, then merge in published weights when requested.

        ``members`` already carries market cap and valuation, so the weights
        call is the only extra request and is skippable.
        """
        client = get_client("cn", credentials)
        rows: list[dict] = []

        for raw in split_symbols(query.symbol):
            key = normalize_index_key(raw)
            members = await call(client.index.members, key, context=f"index.members({key})")
            weights = (
                await call(client.index.weights, key, context=f"index.weights({key})")
                if query.include_weights
                else []
            )
            weight_by_symbol = {
                str(row.get("symbol")): row.get("weight")
                for row in weights or []
                if isinstance(row, dict)
            }

            for member in members or []:
                if not isinstance(member, dict):
                    continue
                code = str(member.get("symbol") or "").strip()
                if not code:
                    continue
                rows.append(
                    {
                        "symbol": ParsedSymbol("cn", code.zfill(6)).canonical,
                        "name": member.get("name"),
                        "index": key,
                        "weight": weight_by_symbol.get(code),
                        "market_cap": member.get("mv"),
                        "pe_ttm": member.get("pe_ttm"),
                        "pb": member.get("pb"),
                        "roe_ttm": member.get("roe_ttm"),
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareIndexConstituentsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIndexConstituentsData]:
        """Validate the constituent rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareIndexConstituentsData.model_validate(row) for row in data]
