"""Token resolvers — accept a string, a sync callable, or an async callable."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from askii._errors import AskiiAuthError

TokenSource: TypeAlias = str | Callable[[], str] | Callable[[], Awaitable[str]]

AsyncResolver = Callable[[], Awaitable[str]]
SyncResolver = Callable[[], str]


def _ensure_token(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise AskiiAuthError(
            status=0,
            detail="Token resolver returned an empty or non-string value",
        )
    return value


def make_async_resolver(source: TokenSource | None) -> AsyncResolver:
    """Build a coroutine resolver from a string, sync callable, or async callable."""
    if source is None:
        raise AskiiAuthError(status=0, detail="No mpass_token provided")

    if isinstance(source, str):
        token = _ensure_token(source)

        async def _static() -> str:
            return token

        return _static

    if callable(source):

        async def _dynamic() -> str:
            value = source()
            if inspect.isawaitable(value):
                value = await value
            return _ensure_token(value)

        return _dynamic

    raise AskiiAuthError(
        status=0,
        detail=f"Unsupported token source: {type(source).__name__}",
    )


def make_sync_resolver(source: TokenSource | None) -> SyncResolver:
    """Build a synchronous resolver. Rejects coroutine factories."""
    if source is None:
        raise AskiiAuthError(status=0, detail="No mpass_token provided")

    if isinstance(source, str):
        token = _ensure_token(source)

        def _static() -> str:
            return token

        return _static

    if inspect.iscoroutinefunction(source) or inspect.isasyncgenfunction(source):
        raise AskiiAuthError(
            status=0,
            detail=(
                "Sync Askii client received an async token callable. "
                "Use AsyncAskii or supply a sync callable / static string."
            ),
        )

    if callable(source):

        def _dynamic() -> str:
            value = source()
            if inspect.isawaitable(value):
                # Close the coroutine cleanly to keep "unawaited coroutine" warnings out.
                if hasattr(value, "close"):
                    value.close()
                raise AskiiAuthError(
                    status=0,
                    detail=(
                        "Sync Askii client received an async token callable. "
                        "Use AsyncAskii or supply a sync callable / static string."
                    ),
                )
            return _ensure_token(value)

        return _dynamic

    raise AskiiAuthError(
        status=0,
        detail=f"Unsupported token source: {type(source).__name__}",
    )


__all__ = [
    "TokenSource",
    "AsyncResolver",
    "SyncResolver",
    "make_async_resolver",
    "make_sync_resolver",
]
