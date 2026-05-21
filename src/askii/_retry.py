"""Tenacity retry policy used by the sync and async transports.

Both transports drive the *same* policy. The only difference is the runner —
:class:`tenacity.AsyncRetrying` vs :class:`tenacity.Retrying`.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
)
from tenacity.wait import wait_base

from askii._errors import (
    AskiiConnectionError,
    AskiiRateLimitError,
    AskiiServerError,
    AskiiTimeoutError,
)

if TYPE_CHECKING:
    from tenacity import RetryCallState

    from askii._config import AskiiConfig

RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AskiiServerError,
    AskiiRateLimitError,
    AskiiConnectionError,
    AskiiTimeoutError,
)


class _AskiiWait(wait_base):
    """Exponential backoff with jitter; honors ``Retry-After`` from 429s."""

    def __init__(self, initial: float = 0.1, max_wait: float = 2.0) -> None:
        self._initial = initial
        self._max = max_wait

    def __call__(self, retry_state: RetryCallState) -> float:
        outcome = retry_state.outcome
        if outcome is not None and outcome.failed:
            exc = outcome.exception()
            if isinstance(exc, AskiiRateLimitError) and exc.retry_after:
                return min(float(exc.retry_after), 60.0)
        attempt = retry_state.attempt_number
        backoff = self._initial * (2 ** max(0, attempt - 1))
        backoff = min(backoff, self._max)
        return float(backoff * (0.5 + random.random() / 2))  # noqa: S311 — jitter, not crypto


def _build_kwargs(config: AskiiConfig) -> dict[str, object]:
    return {
        "stop": stop_after_attempt(max(1, config.max_retries)),
        "wait": _AskiiWait(initial=0.1, max_wait=2.0),
        "retry": retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        "reraise": True,
    }


def build_async_retry(config: AskiiConfig) -> AsyncRetrying:
    """Build the async retry runner for a given config."""
    return AsyncRetrying(**_build_kwargs(config))  # type: ignore[arg-type]


def build_sync_retry(config: AskiiConfig) -> Retrying:
    """Build the sync retry runner for a given config."""
    return Retrying(**_build_kwargs(config))  # type: ignore[arg-type]


__all__ = [
    "RETRYABLE_EXCEPTIONS",
    "build_async_retry",
    "build_sync_retry",
]
