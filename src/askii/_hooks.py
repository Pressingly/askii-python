"""Lifecycle hooks for observability and metrics integration.

Hook callbacks are plain callables, never coroutines (sync + async paths share
them). Exceptions raised inside a callback are caught and logged at WARNING so
they never break the underlying request.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("askii.hooks")


@dataclass(frozen=True, slots=True)
class RequestEvent:
    """Emitted just before the HTTP request is sent (per attempt)."""

    method: str
    path: str
    correlation_id: str
    attempt: int
    headers: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ResponseEvent:
    """Emitted after the HTTP response is received (per attempt, success or not)."""

    method: str
    path: str
    correlation_id: str
    attempt: int
    status_code: int
    elapsed_ms: float
    request_id: str | None


@dataclass(frozen=True, slots=True)
class RetryEvent:
    """Emitted when the retry policy decides to sleep before another attempt."""

    method: str
    path: str
    correlation_id: str
    attempt: int
    sleep_seconds: float
    exception: BaseException


@dataclass(slots=True)
class Hooks:
    """Container for optional lifecycle callbacks.

    All callbacks are optional. Each is invoked synchronously from both the sync
    and async transports; if a callback raises, the exception is swallowed and
    logged at WARNING.
    """

    on_request: Callable[[RequestEvent], None] | None = None
    on_response: Callable[[ResponseEvent], None] | None = None
    on_retry: Callable[[RetryEvent], None] | None = None
    on_cache_hit: Callable[[str], None] | None = None
    on_cache_miss: Callable[[str], None] | None = None
    on_error: Callable[[BaseException], None] | None = None

    def dispatch(self, callback: Callable[..., None] | None, *args: Any) -> None:
        if callback is None:
            return
        try:
            callback(*args)
        except Exception:  # noqa: BLE001 — hooks must never poison the call
            logger.warning("askii hook callback raised; swallowed", exc_info=True)


_EMPTY_HEADERS: Mapping[str, str] = {}


def empty_headers() -> Mapping[str, str]:
    """Return a stable empty headers mapping for event construction."""
    return _EMPTY_HEADERS


@dataclass(slots=True)
class _HooksProxy:
    """Convenience wrapper that adds typed dispatch methods.

    The transport calls this rather than `Hooks` directly so the call sites stay
    readable.
    """

    hooks: Hooks = field(default_factory=Hooks)

    def request(self, event: RequestEvent) -> None:
        self.hooks.dispatch(self.hooks.on_request, event)

    def response(self, event: ResponseEvent) -> None:
        self.hooks.dispatch(self.hooks.on_response, event)

    def retry(self, event: RetryEvent) -> None:
        self.hooks.dispatch(self.hooks.on_retry, event)

    def cache_hit(self, key: str) -> None:
        self.hooks.dispatch(self.hooks.on_cache_hit, key)

    def cache_miss(self, key: str) -> None:
        self.hooks.dispatch(self.hooks.on_cache_miss, key)

    def error(self, exc: BaseException) -> None:
        self.hooks.dispatch(self.hooks.on_error, exc)


__all__ = [
    "Hooks",
    "RequestEvent",
    "ResponseEvent",
    "RetryEvent",
    "empty_headers",
]
