"""In-process TTL + LRU cache. Default backend; always available."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import OrderedDict
from typing import Any

DEFAULT_MAXSIZE = 1024


class InMemoryCache:
    """Thread- and asyncio-safe TTL cache with LRU eviction.

    ``ttl<=0`` on :meth:`set` / :meth:`aset` is a no-op — the value is dropped
    rather than stored. This makes ``InMemoryCache(default_ttl=0)`` an
    "off by default" cache, which is the library default.
    """

    def __init__(self, maxsize: int = DEFAULT_MAXSIZE, default_ttl: float = 0.0) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        self._maxsize = maxsize
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._alock = asyncio.Lock()

    # --- sync API -----------------------------------------------------

    def get(self, key: str) -> Any | None:
        with self._lock:
            return self._get_locked(key)

    def set(self, key: str, value: Any, *, ttl: float) -> None:
        effective_ttl = ttl if ttl > 0 else self._default_ttl
        if effective_ttl <= 0:
            return
        expiry = time.monotonic() + effective_ttl
        with self._lock:
            self._set_locked(key, value, expiry)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [k for k in self._store if k.startswith(prefix)]:
                del self._store[key]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    # --- async API ----------------------------------------------------

    async def aget(self, key: str) -> Any | None:
        async with self._alock:
            with self._lock:
                return self._get_locked(key)

    async def aset(self, key: str, value: Any, *, ttl: float) -> None:
        effective_ttl = ttl if ttl > 0 else self._default_ttl
        if effective_ttl <= 0:
            return
        expiry = time.monotonic() + effective_ttl
        async with self._alock:
            with self._lock:
                self._set_locked(key, value, expiry)

    async def adelete(self, key: str) -> None:
        async with self._alock:
            self.delete(key)

    async def adelete_prefix(self, prefix: str) -> None:
        async with self._alock:
            self.delete_prefix(prefix)

    async def aclear(self) -> None:
        async with self._alock:
            self.clear()

    # --- internals ----------------------------------------------------

    def _get_locked(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expiry, value = entry
        if expiry < time.monotonic():
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return value

    def _set_locked(self, key: str, value: Any, expiry: float) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (expiry, value)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)


__all__ = ["InMemoryCache", "DEFAULT_MAXSIZE"]
