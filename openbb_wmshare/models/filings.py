"""wmshare Company Filings model.

Maps `cli.filings.list` (kind-filtered periodic-report list) onto OpenBB's
filings surface. Rows carry `notice_date` / `report_date` / `pdf_url`; the
catalog's shape declaration calls the link field `url`, but the normalized
rows say `pdf_url` — verified live 2026-11-14 (another under-declared shape,
BUGS.md SDK-5 family).

`report_url` is required by the standard model, so rows without a link are
skipped rather than fabricated; wmshare's periodic-report rows always carry
one in practice.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.company_filings import (
    CompanyFilingsData,
    CompanyFilingsQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols


class WmshareCompanyFilingsQueryParams(CompanyFilingsQueryParams):
    """wmshare Company Filings Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        "kind": {"choices": ["all", "annual", "semi", "quarter"]},
    }

    symbol: str = Field(description="Symbol to get filings for.")
    kind: Literal["all", "annual", "semi", "quarter"] = Field(
        default="all",
        description="Report kind filter: all, annual (年报), semi (半年报), quarter (季报).",
    )
    limit: int = Field(default=10, description="Number of filings per symbol.", ge=1, le=100)


class WmshareCompanyFilingsData(CompanyFilingsData):
    """wmshare Company Filings Data."""

    symbol: str | None = Field(default=None, description="Symbol of the company.")
    report_date: str | None = Field(default=None, description="Fiscal period the report covers.")
    title: str | None = Field(default=None, description="Report title.")


class WmshareCompanyFilingsFetcher(
    Fetcher[WmshareCompanyFilingsQueryParams, list[WmshareCompanyFilingsData]]
):
    """wmshare Company Filings Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareCompanyFilingsQueryParams:
        """Pass the query through unchanged."""
        return WmshareCompanyFilingsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareCompanyFilingsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch filings per symbol."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market="cn")
            client = get_client(parsed.market, credentials)
            filings = await call(
                client.filings.list,
                parsed.code,
                kind=query.kind,
                limit=query.limit,
                context=f"filings.list({parsed.canonical})",
            )
            for row in filings or []:
                if not isinstance(row, dict) or not row.get("pdf_url"):
                    # report_url is required by the standard model; a filing
                    # without a link cannot be represented honestly.
                    continue
                rows.append(
                    {
                        "symbol": parsed.canonical,
                        "filing_date": row.get("notice_date"),
                        "report_type": row.get("notice_type"),
                        "report_url": row.get("pdf_url"),
                        "report_date": row.get("report_date"),
                        "title": row.get("title"),
                    }
                )
        return rows

    @staticmethod
    def transform_data(
        query: WmshareCompanyFilingsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareCompanyFilingsData]:
        """Validate the filing rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareCompanyFilingsData.model_validate(row) for row in data]
