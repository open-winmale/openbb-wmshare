"""Index alias → canonical ``<nnnnnn>.INDEX`` resolution.

wmshare's index bar store is keyed by canonical codes, and the alias mapping is
*not* the intuitive one: ``index.hs300`` is ``399300.INDEX``, **not**
``000300.INDEX`` — the latter is a different index whose series is stale.
Passing an ``index.*`` key straight to ``kline.bars`` returns ``[]``.

The authoritative mapping lives upstream in
``airflow/catalog/index_registry_live.json`` (``canon`` section). A snapshot
ships with this package via ``_index_canon.json`` so the provider works
standalone; :mod:`tools.refresh_index_canon` regenerates it.

Resolution order:
1. an already-canonical ``<digits>.INDEX`` code passes through unchanged;
2. a bare alias (``hs300``) or an ``index.hs300`` key is looked up in the table;
3. anything else returns ``None`` so callers can fail with a precise message
   rather than silently returning an empty series.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from typing import Any

_CANON_FILE = "_index_canon.json"
_CANONICAL_RE = re.compile(r"^\d{6}\.INDEX$", re.IGNORECASE)
_INDEX_KEY_PREFIX = "index."


@lru_cache(maxsize=1)
def _table() -> dict[str, str]:
    """Load the packaged alias table once."""
    try:
        raw = resources.files(__package__).joinpath(_CANON_FILE).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return {}
    payload: Any = json.loads(raw)
    canon = payload.get("canon") if isinstance(payload, dict) else None
    if not isinstance(canon, dict):
        return {}
    return {
        str(alias).strip().lower(): str(code).strip().upper()
        for alias, code in canon.items()
        if str(alias).strip() and str(code).strip()
    }


def canon_asof() -> str | None:
    """Date of the packaged alias snapshot, for diagnostics."""
    try:
        raw = resources.files(__package__).joinpath(_CANON_FILE).read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    payload = json.loads(raw)
    asof = payload.get("asof") if isinstance(payload, dict) else None
    return str(asof) if asof else None


def resolve_index_canonical(key: str) -> str | None:
    """Map an index key onto the canonical code the bar store is keyed by.

    ``"index.hs300"`` and ``"hs300"`` both yield ``"399300.INDEX"``;
    ``"399300.INDEX"`` passes through. ``"industry.S11"`` returns ``None``,
    because industry valuation keys are not index bar series.
    """
    text = str(key or "").strip()
    if not text:
        return None

    if _CANONICAL_RE.match(text):
        return text.upper()

    lower = text.lower()
    if lower.startswith(_INDEX_KEY_PREFIX):
        lower = lower[len(_INDEX_KEY_PREFIX) :]

    return _table().get(lower)


@lru_cache(maxsize=1)
def reverse_table() -> dict[str, str]:
    """Canonical code → user-facing ``index.*`` key.

    Upstream payloads (e.g. ``kline.query_index_last_live_many``) are keyed by
    canonical code; this re-keys them for output. The packaged snapshot is
    1:1, so the first matching alias is deterministic; if upstream ever ships
    duplicate aliases the alphabetically first wins to keep output stable.
    """
    out: dict[str, str] = {}
    for alias, code in sorted(_table().items()):
        out.setdefault(code, f"{_INDEX_KEY_PREFIX}{alias}")
    return out


def is_canonical_index_code(key: str) -> bool:
    """Whether ``key`` is already a canonical ``<digits>.INDEX`` code."""
    return bool(_CANONICAL_RE.match(str(key or "").strip()))


def alias_count() -> int:
    """Number of aliases in the packaged table (diagnostics / tests)."""
    return len(_table())
