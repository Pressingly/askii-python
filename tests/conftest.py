"""Shared pytest fixtures for the askii test suite."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import httpx
import pytest

from askii import AskiiConfig

ASKII_ENV_VARS = ("ASKII_TOKEN", "ASKII_BASE_URL", "ASKII_TIMEOUT_SECONDS", "ASKII_MAX_RETRIES")


@pytest.fixture(autouse=True)
def _scrub_askii_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wipe ASKII_* env vars so tests run from a known baseline."""
    for name in ASKII_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_response() -> Callable[..., httpx.Response]:
    """Build an ``httpx.Response`` for the mock transport."""

    def _factory(
        status: int = 200,
        body: Any | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        request = httpx.Request("POST", "https://api.askii.ai/_test")
        content = b""
        merged_headers = {"content-type": "application/json", **(headers or {})}
        if body is not None:
            content = json.dumps(body).encode("utf-8")
        return httpx.Response(status, headers=merged_headers, content=content, request=request)

    return _factory


@pytest.fixture
def mock_transport() -> Callable[..., tuple[httpx.MockTransport, list[httpx.Request]]]:
    """Build an ``httpx.MockTransport`` that yields a deterministic response sequence.

    Pass either:
    - A single ``httpx.Response`` (replays it for every request)
    - An iterable of responses (one per request, in order)
    - A handler callable ``(httpx.Request) -> httpx.Response``
    """

    def _factory(
        responses: httpx.Response | Iterable[httpx.Response] | Callable[[httpx.Request], httpx.Response],
    ) -> tuple[httpx.MockTransport, list[httpx.Request]]:
        recorded: list[httpx.Request] = []

        if callable(responses) and not isinstance(responses, httpx.Response):
            handler = responses  # type: ignore[assignment]

            def _wrap(request: httpx.Request) -> httpx.Response:
                recorded.append(request)
                return handler(request)

            return httpx.MockTransport(_wrap), recorded

        if isinstance(responses, httpx.Response):
            single = responses

            def _replay(request: httpx.Request) -> httpx.Response:
                recorded.append(request)
                return single

            return httpx.MockTransport(_replay), recorded

        iterator = iter(responses)

        def _seq(request: httpx.Request) -> httpx.Response:
            recorded.append(request)
            return next(iterator)

        return httpx.MockTransport(_seq), recorded

    return _factory


@pytest.fixture
def config_factory() -> Callable[..., AskiiConfig]:
    """Convenience factory for AskiiConfig with sane test defaults."""

    def _factory(**overrides: Any) -> AskiiConfig:
        return AskiiConfig(
            base_url=overrides.pop("base_url", "https://api.askii.test"),
            timeout=overrides.pop("timeout", 5.0),
            max_retries=overrides.pop("max_retries", 1),
            http2=overrides.pop("http2", False),
            token=overrides.pop("token", "test-token"),
            **overrides,
        )

    return _factory


@pytest.fixture
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[float], None]]:
    """Override ``time.monotonic`` inside ``askii._cache.memory`` for deterministic TTL tests."""
    current = [0.0]

    def _now() -> float:
        return current[0]

    monkeypatch.setattr("askii._cache.memory.time.monotonic", _now)

    def _advance(seconds: float) -> None:
        current[0] += seconds

    yield _advance


@pytest.fixture(autouse=True)
def _reset_correlation_id() -> Iterator[None]:
    """Ensure each test starts without a bound correlation ID."""
    from askii._logging import _correlation_id_var

    token = _correlation_id_var.set(None)
    try:
        yield
    finally:
        _correlation_id_var.reset(token)


_FAKEREDIS_AVAILABLE = False
try:  # noqa: SIM105
    import fakeredis  # noqa: F401

    _FAKEREDIS_AVAILABLE = True
except ImportError:
    pass


@pytest.fixture
def fakeredis_clients() -> Any:
    """Yield (sync, async) fakeredis clients, or skip if fakeredis is missing."""
    if not _FAKEREDIS_AVAILABLE:
        pytest.skip("fakeredis not installed")
    import fakeredis
    import fakeredis.aioredis

    server = fakeredis.FakeServer()
    sync = fakeredis.FakeRedis(server=server)
    aio = fakeredis.aioredis.FakeRedis(server=server)
    yield sync, aio


@pytest.fixture
def restore_cwd() -> Iterator[str]:
    """Restore the working directory after a test that runs CLI commands."""
    here = os.getcwd()
    yield here
    os.chdir(here)
