"""wmshare Available Indices model."""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.available_indices import (
    AvailableIndicesData,
    AvailableIndicesQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError

from openbb_wmshare.utils import index_exchange, index_name
from openbb_wmshare.utils.index_universe import all_index_keys, index_keys_only


class WmshareAvailableIndicesQueryParams(AvailableIndicesQueryParams):
    """wmshare Available Indices Query.

    Source: https://github.com/open-winmale/wmshare
    """


class WmshareAvailableIndicesData(AvailableIndicesData):
    """wmshare Available Indices Data."""


class WmshareAvailableIndicesFetcher(
    Fetcher[WmshareAvailableIndicesQueryParams, list[WmshareAvailableIndicesData]]
):
    """wmshare Available Indices Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareAvailableIndicesQueryParams:
        """Pass the query through unchanged."""
        return WmshareAvailableIndicesQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareAvailableIndicesQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """List every index key wmshare can serve."""
        keys = index_keys_only(await all_index_keys(credentials))
        return [
            {
                "symbol": key,
                "name": index_name(key),
                "exchange": index_exchange(key),
                "currency": "CNY",
            }
            for key in keys
        ]

    @staticmethod
    def transform_data(
        query: WmshareAvailableIndicesQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareAvailableIndicesData]:
        """Validate the index rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareAvailableIndicesData.model_validate(row) for row in data]
