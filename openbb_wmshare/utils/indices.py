"""Display metadata for wmshare index keys.

``cli.index.keys()`` returns bare keys such as ``index.hs300`` with no Chinese or
English name. OpenBB's ``IndexSearch`` / ``AvailableIndices`` models both
require a ``name``, so the well-known broad indices are named here and unknown
keys fall back to a title-cased form of the key itself.
"""

from __future__ import annotations

INDEX_NAMES: dict[str, str] = {
    "index.hs300": "CSI 300 Index",
    "index.csi500": "CSI 500 Index",
    "index.sz50": "SSE 50 Index",
    "index.cybz": "ChiNext Index",
    "index.star50": "STAR 50 Index",
    "index.shzs": "SSE Composite Index",
    "index.szcz": "SZSE Component Index",
    "index.szzzs": "SZSE Composite Index",
    "index.zx100": "CSI 100 Index",
    "index.gz2000": "CSI 2000 Index",
    "index.kc200": "STAR 200 Index",
    "index.csidividend": "CSI Dividend Index",
    "index.ssedividend": "SSE Dividend Index",
}

INDEX_NAMES_ZH: dict[str, str] = {
    "index.hs300": "沪深300",
    "index.csi500": "中证500",
    "index.sz50": "上证50",
    "index.cybz": "创业板指",
    "index.star50": "科创50",
    "index.shzs": "上证指数",
    "index.szcz": "深证成指",
    "index.szzzs": "深证综指",
    "index.zx100": "中证100",
    "index.gz2000": "中证2000",
    "index.kc200": "科创200",
    "index.csidividend": "中证红利",
    "index.ssedividend": "上证红利",
}

INDEX_EXCHANGE: dict[str, str] = {
    "index.hs300": "CFFEX",
    "index.csi500": "CFFEX",
    "index.sz50": "SSE",
    "index.cybz": "SZSE",
    "index.star50": "SSE",
    "index.shzs": "SSE",
    "index.szcz": "SZSE",
    "index.szzzs": "SZSE",
    "index.zx100": "CFFEX",
    "index.gz2000": "CFFEX",
    "index.kc200": "SSE",
    "index.csidividend": "CFFEX",
    "index.ssedividend": "SSE",
}


def index_name(key: str) -> str:
    """Human-readable name for an index key, falling back to a prettified key."""
    normalized = key.strip().lower()
    if normalized in INDEX_NAMES:
        return INDEX_NAMES[normalized]
    bare = normalized.split(".", 1)[-1]
    return bare.upper() if len(bare) <= 6 else bare.title()


def index_search_terms(key: str) -> str:
    """Concatenated haystack (key, English and Chinese names) for substring search."""
    normalized = key.strip().lower()
    parts = [normalized, normalized.split(".", 1)[-1]]
    parts.extend(filter(None, [INDEX_NAMES.get(normalized), INDEX_NAMES_ZH.get(normalized)]))
    return " ".join(parts).casefold()


def index_exchange(key: str) -> str | None:
    """Listing venue for an index key, when known."""
    return INDEX_EXCHANGE.get(key.strip().lower())
