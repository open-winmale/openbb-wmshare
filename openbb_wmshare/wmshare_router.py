"""wmshare-owned command namespace (`obb.wmshare.*`).

Registered via the ``openbb_core_extension`` entry point. These commands
serve wmshare-exclusive surfaces whose semantics do not fit any OpenBB
standard model (screener expressions, index valuation quantiles, money-flow
tiers, margin balances, the CBond board); everything stays on
catalog-registered functions through the standard AppId pipeline.

Command function names define the namespace path (obb.wmshare.<name>), so
they are declared explicitly rather than generated in a loop. NOTE: no
``from __future__ import annotations`` here — OpenBB's signature inspector
compares annotation objects, and PEP 563 string annotations fail it.
"""

from openbb_core.app.model.command_context import CommandContext
from openbb_core.app.model.obbject import OBBject
from openbb_core.app.provider_interface import (
    ExtraParams,
    ProviderChoices,
    StandardParams,
)
from openbb_core.app.query import Query
from openbb_core.app.router import Router

router = Router(prefix="", description="wmshare-exclusive A-share surfaces.")


@router.command(model="WmshareScreener")
async def screener(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Screen the whole A-share market with one XS expression over $codes."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="WmshareIndexValuationTrend")
async def index_valuation_trend(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Weekly whole-building index PE/PB series with window percentiles."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="WmshareMoneyflow")
async def moneyflow(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Daily money-flow tiers (extra-large / large / medium / small orders)."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="WmshareMargin")
async def margin(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Daily margin-trading financing and securities-lending balances."""
    return await OBBject.from_query(Query(**locals()))


@router.command(model="WmshareCbondBoard")
async def cbond_board(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
) -> OBBject:
    """Convertible-bond board snapshot (server-precomputed, ~1000 rows)."""
    return await OBBject.from_query(Query(**locals()))
