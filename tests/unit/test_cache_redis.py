"""Tests for the Redis cache backend (skipped unless fakeredis is installed)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest


def test_redis_cache_requires_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """RedisCache raises a helpful error if the redis dependency is absent.

    We simulate the missing extra by stashing real ``redis`` then restoring it.
    """
    import importlib
    import sys

    # Force fresh import; pretend redis is missing.
    monkeypatch.setitem(sys.modules, "redis", None)
    sys.modules.pop("askii._cache.redis", None)
    try:
        with pytest.raises((RuntimeError, ImportError)):
            from askii._cache.redis import RedisCache  # noqa: F401

            RedisCache(url="redis://localhost:6379/0")
    finally:
        monkeypatch.delitem(sys.modules, "redis", raising=False)
        importlib.invalidate_caches()


@pytest.fixture
def redis_cache(fakeredis_clients: tuple[Any, Any]) -> Iterator[Any]:
    from askii._cache.redis import RedisCache

    sync, aio = fakeredis_clients
    yield RedisCache(namespace="askii", sync_client=sync, async_client=aio)


def test_redis_set_get_roundtrip_sync(redis_cache: Any) -> None:
    redis_cache.set("askii:v1:u:keys:list", {"a": 1}, ttl=30)
    assert redis_cache.get("askii:v1:u:keys:list") == {"a": 1}


def test_redis_get_missing_returns_none(redis_cache: Any) -> None:
    assert redis_cache.get("nope") is None


def test_redis_set_ttl_zero_is_no_op(redis_cache: Any) -> None:
    redis_cache.set("k", "v", ttl=0)
    assert redis_cache.get("k") is None


def test_redis_delete(redis_cache: Any) -> None:
    redis_cache.set("k", "v", ttl=30)
    redis_cache.delete("k")
    assert redis_cache.get("k") is None


def test_redis_delete_prefix_removes_matching(redis_cache: Any) -> None:
    redis_cache.set("askii:v1:u:keys:list", "a", ttl=30)
    redis_cache.set("askii:v1:u:keys:get", "b", ttl=30)
    redis_cache.set("askii:v1:u:models:list", "c", ttl=30)
    redis_cache.delete_prefix("askii:v1:u:keys")
    assert redis_cache.get("askii:v1:u:keys:list") is None
    assert redis_cache.get("askii:v1:u:keys:get") is None
    assert redis_cache.get("askii:v1:u:models:list") == "c"


def test_redis_clear_requires_namespace(fakeredis_clients: tuple[Any, Any]) -> None:
    from askii._cache.redis import RedisCache

    sync, aio = fakeredis_clients
    cache = RedisCache(sync_client=sync, async_client=aio)
    with pytest.raises(RuntimeError):
        cache.clear()


async def test_redis_async_roundtrip(redis_cache: Any) -> None:
    await redis_cache.aset("k", {"a": 1}, ttl=30)
    assert await redis_cache.aget("k") == {"a": 1}


async def test_redis_async_delete_prefix(redis_cache: Any) -> None:
    await redis_cache.aset("askii:v1:u:keys:list", "x", ttl=30)
    await redis_cache.aset("askii:v1:u:models:list", "y", ttl=30)
    await redis_cache.adelete_prefix("askii:v1:u:keys")
    assert await redis_cache.aget("askii:v1:u:keys:list") is None
    assert await redis_cache.aget("askii:v1:u:models:list") == "y"


async def test_redis_async_clear_requires_namespace(fakeredis_clients: tuple[Any, Any]) -> None:
    from askii._cache.redis import RedisCache

    sync, aio = fakeredis_clients
    cache = RedisCache(sync_client=sync, async_client=aio)
    with pytest.raises(RuntimeError):
        await cache.aclear()


def test_redis_cache_requires_some_arg() -> None:
    pytest.importorskip("fakeredis")
    from askii._cache.redis import RedisCache

    with pytest.raises(ValueError):
        RedisCache()
