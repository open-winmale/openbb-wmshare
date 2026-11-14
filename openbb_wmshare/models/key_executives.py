"""wmshare Key Executives model.

`equity.query_executives` returns a richer roster than the catalog declares
(age, degree, tenure, nationality — BUGS.md SDK-5 family); the extras pass
through. Standard `title`/`name` are required, so rows missing a position are
skipped.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.key_executives import (
    KeyExecutivesData,
    KeyExecutivesQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareKeyExecutivesQueryParams(KeyExecutivesQueryParams):
    """wmshare Key Executives Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="Symbol to get executives for.")
    market: Literal["cn"] = Field(
        default="cn",
        description="Market segment. The executive roster covers A-shares only.",
    )


class WmshareKeyExecutivesData(KeyExecutivesData):
    """wmshare Key Executives Data."""

    hold_num: float | None = Field(default=None, description="Shares held by the executive.")
    high_degree: str | None = Field(default=None, description="Highest degree earned.")
    age: int | None = Field(default=None, description="Age.")
    nationality: str | None = Field(default=None, description="Nationality.")
    incumbent_time: str | None = Field(default=None, description="Tenure start, as text.")


class WmshareKeyExecutivesFetcher(
    Fetcher[WmshareKeyExecutivesQueryParams, list[WmshareKeyExecutivesData]]
):
    """wmshare Key Executives Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareKeyExecutivesQueryParams:
        """Pass the query through unchanged."""
        return WmshareKeyExecutivesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareKeyExecutivesQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch the executive roster per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            roster = await call(
                client.equity.query_executives,
                parsed.code,
                context=f"equity.query_executives({parsed.canonical})",
            )
            for row in roster or []:
                if not isinstance(row, dict):
                    continue
                # `title` and `name` are required upstream of validation.
                if not row.get("person_name") or not row.get("position"):
                    continue
                rows.append(
                    {
                        "name": row.get("person_name"),
                        "title": row.get("position"),
                        "pay": row.get("salary"),
                        "currency_pay": "CNY" if row.get("salary") is not None else None,
                        "gender": row.get("sex") or None,
                        "year_born": row.get("birth_year"),
                        "hold_num": row.get("hold_num"),
                        "high_degree": row.get("high_degree") or None,
                        "age": row.get("age"),
                        "nationality": row.get("nationality") or None,
                        "incumbent_time": row.get("incumbent_time") or None,
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareKeyExecutivesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareKeyExecutivesData]:
        """Validate the roster rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareKeyExecutivesData.model_validate(row) for row in data]
