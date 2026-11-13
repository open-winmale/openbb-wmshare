"""wmshare Index Search model."""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_search import (
    IndexSearchData,
    IndexSearchQueryParams,
)
from pydantic import Field

from openbb_wmshare.utils import index_exchange, index_name, index_search_terms
from openbb_wmshare.utils.index_universe import all_index_keys, index_keys_only


class WmshareIndexSearchQueryParams(IndexSearchQueryParams):
    """wmshare Index Search Query.

    Source: https://github.com/open-winmale/wmshare
    """


class WmshareIndexSearchData(IndexSearchData):
    """wmshare Index Search Data."""

    exchange: str | None = Field(default=None, description="Listing venue of the index.")


class WmshareIndexSearchFetcher(
    Fetcher[WmshareIndexSearchQueryParams, list[WmshareIndexSearchData]]
):
    """wmshare Index Search Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIndexSearchQueryParams:
        """Pass the query through unchanged."""
        return WmshareIndexSearchQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareIndexSearchQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Filter the available index keys by key, English name or Chinese name.

        ``is_symbol`` narrows the haystack to the key itself, which is what a
        caller passing a real key expects. An empty query lists everything,
        matching the behaviour of other OpenBB search providers.
        """
        keys = index_keys_only(await all_index_keys(credentials))
        term = str(query.query or "").strip().casefold()

        matches = []
        for key in keys:
            haystack = key.casefold() if query.is_symbol else index_search_terms(key)
            if term and term not in haystack:
                continue
            matches.append(
                {
                    "symbol": key,
                    "name": index_name(key),
                    "exchange": index_exchange(key),
                }
            )
        return matches

    @staticmethod
    def transform_data(
        query: WmshareIndexSearchQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIndexSearchData]:
        """Validate the search rows; an empty result is a valid answer."""
        return [WmshareIndexSearchData.model_validate(row) for row in data]
