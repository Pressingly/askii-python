"""Tests for the in-memory TTL + LRU cache."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from askii import InMemoryCache, build_cache_key, build_resource_prefix

# --- sync path -------------------------------------------------------


def test_get_missing_returns_none() -> None:
    cache = InMemoryCache(default_ttl=10)
    assert cache.get("missing") is None


def test_set_get_roundtrip() -> None:
    cache = InMemoryCache(default_ttl=10)
    cache.set("k", {"v": 1}, ttl=10)
    assert cache.get("k") == {"v": 1}


def test_ttl_zero_is_no_op(fixed_clock: Callable[[float], None]) -> None:
    cache = InMemoryCache(default_ttl=0)
    cache.set("k", "v", ttl=0)
    assert cache.get("k") is None


def test_ttl_expiry(fixed_clock: Callable[[float], None]) -> None:
    cache = InMemoryCache(default_ttl=0)
    cache.set("k", "v", ttl=5)
    fixed_clock(4.9)
    assert cache.get("k") == "v"
    fixed_clock(0.2)
    assert cache.get("k") is None


def test_lru_eviction() -> None:
    cache = InMemoryCache(maxsize=3, default_ttl=10)
    cache.set("a", 1, ttl=10)
    cache.set("b", 2, ttl=10)
    cache.set("c", 3, ttl=10)
    # Touch "a" so "b" becomes the LRU victim.
    assert cache.get("a") == 1
    cache.set("d", 4, ttl=10)
    assert cache.get("b") is None
    assert cache.get("a") == 1


def test_delete() -> None:
    cache = InMemoryCache(default_ttl=10)
    cache.set("k", "v", ttl=10)
    cache.delete("k")
    assert cache.get("k") is None


def test_delete_prefix_removes_matching_keys() -> None:
    cache = InMemoryCache(default_ttl=10)
    cache.set("askii:v1:abc:keys:list", "x", ttl=10)
    cache.set("askii:v1:abc:keys:get_config", "y", ttl=10)
    cache.set("askii:v1:abc:models:list", "z", ttl=10)
    cache.delete_prefix("askii:v1:abc:keys")
    assert cache.get("askii:v1:abc:keys:list") is None
    assert cache.get("askii:v1:abc:keys:get_config") is None
    assert cache.get("askii:v1:abc:models:list") == "z"


def test_clear() -> None:
    cache = InMemoryCache(default_ttl=10)
    cache.set("a", 1, ttl=10)
    cache.set("b", 2, ttl=10)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None


def test_maxsize_zero_rejected() -> None:
    with pytest.raises(ValueError):
        InMemoryCache(maxsize=0)


# --- async path ------------------------------------------------------


async def test_aget_aset_roundtrip() -> None:
    cache = InMemoryCache(default_ttl=10)
    await cache.aset("k", "v", ttl=10)
    assert await cache.aget("k") == "v"


async def test_aset_ttl_zero_is_no_op() -> None:
    cache = InMemoryCache(default_ttl=0)
    await cache.aset("k", "v", ttl=0)
    assert await cache.aget("k") is None


async def test_async_delete_prefix() -> None:
    cache = InMemoryCache(default_ttl=10)
    await cache.aset("askii:v1:u:keys:list", "x", ttl=10)
    await cache.aset("askii:v1:u:keys:get", "y", ttl=10)
    await cache.adelete_prefix("askii:v1:u:keys")
    assert await cache.aget("askii:v1:u:keys:list") is None
    assert await cache.aget("askii:v1:u:keys:get") is None


async def test_async_clear() -> None:
    cache = InMemoryCache(default_ttl=10)
    await cache.aset("a", 1, ttl=10)
    await cache.aclear()
    assert await cache.aget("a") is None


# --- key builders ----------------------------------------------------


def test_build_cache_key_is_deterministic() -> None:
    a = build_cache_key("tok", "keys", "list", None)
    b = build_cache_key("tok", "keys", "list", None)
    assert a == b


def test_build_cache_key_differs_by_args() -> None:
    a = build_cache_key("tok", "keys", "get_config", {"key": "alias-a"})
    b = build_cache_key("tok", "keys", "get_config", {"key": "alias-b"})
    assert a != b


def test_build_cache_key_does_not_leak_token() -> None:
    key = build_cache_key("super-secret-jwt", "keys", "list", None)
    assert "super-secret-jwt" not in key
    assert key.startswith("askii:v1:")


def test_build_resource_prefix_is_per_user() -> None:
    a = build_resource_prefix("user-a", "keys")
    b = build_resource_prefix("user-b", "keys")
    assert a != b
    assert a.endswith(":keys")
