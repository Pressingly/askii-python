"""Frozen-dataclass configuration for the Askii client."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from askii._hooks import Hooks
from askii._token import TokenSource

if TYPE_CHECKING:
    from askii._cache import Cache

DEFAULT_BASE_URL = "https://api.askii.ai"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3


def _default_cache() -> Cache:
    from askii._cache.memory import InMemoryCache

    return InMemoryCache(default_ttl=0.0)


def _default_user_agent() -> str:
    try:
        from askii._version import __version__
    except ImportError:
        __version__ = "0.0.0+local"
    return f"askii-python/{__version__} python/{platform.python_version()}"


@dataclass(frozen=True, slots=True)
class AskiiConfig:
    """Immutable runtime configuration for the Askii client.

    Construct directly or via :meth:`from_env`. All fields have sensible defaults
    so callers can pass nothing and still get a working client.
    """

    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    http2: bool = True
    token: TokenSource | None = None
    cache: Cache = field(default_factory=_default_cache)
    hooks: Hooks = field(default_factory=Hooks)
    default_cache_ttl: float = 0.0
    user_agent: str = field(default_factory=_default_user_agent)
    verify: bool | str = True

    @classmethod
    def from_env(cls, **overrides: Any) -> AskiiConfig:
        """Build a config, picking up `ASKII_*` env vars as fallbacks.

        Recognized variables:

        - ``ASKII_BASE_URL``
        - ``ASKII_TOKEN``
        - ``ASKII_TIMEOUT_SECONDS``
        - ``ASKII_MAX_RETRIES``

        Explicit kwargs always win over env vars.
        """
        env_kwargs: dict[str, Any] = {
            "base_url": os.getenv("ASKII_BASE_URL", DEFAULT_BASE_URL),
        }
        if (token := os.getenv("ASKII_TOKEN")) is not None:
            env_kwargs["token"] = token
        if (raw := os.getenv("ASKII_TIMEOUT_SECONDS")) is not None:
            env_kwargs["timeout"] = float(raw)
        if (raw := os.getenv("ASKII_MAX_RETRIES")) is not None:
            env_kwargs["max_retries"] = int(raw)
        env_kwargs.update(overrides)
        return cls(**env_kwargs)


__all__ = ["AskiiConfig", "DEFAULT_BASE_URL", "DEFAULT_TIMEOUT_SECONDS", "DEFAULT_MAX_RETRIES"]
