"""Tests for the token resolver factories."""

from __future__ import annotations

import pytest

from askii import AskiiAuthError
from askii._token import make_async_resolver, make_sync_resolver

# --- async resolver --------------------------------------------------


async def test_async_resolver_from_static_string() -> None:
    resolver = make_async_resolver("jwt-abc")
    assert await resolver() == "jwt-abc"


async def test_async_resolver_from_sync_callable() -> None:
    counter = {"n": 0}

    def provider() -> str:
        counter["n"] += 1
        return f"jwt-{counter['n']}"

    resolver = make_async_resolver(provider)
    assert await resolver() == "jwt-1"
    assert await resolver() == "jwt-2"


async def test_async_resolver_from_async_callable() -> None:
    async def provider() -> str:
        return "jwt-async"

    resolver = make_async_resolver(provider)
    assert await resolver() == "jwt-async"


async def test_async_resolver_rejects_empty_string() -> None:
    with pytest.raises(AskiiAuthError):
        make_async_resolver("")


async def test_async_resolver_rejects_none() -> None:
    with pytest.raises(AskiiAuthError):
        make_async_resolver(None)


async def test_async_resolver_rejects_unsupported_type() -> None:
    with pytest.raises(AskiiAuthError):
        make_async_resolver(42)  # type: ignore[arg-type]


async def test_async_resolver_rejects_callable_returning_empty() -> None:
    resolver = make_async_resolver(lambda: "")
    with pytest.raises(AskiiAuthError):
        await resolver()


# --- sync resolver ---------------------------------------------------


def test_sync_resolver_from_static_string() -> None:
    resolver = make_sync_resolver("jwt-static")
    assert resolver() == "jwt-static"


def test_sync_resolver_from_callable() -> None:
    resolver = make_sync_resolver(lambda: "jwt-call")
    assert resolver() == "jwt-call"


def test_sync_resolver_rejects_none() -> None:
    with pytest.raises(AskiiAuthError):
        make_sync_resolver(None)


def test_sync_resolver_rejects_unsupported() -> None:
    with pytest.raises(AskiiAuthError):
        make_sync_resolver(42)  # type: ignore[arg-type]


def test_sync_resolver_rejects_async_def_at_construction() -> None:
    async def provider() -> str:
        return "x"

    with pytest.raises(AskiiAuthError):
        make_sync_resolver(provider)


def test_sync_resolver_rejects_sync_callable_returning_awaitable() -> None:
    """A plain sync function that returns a coroutine (unusual but possible) is rejected at call time."""

    async def _coro() -> str:
        return "x"

    def trampoline() -> object:
        return _coro()

    resolver = make_sync_resolver(trampoline)
    with pytest.raises(AskiiAuthError):
        resolver()
