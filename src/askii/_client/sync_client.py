"""Sync client (``Askii``)."""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any

from askii._cache import build_cache_key, build_resource_prefix
from askii._config import AskiiConfig
from askii._token import SyncResolver, make_sync_resolver
from askii._transport import HTTPTransport
from askii.resources.keys import KeysResource
from askii.resources.models import ModelsResource

if TYPE_CHECKING:
    import httpx

    from askii._token import TokenSource


class Askii:
    """Synchronous client for the Askii platform API.

    Pass either a static ``mpass_token`` string or a sync callable. Async
    callables are rejected — use :class:`AsyncAskii` instead.

    Example::

        with Askii(token=jwt) as client:
            keys = client.keys.list()
            print(keys.user_id)
    """

    def __init__(
        self,
        token: TokenSource | None = None,
        *,
        config: AskiiConfig | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config or AskiiConfig.from_env()
        resolver_source = token if token is not None else self._config.token
        self._resolver: SyncResolver = make_sync_resolver(resolver_source)
        self._transport = HTTPTransport(self._config, sync=True, http_client=http_client)
        self.keys = KeysResource(self)
        self.models = ModelsResource(self)

    def request(
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
        return self._request(
            method,
            path,
            body=body or {},
            idempotent=idempotent,
            cache_resource=cache_resource,
            cache_op=cache_op,
            cache_args=cache_args,
            cache_ttl=cache_ttl,
        )

    def _request(
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
        token = self._resolver()
        # mpass_token is set last so it cannot be shadowed by a caller-supplied key in body.
        body_with_token: dict[str, Any] = {**body, "mpass_token": token}
        cache_key: str | None = None
        if cache_resource and cache_op and cache_ttl and cache_ttl > 0:
            cache_key = build_cache_key(token, cache_resource, cache_op, cache_args)
        return self._transport.request(
            method,
            path,
            body=body_with_token,
            idempotent=idempotent,
            cache_key=cache_key,
            cache_ttl=cache_ttl,
        )

    def _invalidate(self, resource: str) -> None:
        token = self._resolver()
        self._config.cache.delete_prefix(build_resource_prefix(token, resource))

    @property
    def config(self) -> AskiiConfig:
        return self._config

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> Askii:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


__all__ = ["Askii"]
