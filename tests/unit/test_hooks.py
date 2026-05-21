"""Tests for the lifecycle hook dispatcher."""

from __future__ import annotations

from askii import Hooks, RequestEvent, ResponseEvent, RetryEvent
from askii._hooks import _HooksProxy, empty_headers


def test_dispatch_invokes_callback() -> None:
    seen: list[str] = []
    hooks = Hooks(on_cache_hit=seen.append)
    proxy = _HooksProxy(hooks)
    proxy.cache_hit("k1")
    proxy.cache_hit("k2")
    assert seen == ["k1", "k2"]


def test_dispatch_swallows_exceptions(caplog: object) -> None:
    def kaboom(_: object) -> None:
        raise RuntimeError("nope")

    hooks = Hooks(on_cache_miss=kaboom)
    proxy = _HooksProxy(hooks)
    # Should not propagate
    proxy.cache_miss("k")


def test_dispatch_no_callback_is_noop() -> None:
    proxy = _HooksProxy(Hooks())
    # All call sites should be safe with no callbacks set.
    proxy.cache_hit("k")
    proxy.cache_miss("k")
    proxy.request(RequestEvent("GET", "/", "cid", 1, empty_headers()))
    proxy.response(ResponseEvent("GET", "/", "cid", 1, 200, 1.0, None))
    proxy.error(RuntimeError())


def test_request_event_is_frozen() -> None:
    event = RequestEvent("GET", "/x", "cid", 1, empty_headers())
    import dataclasses

    assert dataclasses.is_dataclass(event)
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.attempt = 2  # type: ignore[misc]


def test_retry_event_carries_exception() -> None:
    exc = ValueError("boom")
    event = RetryEvent("GET", "/x", "cid", 2, 0.5, exc)
    assert event.exception is exc
