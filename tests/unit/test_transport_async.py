"""End-to-end tests for the async transport using ``httpx.MockTransport``."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from askii import (
    AskiiAuthError,
    AskiiConfig,
    AskiiServerError,
    AskiiValidationError,
    Hooks,
    InMemoryCache,
)
from askii._transport import HTTPTransport


def _resp(
    status: int = 200,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    content = json.dumps(body or {}).encode()
    request = httpx.Request("POST", "https://api.askii.test/x")
    return httpx.Response(
        status,
        headers={"content-type": "application/json", **(headers or {})},
        content=content,
        request=request,
    )


def _transport(
    cfg: AskiiConfig,
    handler: Callable[[httpx.Request], httpx.Response],
) -> HTTPTransport:
    mock = httpx.MockTransport(handler)
    client = httpx.AsyncClient(base_url=cfg.base_url, transport=mock, timeout=cfg.timeout)
    return HTTPTransport(cfg, sync=False, http_client=client)


async def test_happy_path_returns_parsed_dict(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body == {"foo": "bar"}
        return _resp(200, {"ok": True})

    transport = _transport(cfg, handler)
    result = await transport.arequest("POST", "/x", body={"foo": "bar"})
    assert result == {"ok": True}
    await transport.aclose()


async def test_204_returns_empty_dict(config_factory: Callable[..., AskiiConfig]) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(204, request=req)

    transport = _transport(config_factory(), handler)
    assert await transport.arequest("POST", "/x", body={}) == {}
    await transport.aclose()


async def test_retries_on_5xx_until_success(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory(max_retries=3)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        if seen["n"] < 3:
            return _resp(500, {"detail": "boom"})
        return _resp(200, {"ok": True})

    transport = _transport(cfg, handler)
    result = await transport.arequest("POST", "/x", body={})
    assert result == {"ok": True}
    assert seen["n"] == 3
    await transport.aclose()


async def test_non_idempotent_call_skips_retries(config_factory: Callable[..., AskiiConfig]) -> None:
    """`idempotent=False` must NOT retry on 5xx — the mutation may already have applied."""
    cfg = config_factory(max_retries=3)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(500, {"detail": "boom"})

    transport = _transport(cfg, handler)
    from askii import AskiiServerError

    with pytest.raises(AskiiServerError):
        await transport.arequest("POST", "/x", body={}, idempotent=False)
    assert seen["n"] == 1
    await transport.aclose()


async def test_non_idempotent_call_still_succeeds_on_2xx(config_factory: Callable[..., AskiiConfig]) -> None:
    """Happy-path non-idempotent calls return as normal."""
    cfg = config_factory(max_retries=3)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(200, {"ok": True})

    transport = _transport(cfg, handler)
    result = await transport.arequest("POST", "/x", body={}, idempotent=False)
    assert result == {"ok": True}
    assert seen["n"] == 1
    await transport.aclose()


async def test_gives_up_after_max_attempts(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory(max_retries=2)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(500, {"detail": "boom"})

    transport = _transport(cfg, handler)
    with pytest.raises(AskiiServerError):
        await transport.arequest("POST", "/x", body={})
    assert seen["n"] == 2
    await transport.aclose()


async def test_does_not_retry_on_401(config_factory: Callable[..., AskiiConfig]) -> None:
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(401, {"detail": "expired"})

    transport = _transport(config_factory(max_retries=3), handler)
    with pytest.raises(AskiiAuthError):
        await transport.arequest("POST", "/x", body={})
    assert seen["n"] == 1
    await transport.aclose()


async def test_422_raises_validation_error(config_factory: Callable[..., AskiiConfig]) -> None:
    body = {
        "detail": [
            {"loc": ["body", "duration_days"], "msg": "bad", "type": "value_error"},
        ]
    }

    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(422, body)

    transport = _transport(config_factory(max_retries=1), handler)
    with pytest.raises(AskiiValidationError) as excinfo:
        await transport.arequest("POST", "/x", body={})
    assert excinfo.value.field_errors[0].path == "body.duration_days"
    await transport.aclose()


async def test_correlation_id_header_is_sent(config_factory: Callable[..., AskiiConfig]) -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(req.headers))
        return _resp(200, {"ok": True})

    transport = _transport(config_factory(), handler)
    await transport.arequest("POST", "/x", body={})
    assert "x-correlation-id" in seen_headers[0]
    await transport.aclose()


async def test_cache_hit_skips_network(config_factory: Callable[..., AskiiConfig]) -> None:
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(200, {"v": seen["n"]})

    cache = InMemoryCache()
    cfg = config_factory(cache=cache, default_cache_ttl=60)
    transport = _transport(cfg, handler)
    first = await transport.arequest("POST", "/x", body={}, cache_key="k", cache_ttl=60)
    second = await transport.arequest("POST", "/x", body={}, cache_key="k", cache_ttl=60)
    assert first == {"v": 1}
    assert second == {"v": 1}  # cache hit
    assert seen["n"] == 1
    await transport.aclose()


async def test_hooks_receive_request_and_response_events(config_factory: Callable[..., AskiiConfig]) -> None:
    events: list[tuple[str, Any]] = []

    hooks = Hooks(
        on_request=lambda e: events.append(("request", e)),
        on_response=lambda e: events.append(("response", e)),
    )

    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(200, {"ok": True})

    transport = _transport(config_factory(hooks=hooks), handler)
    await transport.arequest("POST", "/x", body={})
    kinds = [k for k, _ in events]
    assert kinds == ["request", "response"]
    await transport.aclose()


async def test_hook_callback_exception_is_swallowed(config_factory: Callable[..., AskiiConfig]) -> None:
    def boom(_: Any) -> None:
        raise RuntimeError("test")

    hooks = Hooks(on_request=boom)

    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(200, {"ok": True})

    transport = _transport(config_factory(hooks=hooks), handler)
    # No exception expected
    assert await transport.arequest("POST", "/x", body={}) == {"ok": True}
    await transport.aclose()


async def test_sync_method_raises_on_async_transport(config_factory: Callable[..., AskiiConfig]) -> None:
    transport = _transport(config_factory(), lambda req: _resp(200))
    with pytest.raises(RuntimeError):
        transport.request("POST", "/x", body={})
    await transport.aclose()


async def test_constructor_rejects_wrong_client_type(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()
    sync_client = httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(lambda r: _resp(200)))
    with pytest.raises(TypeError):
        HTTPTransport(cfg, sync=False, http_client=sync_client)  # type: ignore[arg-type]
    sync_client.close()


async def test_network_error_maps_to_connection_error(config_factory: Callable[..., AskiiConfig]) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope")

    transport = _transport(config_factory(max_retries=1), handler)
    from askii import AskiiConnectionError

    with pytest.raises(AskiiConnectionError):
        await transport.arequest("POST", "/x", body={})
    await transport.aclose()
