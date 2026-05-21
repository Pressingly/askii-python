"""Async client (``AsyncAskii``)."""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

from askii._cache import build_cache_key, build_resource_prefix
from askii._config import AskiiConfig
from askii._token import AsyncResolver, make_async_resolver
from askii._transport import HTTPTransport
from askii.resources.keys import AsyncKeysResource
from askii.resources.models import AsyncModelsResource

if TYPE_CHECKING:
    import httpx

    from askii._token import TokenSource


class AsyncAskii:
    """Asynchronous client for the Askii platform API.

    Pass either a static ``mpass_token`` string, a sync callable that returns
    a fresh token, or an async callable / coroutine factory. The token is
    resolved on every request, so callable resolvers can implement refresh.

    Example::

        async with AsyncAskii(token=jwt) as client:
            keys = await client.keys.list()
            print(keys.user_id)
    """

    def __init__(
        self,
        token: TokenSource | None = None,
        *,
        config: AskiiConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or AskiiConfig.from_env()
        resolver_source = token if token is not None else self._config.token
        self._resolver: AsyncResolver = make_async_resolver(resolver_source)
        self._transport = HTTPTransport(self._config, sync=False, http_client=http_client)
        self.keys = AsyncKeysResource(self)
        self.models = AsyncModelsResource(self)

    # ------------------------------------------------------------------
    # public escape hatch
    # ------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotent: bool = True,
        cache_ttl: float | None = None,
        cache_resource: str | None = None,
        cache_op: str | None = None,
        cache_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send an arbitrary request to the Askii API.

        The ``mpass_token`` is injected for you. Provide ``cache_resource`` +
        ``cache_op`` + ``cache_ttl`` if you want the response cached. Pass
        ``idempotent=False`` for mutating endpoints — the SDK then skips the
        retry policy so a transient 5xx cannot double-apply the mutation.
        """
        return await self._arequest(
            method,
            path,
            body=body or {},
            idempotent=idempotent,
            cache_resource=cache_resource,
            cache_op=cache_op,
            cache_args=cache_args,
            cache_ttl=cache_ttl,
        )

    # ------------------------------------------------------------------
    # internal helpers used by resources
    # ------------------------------------------------------------------

    async def _arequest(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any],
        idempotent: bool = True,
        cache_resource: str | None = None,
        cache_op: str | None = None,
        cache_args: dict[str, Any] | None = None,
        cache_ttl: float | None = None,
    ) -> dict[str, Any]:
        token = await self._resolver()
        # mpass_token is set last so it cannot be shadowed by a caller-supplied key in body.
        body_with_token: dict[str, Any] = {**body, "mpass_token": token}
        cache_key: str | None = None
        if cache_resource and cache_op and cache_ttl and cache_ttl > 0:
            cache_key = build_cache_key(token, cache_resource, cache_op, cache_args)
        return await self._transport.arequest(
            method,
            path,
            body=body_with_token,
            idempotent=idempotent,
            cache_key=cache_key,
            cache_ttl=cache_ttl,
        )

    async def _ainvalidate(self, resource: str) -> None:
        token = await self._resolver()
        await self._config.cache.adelete_prefix(build_resource_prefix(token, resource))

    @property
    def config(self) -> AskiiConfig:
        return self._config

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    async def aclose(self) -> None:
        await self._transport.aclose()

    async def __aenter__(self) -> AsyncAskii:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


__all__ = ["AsyncAskii"]
