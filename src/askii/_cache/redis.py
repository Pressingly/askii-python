"""Redis-backed cache. Requires the ``[redis]`` install extra.

Values are JSON-encoded so any consumer can read them regardless of language,
and so a poisoned cache cannot execute arbitrary Python (no pickle).
"""

from __future__ import annotations

import json
from typing import Any


class RedisCache:
    """A :class:`askii._cache.Cache`-shaped wrapper over a real Redis client.

    Pass either a connection URL (and we'll build the clients) or pre-built
    sync + async clients. The namespace prefix is added to every key so a
    single Redis instance can serve multiple services without collision.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        namespace: str = "",
        sync_client: Any = None,
        async_client: Any = None,
        scan_count: int = 500,
    ) -> None:
        try:
            import redis as _redis
            import redis.asyncio as _aredis
        except ImportError as exc:  # pragma: no cover — exercised by integration
            raise RuntimeError(
                "RedisCache requires the optional 'redis' extra. Install with: pip install 'askii[redis]'"
            ) from exc

        if sync_client is None and async_client is None and url is None:
            raise ValueError("Provide a redis URL or pre-built clients")

        self._sync: Any = sync_client if sync_client is not None else _redis.Redis.from_url(url or "")
        self._async: Any = async_client if async_client is not None else _aredis.Redis.from_url(url or "")
        self._ns = namespace.rstrip(":") + ":" if namespace else ""
        self._scan_count = scan_count

    # --- sync ---------------------------------------------------------

    def get(self, key: str) -> Any | None:
        raw = self._sync.get(self._k(key))
        return _decode(raw)

    def set(self, key: str, value: Any, *, ttl: float) -> None:
        if ttl <= 0:
            return
        self._sync.set(self._k(key), _encode(value), ex=max(1, int(ttl)))

    def delete(self, key: str) -> None:
        self._sync.delete(self._k(key))

    def delete_prefix(self, prefix: str) -> None:
        pattern = self._k(prefix) + "*"
        for key in self._sync.scan_iter(match=pattern, count=self._scan_count):
            self._sync.delete(key)

    def clear(self) -> None:
        if not self._ns:
            raise RuntimeError("Refusing to FLUSH a shared Redis without a namespace")
        self.delete_prefix("")

    # --- async --------------------------------------------------------

    async def aget(self, key: str) -> Any | None:
        raw = await self._async.get(self._k(key))
        return _decode(raw)

    async def aset(self, key: str, value: Any, *, ttl: float) -> None:
        if ttl <= 0:
            return
        await self._async.set(self._k(key), _encode(value), ex=max(1, int(ttl)))

    async def adelete(self, key: str) -> None:
        await self._async.delete(self._k(key))

    async def adelete_prefix(self, prefix: str) -> None:
        pattern = self._k(prefix) + "*"
        async for key in self._async.scan_iter(match=pattern, count=self._scan_count):
            await self._async.delete(key)

    async def aclear(self) -> None:
        if not self._ns:
            raise RuntimeError("Refusing to FLUSH a shared Redis without a namespace")
        await self.adelete_prefix("")

    # --- internals ----------------------------------------------------

    def _k(self, key: str) -> str:
        return f"{self._ns}{key}"


def _encode(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")


def _decode(raw: bytes | str | None) -> Any | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


__all__ = ["RedisCache"]
