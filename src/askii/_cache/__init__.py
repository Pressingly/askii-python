"""Pluggable cache layer for the askii client.

The :class:`Cache` Protocol covers both sync and async paths so a single backend
instance can serve both :class:`askii.Askii` and :class:`askii.AsyncAskii`.

Two backends ship in-box:

* :class:`askii._cache.memory.InMemoryCache` — always available.
* :class:`askii._cache.redis.RedisCache` — requires the ``[redis]`` extra.

Cache keys are built by :func:`build_cache_key` so all backends agree on the
shape: ``askii:v1:{user_hash}:{resource}:{op}:{args_hash}``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol, runtime_checkable

CACHE_VERSION = "v1"
CACHE_PREFIX = "askii"


@runtime_checkable
class Cache(Protocol):
    """A cache that supports both synchronous and asynchronous access.

    Implementations must be safe to share between threads and event loops.
    A ``ttl`` of zero (or less) must be treated as a no-op for writes.
    """

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, *, ttl: float) -> None: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> None: ...
    def clear(self) -> None: ...

    async def aget(self, key: str) -> Any | None: ...
    async def aset(self, key: str, value: Any, *, ttl: float) -> None: ...
    async def adelete(self, key: str) -> None: ...
    async def adelete_prefix(self, prefix: str) -> None: ...
    async def aclear(self) -> None: ...


def _hash8(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _canonical_args(args: dict[str, Any] | None) -> str:
    if not args:
        return ""
    return json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)


def build_user_prefix(token: str) -> str:
    """Per-user namespace prefix; never contains the token itself."""
    return f"{CACHE_PREFIX}:{CACHE_VERSION}:{_hash8(token)}"


def build_resource_prefix(token: str, resource: str) -> str:
    """Per-resource prefix for bulk invalidation."""
    return f"{build_user_prefix(token)}:{resource}"


def build_cache_key(
    token: str,
    resource: str,
    op: str,
    args: dict[str, Any] | None = None,
) -> str:
    """Build a stable cache key for one resource operation."""
    args_hash = _hash8(_canonical_args(args)) if args else "noargs"
    return f"{build_resource_prefix(token, resource)}:{op}:{args_hash}"


__all__ = [
    "Cache",
    "CACHE_PREFIX",
    "CACHE_VERSION",
    "build_cache_key",
    "build_resource_prefix",
    "build_user_prefix",
]
