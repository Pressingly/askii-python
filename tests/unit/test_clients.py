"""Resource-level tests for AsyncAskii / Askii."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from askii import (
    Askii,
    AskiiConfig,
    AsyncAskii,
    InMemoryCache,
    MemoryMode,
)
from askii._endpoints import (
    GET_KEY_CONFIG,
    LIST_KEYS,
    PROVISION_KEY,
    UPDATE_KEY_MODEL,
)


def _resp(status: int = 200, body: dict[str, Any] | None = None) -> httpx.Response:
    content = json.dumps(body or {}).encode()
    request = httpx.Request("POST", "https://api.askii.test/x")
    return httpx.Response(status, headers={"content-type": "application/json"}, content=content, request=request)


def _async_handler(
    routes: dict[str, dict[str, Any]],
) -> tuple[Callable[[httpx.Request], httpx.Response], list[httpx.Request]]:
    recorded: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        recorded.append(req)
        return _resp(200, routes.get(req.url.path, {}))

    return handler, recorded


async def test_async_keys_provision_invokes_endpoint(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()
    routes = {
        PROVISION_KEY: {
            "api_key": "sk-real-secret-key-1234567890",
            "key_name": "key-1",
            "user_id": "user-1",
            "expires": "2026-08-01T00:00:00Z",
        }
    }
    handler, recorded = _async_handler(routes)
    client = AsyncAskii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    )
    resp = await client.keys.provision(
        key_alias="alias-1", duration_days=30, memory_enabled=True, memory_mode=MemoryMode.PKG
    )
    assert resp.api_key.get_secret_value() == "sk-real-secret-key-1234567890"
    sent = json.loads(recorded[0].content)
    assert sent["mpass_token"] == "jwt-1"
    assert sent["duration_days"] == 30
    assert sent["memory_mode"] == "pkg"
    await client.aclose()


async def test_async_keys_list_caches_when_ttl_given(config_factory: Callable[..., AskiiConfig]) -> None:
    cache = InMemoryCache()
    cfg = config_factory(cache=cache)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(200, {"user_id": "u", "keys": []})

    client = AsyncAskii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    )
    await client.keys.list(cache_ttl=60)
    await client.keys.list(cache_ttl=60)
    assert seen["n"] == 1
    await client.aclose()


async def test_async_keys_provision_invalidates_list_cache(config_factory: Callable[..., AskiiConfig]) -> None:
    cache = InMemoryCache()
    cfg = config_factory(cache=cache)
    seen = {"n": 0}
    routes = {
        LIST_KEYS: {"user_id": "u", "keys": []},
        PROVISION_KEY: {
            "api_key": "sk-abcdefgh12345678",
            "key_name": "k",
            "user_id": "u",
        },
    }

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == LIST_KEYS:
            seen["n"] += 1
        return _resp(200, routes[req.url.path])

    client = AsyncAskii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    )
    await client.keys.list(cache_ttl=60)
    await client.keys.provision()  # invalidates list cache
    await client.keys.list(cache_ttl=60)
    assert seen["n"] == 2  # cache was invalidated, second list re-fetches
    await client.aclose()


async def test_async_request_escape_hatch_injects_token(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()
    recorded: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        recorded.append(req)
        return _resp(200, {"raw": True})

    client = AsyncAskii(
        token="jwt-9",
        config=cfg,
        http_client=httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    )
    result = await client.request("POST", "/platform/future-endpoint", body={"a": 1})
    assert result == {"raw": True}
    sent = json.loads(recorded[0].content)
    assert sent == {"mpass_token": "jwt-9", "a": 1}
    await client.aclose()


async def test_async_models_list(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()

    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(200, {"models": [{"model_name": "gpt-4o"}]})

    client = AsyncAskii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.AsyncClient(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    )
    resp = await client.models.list()
    assert [m.model_name for m in resp.models] == ["gpt-4o"]
    await client.aclose()


async def test_async_client_context_manager() -> None:
    cfg = AskiiConfig(token="jwt-1", base_url="https://api.askii.test", max_retries=1)
    async with AsyncAskii(
        config=cfg,
        http_client=httpx.AsyncClient(
            base_url=cfg.base_url,
            transport=httpx.MockTransport(lambda r: _resp(200, {"models": []})),
        ),
    ) as client:
        await client.models.list()
    # client is closed here; no further calls


def test_sync_keys_provision(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()

    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(
            200,
            {
                "api_key": "sk-syncsyncsyncsyncsync",
                "key_name": "k",
                "user_id": "u",
            },
        )

    client = Askii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    )
    resp = client.keys.provision()
    assert resp.api_key.get_secret_value() == "sk-syncsyncsyncsyncsync"
    client.close()


def test_sync_request_escape_hatch_injects_token(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()
    recorded: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        recorded.append(req)
        return _resp(200, {"raw": True})

    with Askii(
        token="jwt-2",
        config=cfg,
        http_client=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    ) as client:
        result = client.request("POST", "/platform/anything", body={"b": 2})
    sent = json.loads(recorded[0].content)
    assert sent == {"mpass_token": "jwt-2", "b": 2}
    assert result == {"raw": True}


def test_sync_keys_list_with_cache(config_factory: Callable[..., AskiiConfig]) -> None:
    cache = InMemoryCache()
    cfg = config_factory(cache=cache)
    seen = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["n"] += 1
        return _resp(200, {"user_id": "u", "keys": []})

    with Askii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    ) as client:
        client.keys.list(cache_ttl=60)
        client.keys.list(cache_ttl=60)
    assert seen["n"] == 1


def test_sync_keys_get_config_then_invalidate(config_factory: Callable[..., AskiiConfig]) -> None:
    cache = InMemoryCache()
    cfg = config_factory(cache=cache)
    seen = {"get_config": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == GET_KEY_CONFIG:
            seen["get_config"] += 1
            return _resp(200, {"key_name": "k", "models": [], "memory_enabled": False})
        if req.url.path == UPDATE_KEY_MODEL:
            return _resp(200, {"updated": True, "key_name": "k", "models": ["gpt-4o"]})
        return _resp(404, {"detail": "?"})

    with Askii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    ) as client:
        client.keys.get_config(key="alias", cache_ttl=60)
        client.keys.get_config(key="alias", cache_ttl=60)
        assert seen["get_config"] == 1
        client.keys.update_model(key="alias", models=["gpt-4o"])  # invalidates
        client.keys.get_config(key="alias", cache_ttl=60)
        assert seen["get_config"] == 2


def test_sync_async_callable_token_rejected() -> None:
    async def provider() -> str:
        return "x"

    cfg = AskiiConfig(
        base_url="https://api.askii.test",
        max_retries=1,
    )
    from askii import AskiiAuthError

    with pytest.raises(AskiiAuthError):
        Askii(token=provider, config=cfg)


def test_sync_revoke(config_factory: Callable[..., AskiiConfig]) -> None:
    cfg = config_factory()

    def handler(req: httpx.Request) -> httpx.Response:
        return _resp(200, {"revoked": True, "detail": "ok"})

    with Askii(
        token="jwt-1",
        config=cfg,
        http_client=httpx.Client(base_url=cfg.base_url, transport=httpx.MockTransport(handler)),
    ) as client:
        resp = client.keys.revoke(key="alias")
    assert resp.revoked is True
