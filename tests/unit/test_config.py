"""Tests for AskiiConfig and env handling."""

from __future__ import annotations

import pytest

from askii import AskiiConfig, Hooks, InMemoryCache
from askii._config import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT_SECONDS


def test_defaults_are_sane() -> None:
    cfg = AskiiConfig()
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.timeout == DEFAULT_TIMEOUT_SECONDS
    assert cfg.max_retries == DEFAULT_MAX_RETRIES
    assert cfg.http2 is True
    assert cfg.default_cache_ttl == 0.0
    assert cfg.token is None
    assert isinstance(cfg.cache, InMemoryCache)
    assert isinstance(cfg.hooks, Hooks)
    assert "askii-python" in cfg.user_agent


def test_config_is_frozen() -> None:
    cfg = AskiiConfig()
    with pytest.raises(Exception):  # noqa: B017 — dataclasses.FrozenInstanceError
        cfg.base_url = "x"  # type: ignore[misc]


def test_from_env_reads_known_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASKII_BASE_URL", "https://override.test")
    monkeypatch.setenv("ASKII_TOKEN", "tok-1")
    monkeypatch.setenv("ASKII_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("ASKII_MAX_RETRIES", "5")
    cfg = AskiiConfig.from_env()
    assert cfg.base_url == "https://override.test"
    assert cfg.token == "tok-1"
    assert cfg.timeout == 12.5
    assert cfg.max_retries == 5


def test_from_env_kwargs_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASKII_BASE_URL", "https://env.test")
    cfg = AskiiConfig.from_env(base_url="https://kw.test")
    assert cfg.base_url == "https://kw.test"


def test_from_env_without_vars_uses_defaults() -> None:
    cfg = AskiiConfig.from_env()
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.token is None


def test_user_agent_includes_python_version() -> None:
    import platform

    cfg = AskiiConfig()
    assert platform.python_version() in cfg.user_agent
