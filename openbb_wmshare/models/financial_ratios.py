"""wmshare Financial Ratios model.

Two sources, deliberately mixed — the newest period comes from wmshare's own
metric layer, older periods are derived locally:

* **Newest period — upstream ``$`` codes.** The platform already publishes these
  ratios, computed from the same statements plus share/dividend data we do not
  join locally. Recomputing them here would drift from the official figures, so
  where a curated code exists it wins.
* **Older periods — local derivation.** The metric layer is point-in-time only
  (``*_LAST`` codes return the latest value, with no history), so history has to
  come from the statements via :func:`compute_ratios`.

Every upstream code used here is *curated* (declared with a range guard in the
wmshare catalog), which means the SDK has already normalised it to a decimal.
Uncurated ``*_RATE``/``$SD`` style codes return native percentages and would put
a ``32.5`` next to a ``0.325`` in the same column, so they are excluded by
:data:`RATIO_CODES`. wmshare's ``statement_tree`` view is likewise not used: its
``pct`` rows carry native percentages.
"""

from __future__ import annotations

from typing import Any

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.financial_ratios import (
    FinancialRatiosData,
    FinancialRatiosQueryParams,
)
from openbb_core.provider.utils.errors import EmptyDataError, OpenBBError
from pydantic import Field

from openbb_wmshare.models._statements import WmshareStatementQueryParams
from openbb_wmshare.utils import call, get_client, parse_symbol, split_symbols
from openbb_wmshare.utils.statements import compute_ratios

RATIO_CODES: dict[str, str] = {
    "gross_margin": "$GM",
    "return_on_equity": "$ROE_TTM_LAST",
    "return_on_assets": "$ROIC_LAST",
    "asset_turnover": "$TA_TURNOVER",
    "debt_to_assets": "$TL_RATE_LAST",
    "quick_ratio": "$QUICK_RATIO_LAST",
}
"""OpenBB field -> curated wmshare metric code, applied to the newest period.

Curated codes only: the catalog's range guard tells the SDK to normalise them to
decimals, matching what ``compute_ratios`` emits for the older rows.
``$ROIC_LAST`` fills ``return_on_assets`` because wmshare has no ``$ROA_LAST``;
return on invested capital is the closest guarded code available.
"""


class WmshareFinancialRatiosQueryParams(WmshareStatementQueryParams, FinancialRatiosQueryParams):
    """wmshare Financial Ratios Query.

    Source: https://github.com/open-winmale/wmshare
    """

    __json_schema_extra__ = {
        "symbol": {"multiple_items_allowed": True},
        **WmshareStatementQueryParams.__json_schema_extra__,
    }


class WmshareFinancialRatiosData(FinancialRatiosData):
    """wmshare Financial Ratios Data.

    All ratios are decimals: ``0.32`` means 32%.
    """

    gross_margin: float | None = Field(default=None, description="Gross profit margin.")
    operating_margin: float | None = Field(default=None, description="Operating margin.")
    pretax_margin: float | None = Field(default=None, description="Pre-tax profit margin.")
    net_margin: float | None = Field(default=None, description="Net profit margin.")
    return_on_assets: float | None = Field(default=None, description="Return on assets.")
    return_on_equity: float | None = Field(default=None, description="Return on equity.")
    debt_to_assets: float | None = Field(default=None, description="Total liabilities / assets.")
    equity_to_assets: float | None = Field(default=None, description="Total equity / assets.")
    current_ratio: float | None = Field(
        default=None, description="Current assets / current liabilities."
    )
    quick_ratio: float | None = Field(
        default=None, description="(Current assets - inventories) / current liabilities."
    )
    cash_ratio: float | None = Field(default=None, description="Cash / current liabilities.")
    asset_turnover: float | None = Field(default=None, description="Revenue / average assets.")
    inventory_turnover: float | None = Field(
        default=None, description="Operating cost / average inventories."
    )
    receivables_turnover: float | None = Field(
        default=None, description="Revenue / average accounts receivable."
    )


class WmshareFinancialRatiosFetcher(
    Fetcher[WmshareFinancialRatiosQueryParams, list[WmshareFinancialRatiosData]]
):
    """wmshare Financial Ratios Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareFinancialRatiosQueryParams:
        """Pass the query through unchanged."""
        return WmshareFinancialRatiosQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareFinancialRatiosQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Fetch both statements per symbol, then derive the ratios."""
        rows: list[dict] = []
        for raw in split_symbols(query.symbol):
            parsed = parse_symbol(raw, default_market=query.market)
            if parsed.market != "cn":
                raise OpenBBError(
                    "wmshare publishes financial statements for A-shares only; "
                    f"{parsed.canonical} is a {parsed.market.upper()} symbol."
                )

            client = get_client(parsed.market, credentials)
            years = int(query.limit or 5)
            statements = {}
            for kind in ("income", "balance"):
                statements[kind] = await call(
                    getattr(client.statements, kind),
                    symbol=parsed.code,
                    years=years,
                    scope="合并",
                    context=f"statements.{kind}({parsed.canonical})",
                )

            symbol_rows = compute_ratios(statements["income"] or [], statements["balance"] or [])
            for record in symbol_rows:
                record["symbol"] = parsed.canonical
            if symbol_rows:
                # Only this symbol's newest row is overlaid; older periods keep
                # the locally derived numbers.
                await _overlay_upstream_ratios(client, parsed, symbol_rows)
            rows.extend(symbol_rows)
        return rows

    @staticmethod
    def transform_data(
        query: WmshareFinancialRatiosQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareFinancialRatiosData]:
        """Validate the ratio rows."""
        if not data:
            raise EmptyDataError()
        return [WmshareFinancialRatiosData.model_validate(row) for row in data]


async def _overlay_upstream_ratios(client: Any, parsed: Any, rows: list[dict]) -> None:
    """Replace the newest period's locally derived ratios with upstream values.

    ``compute_ratios`` sorts newest-first, so ``rows[0]`` is the period the
    ``*_LAST`` codes describe. Values are written in place; a code that returns
    ``None`` leaves the locally derived number, so a partial upstream response
    degrades one column instead of blanking the row.
    """
    values = await call(
        client.indicator.metrics,
        parsed.code,
        list(RATIO_CODES.values()),
        context=f"indicator.metrics({parsed.canonical})",
    )
    if not isinstance(values, dict) or not values:
        return

    newest = rows[0]
    for field, code in RATIO_CODES.items():
        if code not in values:
            continue
        value = values.get(code)
        if value is None:
            continue
        newest[field] = value
