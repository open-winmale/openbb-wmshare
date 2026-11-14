"""wmshare Index Snapshots model.

One batched request (`kline.query_index_last_live_many`) covers every key, so
the default fetch is the whole A-share index universe. Upstream keys the
payload by canonical code (`399300.INDEX`); rows are re-keyed to the
`index.hs300` form every other endpoint in this provider uses.

Caliber notes (verified live 2026-11-14): the live snapshot's `percent` is a
normalized decimal like equity bars — unlike the index *bar* store, where it
is a percentage number (BUGS.md D-2). There is no `prev_close` field; it is
derived from `close - change` so downstream consumers do not have to.
"""

from __future__ import annotations

from typing import Any, Literal

from openbb_core.provider.abstract.fetcher import Fetcher
from openbb_core.provider.standard_models.index_snapshots import (
    IndexSnapshotsData,
    IndexSnapshotsQueryParams,
)
from pydantic import Field

from openbb_wmshare.utils import (
    alias_for_canonical,
    call,
    get_client,
    index_name,
    require_rows,
)


class WmshareIndexSnapshotsQueryParams(IndexSnapshotsQueryParams):
    """wmshare Index Snapshots Query.

    Source: https://github.com/open-winmale/wmshare
    """

    region: Literal["cn", "us"] = Field(
        default="cn",
        description="Informational only: wmshare publishes A-share indices, so the "
        "output is always the cn universe regardless of this value. 'us' is "
        "accepted because it is the command-level default of the standard model.",
    )


class WmshareIndexSnapshotsData(IndexSnapshotsData):
    """wmshare Index Snapshots Data."""

    amount: float | None = Field(default=None, description="Turnover (notional value traded).")
    turnover_rate: float | None = Field(
        default=None,
        description="Turnover rate, as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    amplitude: float | None = Field(
        default=None,
        description="Intraday amplitude (high-low over prev close), as a normalized percent.",
        json_schema_extra={"x-unit_measurement": "percent", "x-frontend_multiply": 100},
    )
    asof: str | None = Field(default=None, description="Timestamp of the last quote refresh.")


class WmshareIndexSnapshotsFetcher(
    Fetcher[WmshareIndexSnapshotsQueryParams, list[WmshareIndexSnapshotsData]]
):
    """wmshare Index Snapshots Fetcher."""

    require_credentials = False

    @staticmethod
    def transform_query(params: dict[str, Any]) -> WmshareIndexSnapshotsQueryParams:
        """Pass the query through unchanged."""
        return WmshareIndexSnapshotsQueryParams(**params)

    @staticmethod
    async def aextract_data(
        query: WmshareIndexSnapshotsQueryParams,
        credentials: dict[str, str] | None,
        **kwargs: Any,
    ) -> list[dict]:
        """Snapshot the whole index universe in a single batched request."""
        from openbb_wmshare.utils.index_canon import resolve_index_canonical
        from openbb_wmshare.utils.index_universe import all_index_keys, index_keys_only

        keys = index_keys_only(await all_index_keys(credentials))
        canonicals = [resolve_index_canonical(key) for key in keys]
        payload = [code for code in canonicals if code]

        client = get_client("cn", credentials)
        snapshots = await call(
            client.call,
            "kline.query_index_last_live_many",
            keys=payload,
            context="kline.query_index_last_live_many",
        )

        rows: list[dict] = []
        by_canon = snapshots if isinstance(snapshots, dict) else {}
        for canon, snap in by_canon.items():
            if not isinstance(snap, dict):
                continue
            rows.append(_to_snapshot_row(canon, snap))
        return rows

    @staticmethod
    def transform_data(
        query: WmshareIndexSnapshotsQueryParams,
        data: list[dict],
        **kwargs: Any,
    ) -> list[WmshareIndexSnapshotsData]:
        """Validate the snapshot rows."""
        return [WmshareIndexSnapshotsData.model_validate(row) for row in require_rows(data)]


def _to_snapshot_row(canonical: str, snap: dict) -> dict:
    """Normalise one live snapshot onto OpenBB's schema, re-keyed to the alias."""
    close, change = snap.get("close"), snap.get("change")
    row: dict[str, Any] = {
        "symbol": alias_for_canonical(canonical) or canonical,
        "name": index_name(alias_for_canonical(canonical) or canonical),
        "currency": "CNY",
        "price": close,
        "open": snap.get("open"),
        "high": snap.get("high"),
        "low": snap.get("low"),
        "close": close,
        "volume": snap.get("volume"),
        "change": change,
        "change_percent": snap.get("percent"),
        "amount": snap.get("amount"),
        "turnover_rate": snap.get("turnover_rate"),
        "amplitude": snap.get("amplitude"),
        "asof": snap.get("refreshed_at") or snap.get("asof"),
        "last_timestamp": snap.get("date"),
    }
    if isinstance(close, int | float) and isinstance(change, int | float):
        row["prev_close"] = round(close - change, 6)
    return row
