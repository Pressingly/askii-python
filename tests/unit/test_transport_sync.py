"""End-to-end tests for the sync transport using ``httpx.MockTransport``."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from askii import (
    AskiiAuthError,
    AskiiConfig,
    AskiiConnectionError,
    AskiiServerError,
    InMemoryCache,
)
from askii._transport import HTTPTransport


def _resp(status: int = 200, body: dict[str, Any] | None = None) -> httpx.Response:
    content = json.dumps(body or {}).encode()
    request = httpx.Request("POST", "https://api.askii.test/x")
    return httpx.Response(status, headers={"content-type": "application/json"}, content=content, request=request)


def _transport(
    cfg: AskiiConfig,
    handler: Callable[[httpx.Request], httpx.Response],
) -> HTTPTransport:
    mock = httpx.MockTransport(handler)
    client = httpx.Client(base_url=cfg.base_url, transport=mock, timeout=cfg.timeout)
    return HTTPTransport(cfg, sync=True, http_client=client)


def test_sync_happy_path(config_factory: Callable[..., AskiiConfig]) -> None:
    transport = _transport(config_factory(), lambda req: _resp(200, {"v": 1}))
    assert transport.request("POST", "/x", body={}) == {"v": 1}
    transport.close()


def test_sync_5xx_retries(config_factory: Callable[..., AskiiConfig]) -> None:
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        if seen["n"] < 3:
            return _resp(500, {"detail": "x"})
        return _resp(200, {"ok": True})

    transport = _transport(config_factory(max_retries=3), handler)
    assert transport.request("POST", "/x", body={}) == {"ok": True}
    assert seen["n"] == 3
    transport.close()


def test_sync_401_no_retry(config_factory: Callable[..., AskiiConfig]) -> None:
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(401, {"detail": "x"})

    transport = _transport(config_factory(max_retries=3), handler)
    with pytest.raises(AskiiAuthError):
        transport.request("POST", "/x", body={})
    assert seen["n"] == 1
    transport.close()


def test_sync_cache_hit(config_factory: Callable[..., AskiiConfig]) -> None:
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(200, {"v": seen["n"]})

    cache = InMemoryCache()
    cfg = config_factory(cache=cache)
    transport = _transport(cfg, handler)
    first = transport.request("POST", "/x", body={}, cache_key="k", cache_ttl=60)
    second = transport.request("POST", "/x", body={}, cache_key="k", cache_ttl=60)
    assert first == second
    assert seen["n"] == 1
    transport.close()


def test_sync_constructor_rejects_async_client(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()
    aclient = httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(lambda r: _resp(200)))
    with pytest.raises(TypeError):
        HTTPTransport(cfg, sync=True, http_client=aclient)  # type: ignore[arg-type]


def test_sync_method_raises_on_async_transport_object(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()
    aclient = httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(lambda r: _resp(200)))
    transport = HTTPTransport(cfg, sync=False, http_client=aclient)
    with pytest.raises(RuntimeError):
        transport.request("POST", "/x", body={})


def test_sync_non_idempotent_skips_retries(config_factory: Callable[..., AskiiConfig]) -> None:
    """`idempotent=False` must NOT retry on 5xx in the sync transport either."""
    cfg = config_factory(max_retries=3)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(500, {"detail": "boom"})

    transport = _transport(cfg, handler)
    with pytest.raises(AskiiServerError):
        transport.request("POST", "/x", body={}, idempotent=False)
    assert seen["n"] == 1
    transport.close()


def test_sync_returns_500_after_retries(config_factory: Callable[..., AskiiConfig]) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(500, {"detail": "boom"})

    transport = _transport(config_factory(max_retries=2), handler)
    with pytest.raises(AskiiServerError):
        transport.request("POST", "/x", body={})
    transport.close()


def test_sync_connection_error_maps(config_factory: Callable[..., AskiiConfig]) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    transport = _transport(config_factory(max_retries=1), handler)
    with pytest.raises(AskiiConnectionError):
        transport.request("POST", "/x", body={})
    transport.close()
