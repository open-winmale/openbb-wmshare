"""wmshare index key discovery.

``cli.index.keys()`` returns opaque internal identifiers (``idx_1_0bf8...``), not
the ``index.hs300`` style keys that ``members`` / ``weights`` / ``trend`` accept.
``cli.index.universe_keys()`` returns the real keys, grouped by category, so
that is what index search and availability are built on.
"""

from __future__ import annotations

from openbb_wmshare.utils.client import call, get_client

UNIVERSE_GROUPS: tuple[str, ...] = ("broad", "industry", "dividend")


async def all_index_keys(credentials: dict[str, str] | None) -> list[str]:
    """Return every resolvable index key, sorted and de-duplicated.

    ``universe_keys`` is queried per group because the server-side ``all``
    group is not implemented on every deployment; the union is computed here
    instead so a partial rollout still yields the available keys.
    """
    client = get_client("cn", credentials)
    keys: set[str] = set()

    for group in UNIVERSE_GROUPS:
        try:
            group_keys = await call(
                client.index.universe_keys, group, context=f"index.universe_keys({group})"
            )
        except Exception:
            # A missing group is not fatal: the remaining groups still describe
            # a usable universe.
            continue
        keys.update(str(key) for key in group_keys or [] if str(key).strip())

    return sorted(keys)


def is_stock_index(key: str) -> bool:
    """Whether a key names an index (as opposed to an industry classification)."""
    return key.startswith("index.")


def index_keys_only(keys: list[str]) -> list[str]:
    """Filter a key list down to real indices."""
    return [key for key in keys if is_stock_index(key)]
