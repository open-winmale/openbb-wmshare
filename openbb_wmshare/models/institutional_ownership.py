"""wmshare Institutional Ownership model.

`equity.query_institution_detail` lists institutional holders per report
period. The standard model only requires `symbol` + `date`; wmshare's richer
rows (holder, shares, value, ratios) pass through as declared extras. Ratios
arrive already normalized to decimals (SDK unit handling).
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.institutional_ownership import (
    InstitutionalOwnershipData,
    InstitutionalOwnershipQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareInstitutionalOwnershipQueryParams(InstitutionalOwnershipQueryParams):
    """wmshare Institutional Ownership Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {"symbol": {"multiple_items_allowed": True}}

    symbol: str = Field(description="Symbol to get institutional holders for.")
    limit: int = Field(default=20, description="Number of holder rows per symbol.", ge=1, le=100)
    market: Literal["cn"] = Field(
        default="cn",
        description="Market segment. Institutional holdings cover A-shares only.",
    )


class WmshareInstitutionalOwnershipData(InstitutionalOwnershipData):
    """wmshare Institutional Ownership Data."""

    holder_name: str | None = Field(default=None, description="Institution holder name.")
    org_type: str | None = Field(default=None, description="Institution type code.")
    shares: float | None = Field(default=None, description="Shares held.")
    value: float | None = Field(default=None, description="Holding value, in CNY.")
    total_shares_ratio: float | None = Field(
        default=None,
        description="Holding as a share of total shares, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    free_shares_ratio: float | None = Field(
        default=None,
        description="Holding as a share of free float, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )


class WmshareInstitutionalOwnershipFetcher(
    Fetcher[WmshareInstitutionalOwnershipQueryParams, list[WmshareInstitutionalOwnershipData]]
):
    """wmshare Institutional Ownership Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareInstitutionalOwnershipQueryParams:
        """Pass the query through unchanged."""
        return WmshareInstitutionalOwnershipQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareInstitutionalOwnershipQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch institutional holder rows per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            client = get_client(parsed.market, credentials)
            holders = await call(
                client.equity.query_institution_detail,
                parsed.code,
                limit=query.limit,
                context=f"equity.query_institution_detail({parsed.canonical})",
            )
            for row in holders or []:
                if not isinstance(row, dict) or not row.get("report_date"):
                    # `date` is required by the standard model.
                    continue
                rows.append(
                    {
                        "symbol": parsed.canonical,
                        "date": row.get("report_date"),
                        "holder_name": row.get("holder_name"),
                        "org_type": row.get("org_type"),
                        "shares": row.get("total_shares"),
                        "value": row.get("hold_value"),
                        "total_shares_ratio": row.get("total_shares_ratio"),
                        "free_shares_ratio": row.get("free_shares_ratio"),
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareInstitutionalOwnershipQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareInstitutionalOwnershipData]:
        """Validate the holder rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareInstitutionalOwnershipData.model_validate(row) for row in data]
