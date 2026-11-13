"""Symbol parsing between OpenBB conventions and wmshare market codes.

wmshare is market-scoped: a ``Client(market="cn"|"hk"|"us")`` only answers for
that market, and the code format differs per market (6-digit A-share, 5-digit
HK, bare ticker for US). OpenBB passes a single ``symbol`` string, so every
fetcher needs the same normalisation first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Market = Literal["cn", "hk", "us"]

MARKETS: tuple[Market, ...] = ("cn", "hk", "us")

_CN_SUFFIXES = ("SH", "SS", "SZ", "BJ")
_HK_SUFFIXES = ("HK",)
_US_SUFFIXES = ("US", "O", "N", "A", "K", "P", "OQ", "NQ")

_INDEX_PREFIX = "index."
_INDEX_NAMESPACE = "index"

_SUFFIX_MARKET: dict[str, Market] = {
    **dict.fromkeys(_CN_SUFFIXES, "cn"),
    **dict.fromkeys(_HK_SUFFIXES, "hk"),
    **dict.fromkeys(_US_SUFFIXES, "us"),
}

_CN_CODE = re.compile(r"^\d{6}$")
_HK_CODE = re.compile(r"^\d{1,5}$")
_US_CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z])?$")


@dataclass(frozen=True)
class ParsedSymbol:
    """A symbol resolved to its wmshare market and lookup code."""

    market: Market
    code: str
    """Code as wmshare expects it (``600519``, ``00700``, ``AAPL``)."""

    @property
    def canonical(self) -> str:
        """Unambiguous display form: ``600519.SH`` / ``00700.HK`` / ``AAPL``."""
        if self.market == "cn":
            return f"{self.code}.{_cn_exchange(self.code)}"
        if self.market == "hk":
            return f"{self.code}.HK"
        return self.code


def _cn_exchange(code: str) -> str:
    """Infer the A-share exchange suffix from the code prefix."""
    if code.startswith(("5", "6", "9")):
        return "SH"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def parse_symbol(raw: str, default_market: Market = "cn") -> ParsedSymbol:
    """Resolve an OpenBB symbol string into ``(market, wmshare code)``.

    Accepts ``600519``, ``600519.SH``, ``600519.SS``, ``sh.600519``,
    ``00700.HK``, ``700.HK``, ``AAPL``, ``AAPL.US`` and ``BRK.B``.

    Resolution order: explicit suffix, then code shape, then ``default_market``.
    Shape is checked before the default because the three markets never collide
    — A-share codes are exactly 6 digits, HK codes are 1-5 digits, and US codes
    start with a letter — so ``AAPL`` resolves to ``us`` even inside an A-share
    call, and a caller-supplied market can never silently mangle it.
    """
    if not raw or not str(raw).strip():
        raise ValueError("Symbol cannot be empty.")

    text = str(raw).strip()
    if text.lower().startswith(_INDEX_PREFIX):
        raise ValueError(f"{raw!r} is an index key; use the index endpoints instead.")

    # Strip wmshare/OpenBB prefixes such as ``sh.600519`` or ``cn.000001``.
    text = re.sub(r"^(?:cn|sh|sz|bj|hk|us)\.", "", text, flags=re.IGNORECASE)

    base, _, suffix = text.rpartition(".")
    if base and suffix.upper() in _SUFFIX_MARKET:
        return _finalize(base, _SUFFIX_MARKET[suffix.upper()])

    if base:
        # ``BRK.B``: a class-share separator, not an exchange suffix.
        merged = f"{base}_{suffix.upper()}"
        if _US_CODE.match(merged):
            return _finalize(merged, "us")
        raise ValueError(
            f"Unrecognised symbol {raw!r}. Supported suffixes: "
            ".SH/.SZ/.BJ (A-share), .HK, .US (and .O/.N/.OQ style US venues)."
        )

    return _finalize(text, _infer_market(text, default_market))


def _infer_market(code: str, default_market: Market) -> Market:
    """Pick the market a bare code belongs to; ``default_market`` is the last resort."""
    text = code.strip()
    if text.isdigit():
        if len(text) == 6:
            return "cn"
        if 1 <= len(text) <= 5:
            return "hk"
        return default_market
    if text[:1].isalpha():
        return "us"
    return default_market


def _finalize(text: str, market: Market) -> ParsedSymbol:
    code = text.strip().upper()
    if market == "cn":
        if not code.isdigit():
            raise ValueError(f"A-share symbol {text!r} must be numeric.")
        return ParsedSymbol("cn", code.zfill(6))
    if market == "hk":
        if not _HK_CODE.match(code):
            raise ValueError(f"Hong Kong symbol {text!r} must be 1-5 digits.")
        return ParsedSymbol("hk", code.zfill(5))
    if not _US_CODE.match(code):
        raise ValueError(f"US symbol {text!r} must start with a letter.")
    return ParsedSymbol("us", code)


def resolve_market(raw: str, default_market: Market = "cn") -> Market:
    """Return only the market for a symbol (convenience wrapper)."""
    return parse_symbol(raw, default_market).market


def split_symbols(raw: str) -> list[str]:
    """Split OpenBB's comma-separated multi-symbol form, dropping blanks."""
    return [part.strip() for part in str(raw or "").split(",") if part.strip()]


def market_for_indices(market: Market | None = None) -> Market:
    """Index endpoints are A-share only; fail loudly rather than return nothing."""
    resolved: Market = market or "cn"
    if resolved != "cn":
        raise ValueError(
            f"wmshare index data covers A-share indices only; got market={resolved!r}."
        )
    return resolved


def normalize_index_key(raw: str) -> str:
    """Normalise an index key to wmshare's ``index.xxx`` form.

    ``hs300``, ``HS300`` and ``index.hs300`` all resolve to ``index.hs300``.
    OpenBB's standard validators upper-case the symbol, so the ``index.``
    namespace is lower-cased here; keys in another namespace
    (``industry.S11``) keep their original casing because the segment after the
    dot is case-sensitive upstream.
    """
    text = str(raw or "").strip()
    if not text:
        raise ValueError("Index key cannot be empty.")

    prefix, _, rest = text.partition(".")
    if not rest:
        return f"{_INDEX_PREFIX}{prefix.lower()}"
    if prefix.lower() == _INDEX_NAMESPACE:
        return f"{_INDEX_PREFIX}{rest.lower()}"
    return text
