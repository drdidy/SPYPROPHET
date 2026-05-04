from __future__ import annotations

import logging
import time
from collections.abc import Callable
from threading import Lock
from typing import TypeVar

from spyprophet_core.secrets import read_secret
from tastytrade_provider import TastytradeProvider

logger = logging.getLogger("spyprophet.api")

TASTYTRADE_SECRET_KEYS = (
    "TASTYTRADE_CLIENT_ID",
    "TASTYTRADE_CLIENT_SECRET",
    "TASTYTRADE_REFRESH_TOKEN",
)


def missing_tastytrade_secrets() -> list[str]:
    return [k for k in TASTYTRADE_SECRET_KEYS if not read_secret(k)]


def tastytrade_configured() -> bool:
    return not missing_tastytrade_secrets()


_provider_singleton: TastytradeProvider | None = None
_provider_lock = Lock()


def get_tastytrade_provider() -> TastytradeProvider | None:
    """Return a process-wide TastytradeProvider, or None if secrets are missing.

    Single instance per process so the OAuth refresh-token rotation tracked in
    ``TastytradeProvider.refresh_token_rotated`` actually persists between
    requests instead of resetting on every call.
    """
    global _provider_singleton
    if missing_tastytrade_secrets():
        return None
    if _provider_singleton is not None:
        return _provider_singleton
    with _provider_lock:
        if _provider_singleton is not None:
            return _provider_singleton
        _provider_singleton = TastytradeProvider(
            client_id=read_secret("TASTYTRADE_CLIENT_ID"),
            client_secret=read_secret("TASTYTRADE_CLIENT_SECRET"),
            refresh_token=read_secret("TASTYTRADE_REFRESH_TOKEN"),
            environment=read_secret("TASTYTRADE_ENVIRONMENT") or "production",
        )
    return _provider_singleton


def reset_provider_for_tests() -> None:
    global _provider_singleton
    with _provider_lock:
        _provider_singleton = None


T = TypeVar("T")


class TTLCache:
    """Tiny per-key TTL cache. We use it to keep upstream fetch volume sane
    when many concurrent API requests arrive — yfinance and Tastytrade both
    have rate limits we don't want to brush against."""

    def __init__(self, default_ttl: float = 30.0):
        self._default_ttl = default_ttl
        self._lock = Lock()
        self._store: dict[str, tuple[float, object]] = {}

    def get_or_compute(self, key: str, compute: Callable[[], T], ttl: float | None = None) -> T:
        ttl = self._default_ttl if ttl is None else ttl
        now = time.monotonic()
        with self._lock:
            cached = self._store.get(key)
            if cached and cached[0] > now:
                return cached[1]  # type: ignore[return-value]
        value = compute()
        with self._lock:
            self._store[key] = (now + ttl, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


_global_cache = TTLCache(default_ttl=30.0)


def get_cache() -> TTLCache:
    return _global_cache
