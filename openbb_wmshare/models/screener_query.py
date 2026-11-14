"""wmshare screener query — provider-exclusive command (`obb.wmshare.screener`).

The OpenBB EquityScreener standard model is a fixed-field parameterized
screen; wmshare's screener is a server-side boolean expression scan over
`$codes` (e.g. ``"$ROE_TTM_LAST > 0.15"``). The semantics do not fit the
standard model, so this is exposed as a provider-owned command instead of
being forced into it.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.data import Data
from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.abstract.query_params import QueryParams
from openbb_core.provider.utils.errors import EmptyDataError
from pydantic import Field

from openbb_wmshare.utils import call, get_client
from openbb_wmshare.utils.symbols import ParsedSymbol


class WmshareScreenerQueryParams(QueryParams):
    """wmshare Screener Query.

    Source: https://github.com/open-winmale/wmshare
    """

    where: str = Field(
        description="XS boolean expression over catalog $codes, e.g. "
        "'$BONUS_RATE_3Y_AVG_LAST > 0.03 && $ROE_TTM_LAST > 0.15'. "
        "Browse codes via `obb.equity.search` / the wmshare catalog."
    )
    order: str | None = Field(
        default=None, description="$code to sort by, descending when desc=True."
    )
    desc: bool = Field(default=True, description="Sort direction for `order`.")
    limit: int = Field(default=50, description="Rows to return (0 = count only).", ge=0)
    offset: int = Field(default=0, description="Row offset for pagination.", ge=0)
    market: Literal["cn"] = Field(
        default="cn", description="Market segment. The screener index covers A-shares."
    )


class WmshareScreenerData(Data):
    """wmshare Screener Row.

    `symbol`/`name` are always present; every `$code` named in `where`/`order`
    comes back as an extra field keyed by its code (e.g. ``$ROE_TTM_LAST``).
    """

    symbol: str = Field(description="Matched A-share code.")
    name: str | None = Field(default=None, description="Company name.")


class WmshareScreenerFetcher(Fetcher[WmshareScreenerQueryParams, list[WmshareScreenerData]]):
    """wmshare Screener Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareScreenerQueryParams:
        """Pass the query through unchanged."""
        return WmshareScreenerQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareScreenerQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> dict:
        """Run the server-side scan; the hit count is in `count`, rows are top-N."""
        client = get_client(query.market, credentials)
        kwargs_call: dict[str, Any] = {
            "where": query.where,
            "limit": query.limit,
            "offset": query.offset,
        }
        if query.order:
            kwargs_call["order"] = query.order
            kwargs_call["desc"] = query.desc
        return await call(client.screener.query, **kwargs_call, context="screener.query")

    @staticmethod
    def transform_data(
        query: WmshareScreenerQueryParams,
        data: dict,
        **kwargs: Any,
    ) -> Any:
        """Return rows plus the true hit count as an annotated result.

        The scan's `count` is the whole-market hit count, not the row count —
        surfacing it per row would be wrong, so it rides the result metadata
        instead.
        """
        rows = data.get("rows") if isinstance(data, dict) else None
        if not rows:
            raise EmptyDataError("No matches; check the expression against catalog $codes.")
        # Upstream rows carry bare 6-digit codes; canonicalize to 600519.SH form
        # so output matches every other endpoint in this provider.
        for row in rows:
            if isinstance(row, dict) and row.get("symbol"):
                row["symbol"] = ParsedSymbol("cn", str(row["symbol"]).zfill(6)).canonical
        result = [WmshareScreenerData.model_validate(row) for row in rows]
        count = data.get("count")
        from openbb_core.provider.abstract.annotated_result import AnnotatedResult

        return (
            AnnotatedResult(result=result, metadata={"count": count})
            if count is not None
            else result
        )
