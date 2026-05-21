"""Tests for the tenacity retry policy factory."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from askii import AskiiConfig, AskiiRateLimitError, AskiiServerError, AskiiTimeoutError
from askii._retry import _AskiiWait, build_async_retry, build_sync_retry


@pytest.fixture
def cfg(config_factory: Callable[..., AskiiConfig]) -> AskiiConfig:
    return config_factory(max_retries=4)


def test_sync_retry_runs_until_success(cfg: AskiiConfig) -> None:
    runner = build_sync_retry(cfg)
    attempts = {"n": 0}

    def call() -> int:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise AskiiServerError(500, "boom")
        return 42

    result: int | None = None
    for attempt in runner:
        with attempt:
            result = call()
    assert result == 42
    assert attempts["n"] == 3


def test_sync_retry_gives_up_after_max_attempts(cfg: AskiiConfig) -> None:
    runner = build_sync_retry(cfg)
    attempts = {"n": 0}

    def call() -> None:
        attempts["n"] += 1
        raise AskiiServerError(500, "boom")

    with pytest.raises(AskiiServerError):
        for attempt in runner:
            with attempt:
                call()
    assert attempts["n"] == 4


def test_sync_retry_doesnt_retry_unknown_errors(cfg: AskiiConfig) -> None:
    runner = build_sync_retry(cfg)
    attempts = {"n": 0}

    def call() -> None:
        attempts["n"] += 1
        raise ValueError("unrelated")

    with pytest.raises(ValueError):
        for attempt in runner:
            with attempt:
                call()
    assert attempts["n"] == 1


async def test_async_retry_runs_until_success(cfg: AskiiConfig) -> None:
    runner = build_async_retry(cfg)
    attempts = {"n": 0}

    async def call() -> int:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise AskiiTimeoutError("slow")
        return 7

    result: int | None = None
    async for attempt in runner:
        with attempt:
            result = await call()
    assert result == 7
    assert attempts["n"] == 2


def test_wait_strategy_honors_retry_after() -> None:
    wait = _AskiiWait(initial=0.1, max_wait=2.0)

    class _State:
        attempt_number = 2
        outcome: Any

    state = _State()

    class _Outcome:
        failed = True

        def exception(self) -> BaseException:
            return AskiiRateLimitError(429, "rl", retry_after=3.5)

    state.outcome = _Outcome()
    assert wait(state) == 3.5  # type: ignore[arg-type]


def test_wait_strategy_falls_back_to_exponential() -> None:
    wait = _AskiiWait(initial=0.1, max_wait=2.0)

    class _State:
        attempt_number = 3
        outcome: Any = None

    sleep = wait(_State())  # type: ignore[arg-type]
    # On attempt 3, base = 0.1 * 2^2 = 0.4, clamped to 2.0; jitter halves to [0.2, 0.4).
    assert 0.0 < sleep <= 2.0


def test_wait_caps_retry_after_at_60s() -> None:
    wait = _AskiiWait(initial=0.1, max_wait=2.0)

    class _State:
        attempt_number = 1
        outcome: Any

    state = _State()

    class _Outcome:
        failed = True

        def exception(self) -> BaseException:
            return AskiiRateLimitError(429, "rl", retry_after=99999)

    state.outcome = _Outcome()
    assert wait(state) == 60.0  # type: ignore[arg-type]
