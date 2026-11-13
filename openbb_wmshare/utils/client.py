"""wmshare client construction, error mapping and sync→async bridging.

Two rules drive this module:

* ``wmshare`` is a synchronous ``requests`` SDK. Fetchers run on the event
  loop, so every call goes through :func:`run_sync` (``asyncio.to_thread``).
* ``import wmshare`` pulls in the bundled catalog. Keep it inside functions so
  ``import openbb`` stays fast.

Credentials arrive already filtered by OpenBB's query executor as
``{"wmshare_client_id": ..., "wmshare_client_secret": ...}``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from functools import lru_cache
from typing import Any, TypeVar

from openbb_core.provider.utils.errors import (
    EmptyDataError,
    OpenBBError,
    UnauthorizedError,
)

from openbb_wmshare.utils.symbols import Market

T = TypeVar("T")

CLIENT_ID_KEY = "wmshare_client_id"
CLIENT_SECRET_KEY = "wmshare_client_secret"

CREDENTIALS_OPTIONAL = True
"""wmshare credentials are declared on the ``Provider`` but not enforced by OpenBB.

The wmshare SDK already resolves credentials from three places
(``WMSHARE_CLIENT_ID``/``WMSHARE_CLIENT_SECRET``, ``~/.wmshare/credentials.env``,
and explicit constructor arguments). Making OpenBB a fourth gatekeeper would
break every user who configured credentials the SDK way, and the SDK's own
``AuthError`` is more actionable. So every fetcher sets
``require_credentials = False`` and the check happens on the first real call.
"""


def _credentials(credentials: dict[str, str] | None) -> tuple[str | None, str | None]:
    if not credentials:
        return None, None
    return credentials.get(CLIENT_ID_KEY), credentials.get(CLIENT_SECRET_KEY)


def build_client(
    market: Market = "cn",
    credentials: dict[str, str] | None = None,
    *,
    max_limit: int | None = None,
) -> Any:
    """Create a wmshare ``Client`` for one market.

    Falls back to ``Client.from_env()`` when OpenBB supplied no credentials so
    that users who configured ``~/.wmshare/credentials.env`` or environment
    variables keep working.
    """
    from wmshare import Client

    client_id, client_secret = _credentials(credentials)
    if client_id and client_secret:
        kwargs: dict[str, Any] = {
            "market": market,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if max_limit is not None:
            kwargs["max_limit"] = max_limit
        return Client(**kwargs)

    client = Client.from_env(market=market, **({"max_limit": max_limit} if max_limit else {}))
    return client


@lru_cache(maxsize=8)
def _cached_client(market: Market, client_id: str, client_secret: str) -> Any:
    """Reuse one client per (market, credentials) pair across fetches.

    wmshare keeps an OAuth token on the client instance, so rebuilding it per
    call would re-authenticate on every request. Credential values are part of
    the key so a rotated secret gets a fresh client.
    """
    from wmshare import Client

    return Client(market=market, client_id=client_id, client_secret=client_secret)


def get_client(market: Market = "cn", credentials: dict[str, str] | None = None) -> Any:
    """Return a reusable client, or build an uncached one from the environment."""
    client_id, client_secret = _credentials(credentials)
    if client_id and client_secret:
        return _cached_client(market, client_id, client_secret)
    return build_client(market, credentials)


def clear_client_cache() -> None:
    """Drop cached clients (test hook)."""
    _cached_client.cache_clear()


async def run_sync(func: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a blocking wmshare call off the event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)


def translate_error(exc: Exception, context: str = "") -> Exception:
    """Map wmshare exceptions onto the OpenBB error types the REST layer understands.

    Already-OpenBB errors pass through untouched so nested helpers do not
    double-wrap them.
    """
    from wmshare.errors import (
        ApiError,
        AuthError,
        DataError,
        LimitError,
        QuotaError,
        ServerError,
        TransportError,
        UsageError,
    )

    prefix = f"{context}: " if context else ""
    message = f"{prefix}{exc}"

    if isinstance(exc, (EmptyDataError, OpenBBError, UnauthorizedError, ValueError)):
        return exc
    if isinstance(exc, AuthError):
        return UnauthorizedError(
            f"{message}\nCheck wmshare_client_id / wmshare_client_secret, or the "
            "WMSHARE_CLIENT_ID / WMSHARE_CLIENT_SECRET environment variables."
        )
    if isinstance(exc, QuotaError):
        return OpenBBError(
            f"{message}\nThis request exceeded the wmshare quota (EC) for the billing period; "
            "narrow the date range or wait for the quota to reset."
        )
    if isinstance(exc, LimitError):
        return OpenBBError(
            f"{message}\nNarrow the request (shorter range, fewer symbols, smaller limit)."
        )
    if isinstance(exc, UsageError):
        return OpenBBError(f"{message}\nCheck the provider parameters for this command.")
    if isinstance(exc, DataError):
        return OpenBBError(
            f"{message}\nwmshare's data guards rejected the payload as implausible; "
            "this is an upstream data issue, please report it."
        )
    if isinstance(exc, (ServerError, TransportError, ApiError)):
        return OpenBBError(f"{message}\nUpstream wmshare service error; retry later.")
    return OpenBBError(message)


async def call(
    func: Callable[..., T],
    /,
    *args: Any,
    context: str = "",
    **kwargs: Any,
) -> T:
    """Invoke a blocking wmshare callable with error translation applied."""
    try:
        return await run_sync(func, *args, **kwargs)
    except Exception as exc:
        raise translate_error(exc, context) from exc


def require_rows(rows: Any, context: str = "") -> list[dict]:
    """Coerce wmshare output to a list of dicts, raising ``EmptyDataError`` when empty."""
    if rows is None:
        raise EmptyDataError(f"{context}: no data returned." if context else "No data returned.")
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or not rows:
        raise EmptyDataError(f"{context}: no data returned." if context else "No data returned.")
    return [row for row in rows if isinstance(row, dict)]
