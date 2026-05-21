"""HTTP transport — the engine that powers both sync and async clients.

A single :class:`HTTPTransport` instance is either sync- or async-flavored
(its httpx client is fixed at construction). Both flavors share every other
concern: header construction, correlation IDs, cache check + write, retry
policy, response parsing, error mapping, and hook dispatch.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from askii._errors import (
    AskiiConnectionError,
    AskiiTimeoutError,
    AskiiTransportError,
    map_response_to_error,
)
from askii._hooks import RequestEvent, ResponseEvent, RetryEvent, _HooksProxy
from askii._logging import (
    bind_correlation_id,
    get_correlation_id,
    get_logger,
    reset_correlation_id,
)
from askii._retry import build_async_retry, build_sync_retry

if TYPE_CHECKING:
    from contextvars import Token

    from askii._cache import Cache
    from askii._config import AskiiConfig

logger = get_logger("askii.transport")


class HTTPTransport:
    """Engine that owns one httpx client and runs requests with retries.

    Construct with ``sync=True`` for :class:`httpx.Client` or ``sync=False``
    for :class:`httpx.AsyncClient`. The other path will raise if invoked.
    """

    def __init__(
        self,
        config: AskiiConfig,
        *,
        sync: bool,
        http_client: httpx.Client | httpx.AsyncClient | None = None,
    ) -> None:
        self._cfg = config
        self._sync = sync
        self._owns_client = http_client is None
        self._client_sync: httpx.Client | None
        self._client_async: httpx.AsyncClient | None
        if sync:
            if http_client is not None and not isinstance(http_client, httpx.Client):
                raise TypeError("sync=True requires an httpx.Client (got AsyncClient)")
            self._client_sync = http_client or self._build_sync_client()
            self._client_async = None
        else:
            if http_client is not None and not isinstance(http_client, httpx.AsyncClient):
                raise TypeError("sync=False requires an httpx.AsyncClient (got Client)")
            self._client_async = http_client or self._build_async_client()
            self._client_sync = None
        self._hooks = _HooksProxy(config.hooks)
        self._cache: Cache = config.cache

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    def _common_client_kwargs(self) -> dict[str, Any]:
        return {
            "base_url": self._cfg.base_url,
            "timeout": httpx.Timeout(self._cfg.timeout),
            "http2": self._cfg.http2,
            "verify": self._cfg.verify,
            "headers": {
                "User-Agent": self._cfg.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        }

    def _build_sync_client(self) -> httpx.Client:
        return httpx.Client(**self._common_client_kwargs())

    def _build_async_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(**self._common_client_kwargs())

    # ------------------------------------------------------------------
    # async path
    # ------------------------------------------------------------------

    async def arequest(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any],
        cache_key: str | None = None,
        cache_ttl: float | None = None,
    ) -> dict[str, Any]:
        """Run an async request with cache + retry + hooks."""
        if self._sync or self._client_async is None:
            raise RuntimeError("HTTPTransport was constructed with sync=True")

        if cache_key:
            cached = await self._cache.aget(cache_key)
            if cached is not None:
                self._hooks.cache_hit(cache_key)
                return cached  # type: ignore[no-any-return]
            self._hooks.cache_miss(cache_key)

        correlation_token, correlation_id = self._ensure_correlation_id()
        try:
            payload = await self._arun_with_retries(method, path, body, correlation_id)
        except BaseException as exc:
            self._hooks.error(exc)
            raise
        finally:
            if correlation_token is not None:
                reset_correlation_id(correlation_token)

        if cache_key and cache_ttl and cache_ttl > 0:
            await self._cache.aset(cache_key, payload, ttl=cache_ttl)
        return payload

    async def _arun_with_retries(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        retrying = build_async_retry(self._cfg)
        last_payload: dict[str, Any] | None = None
        async for attempt in retrying:
            with attempt:
                attempt_num = attempt.retry_state.attempt_number
                if attempt_num > 1 and attempt.retry_state.outcome is not None:
                    self._emit_retry_event(method, path, correlation_id, attempt_num, attempt.retry_state)
                last_payload = await self._asend(method, path, body, correlation_id, attempt_num)
        assert last_payload is not None
        return last_payload

    async def _asend(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        correlation_id: str,
        attempt: int,
    ) -> dict[str, Any]:
        assert self._client_async is not None
        headers = {"X-Correlation-ID": correlation_id}
        self._hooks.request(RequestEvent(method, path, correlation_id, attempt, headers))
        start = time.monotonic()
        try:
            response = await self._client_async.request(method, path, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise AskiiTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise AskiiConnectionError(str(exc)) from exc
        except httpx.NetworkError as exc:
            raise AskiiTransportError(str(exc)) from exc
        return self._parse(method, path, correlation_id, attempt, response, start)

    # ------------------------------------------------------------------
    # sync path
    # ------------------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any],
        cache_key: str | None = None,
        cache_ttl: float | None = None,
    ) -> dict[str, Any]:
        """Run a sync request with cache + retry + hooks."""
        if not self._sync or self._client_sync is None:
            raise RuntimeError("HTTPTransport was constructed with sync=False")

        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._hooks.cache_hit(cache_key)
                return cached  # type: ignore[no-any-return]
            self._hooks.cache_miss(cache_key)

        correlation_token, correlation_id = self._ensure_correlation_id()
        try:
            payload = self._run_with_retries(method, path, body, correlation_id)
        except BaseException as exc:
            self._hooks.error(exc)
            raise
        finally:
            if correlation_token is not None:
                reset_correlation_id(correlation_token)

        if cache_key and cache_ttl and cache_ttl > 0:
            self._cache.set(cache_key, payload, ttl=cache_ttl)
        return payload

    def _run_with_retries(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        retrying = build_sync_retry(self._cfg)
        last_payload: dict[str, Any] | None = None
        for attempt in retrying:
            with attempt:
                attempt_num = attempt.retry_state.attempt_number
                if attempt_num > 1 and attempt.retry_state.outcome is not None:
                    self._emit_retry_event(method, path, correlation_id, attempt_num, attempt.retry_state)
                last_payload = self._send(method, path, body, correlation_id, attempt_num)
        assert last_payload is not None
        return last_payload

    def _send(
        self,
        method: str,
        path: str,
        body: dict[str, Any],
        correlation_id: str,
        attempt: int,
    ) -> dict[str, Any]:
        assert self._client_sync is not None
        headers = {"X-Correlation-ID": correlation_id}
        self._hooks.request(RequestEvent(method, path, correlation_id, attempt, headers))
        start = time.monotonic()
        try:
            response = self._client_sync.request(method, path, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise AskiiTimeoutError(str(exc)) from exc
        except httpx.ConnectError as exc:
            raise AskiiConnectionError(str(exc)) from exc
        except httpx.NetworkError as exc:
            raise AskiiTransportError(str(exc)) from exc
        return self._parse(method, path, correlation_id, attempt, response, start)

    # ------------------------------------------------------------------
    # shared helpers
    # ------------------------------------------------------------------

    def _parse(
        self,
        method: str,
        path: str,
        correlation_id: str,
        attempt: int,
        response: httpx.Response,
        start: float,
    ) -> dict[str, Any]:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        self._hooks.response(
            ResponseEvent(
                method=method,
                path=path,
                correlation_id=correlation_id,
                attempt=attempt,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                request_id=request_id,
            )
        )
        logger.info(
            "askii.http",
            extra={
                "method": method,
                "path": path,
                "status": response.status_code,
                "latency_ms": round(elapsed_ms, 2),
                "attempt": attempt,
                "request_id": request_id,
            },
        )
        if response.status_code >= 400:
            raise map_response_to_error(response)
        if response.status_code == 204 or not response.content:
            return {}
        try:
            data = response.json()
        except ValueError as exc:
            raise AskiiTransportError(f"Upstream returned non-JSON response: {exc}") from exc
        if not isinstance(data, dict):
            return {"value": data}
        return data

    def _emit_retry_event(
        self,
        method: str,
        path: str,
        correlation_id: str,
        attempt: int,
        retry_state: Any,
    ) -> None:
        outcome = retry_state.outcome
        if outcome is None or not outcome.failed:
            return
        exc = outcome.exception()
        if exc is None:
            return
        sleep_seconds = float(getattr(retry_state.next_action, "sleep", 0.0) or 0.0)
        self._hooks.retry(
            RetryEvent(
                method=method,
                path=path,
                correlation_id=correlation_id,
                attempt=attempt,
                sleep_seconds=sleep_seconds,
                exception=exc,
            )
        )

    @staticmethod
    def _ensure_correlation_id() -> tuple[Token[str | None] | None, str]:
        existing = get_correlation_id()
        if existing is not None:
            return None, existing
        token = bind_correlation_id()
        current = get_correlation_id()
        assert current is not None  # bind_correlation_id always sets a value
        return token, current

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        if self._owns_client and self._client_async is not None:
            await self._client_async.aclose()

    def close(self) -> None:
        if self._owns_client and self._client_sync is not None:
            self._client_sync.close()


__all__ = ["HTTPTransport"]
