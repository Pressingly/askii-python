"""``client.keys.*`` — Platform Key Management resource."""

from __future__ import annotations

from typing import TYPE_CHECKING

from askii._endpoints import (
    GET_KEY_CONFIG,
    LIST_KEYS,
    PROVISION_KEY,
    REVOKE_KEY,
    UPDATE_KEY_MODEL,
)
from askii.models import (
    GetKeyConfigRequest,
    KeyConfig,
    ListKeysResponse,
    ProvisionKeyRequest,
    ProvisionKeyResponse,
    RevokeKeyRequest,
    RevokeKeyResponse,
    UpdateKeyModelRequest,
    UpdateKeyModelResponse,
)
from askii.models._shared import MemoryMode
from askii.resources._base import _AsyncResource, _SyncResource

if TYPE_CHECKING:
    from askii._client.async_client import AsyncAskii  # noqa: F401 — used in string forward ref
    from askii._client.sync_client import Askii  # noqa: F401 — used in string forward ref


_RESOURCE = "keys"

# Alias avoids `list[str]` resolving to the class's `list()` method in annotations.
_StrList = list[str]


def _provision_body(req: ProvisionKeyRequest) -> dict[str, object]:
    return req.model_dump(exclude_none=True, mode="json")


def _revoke_body(key: str) -> dict[str, object]:
    return RevokeKeyRequest(key=key).model_dump(mode="json")


def _get_config_body(key: str) -> dict[str, object]:
    return GetKeyConfigRequest(key=key).model_dump(mode="json")


def _update_body(key: str, models: _StrList, default_model: str | None) -> dict[str, object]:
    return UpdateKeyModelRequest(
        key=key,
        models=models,
        default_model=default_model,
    ).model_dump(mode="json", exclude_none=True)


class AsyncKeysResource(_AsyncResource["AsyncAskii"]):
    """Async ``keys`` namespace."""

    async def provision(
        self,
        *,
        key_alias: str | None = None,
        duration_days: int = 90,
        memory_enabled: bool = False,
        memory_mode: MemoryMode | None = None,
        models: _StrList | None = None,
        default_model: str | None = None,
    ) -> ProvisionKeyResponse:
        """Provision a new LiteLLM virtual key."""
        req = ProvisionKeyRequest(
            key_alias=key_alias,
            duration_days=duration_days,
            memory_enabled=memory_enabled,
            memory_mode=memory_mode,
            models=models,
            default_model=default_model,
        )
        data = await self._client._arequest("POST", PROVISION_KEY, body=_provision_body(req))
        await self._client._ainvalidate(_RESOURCE)
        return ProvisionKeyResponse.model_validate(data)

    async def list(self, *, cache_ttl: float | None = None) -> ListKeysResponse:
        """List active keys for the authenticated user."""
        data = await self._client._arequest(
            "POST",
            LIST_KEYS,
            body={},
            cache_resource=_RESOURCE,
            cache_op="list",
            cache_ttl=cache_ttl,
        )
        return ListKeysResponse.model_validate(data)

    async def revoke(self, *, key: str) -> RevokeKeyResponse:
        """Revoke a key by ``sk-...`` value or ``key_alias``."""
        data = await self._client._arequest("POST", REVOKE_KEY, body=_revoke_body(key))
        await self._client._ainvalidate(_RESOURCE)
        return RevokeKeyResponse.model_validate(data)

    async def get_config(self, *, key: str, cache_ttl: float | None = None) -> KeyConfig:
        """Return model configuration for one key."""
        data = await self._client._arequest(
            "POST",
            GET_KEY_CONFIG,
            body=_get_config_body(key),
            cache_resource=_RESOURCE,
            cache_op="get_config",
            cache_args={"key": key},
            cache_ttl=cache_ttl,
        )
        return KeyConfig.model_validate(data)

    async def update_model(
        self,
        *,
        key: str,
        models: _StrList,
        default_model: str | None = None,
    ) -> UpdateKeyModelResponse:
        """Update the model configuration for a key."""
        data = await self._client._arequest(
            "POST",
            UPDATE_KEY_MODEL,
            body=_update_body(key, models, default_model),
        )
        await self._client._ainvalidate(_RESOURCE)
        return UpdateKeyModelResponse.model_validate(data)


class KeysResource(_SyncResource["Askii"]):
    """Sync ``keys`` namespace."""

    def provision(
        self,
        *,
        key_alias: str | None = None,
        duration_days: int = 90,
        memory_enabled: bool = False,
        memory_mode: MemoryMode | None = None,
        models: _StrList | None = None,
        default_model: str | None = None,
    ) -> ProvisionKeyResponse:
        """Provision a new LiteLLM virtual key."""
        req = ProvisionKeyRequest(
            key_alias=key_alias,
            duration_days=duration_days,
            memory_enabled=memory_enabled,
            memory_mode=memory_mode,
            models=models,
            default_model=default_model,
        )
        data = self._client._request("POST", PROVISION_KEY, body=_provision_body(req))
        self._client._invalidate(_RESOURCE)
        return ProvisionKeyResponse.model_validate(data)

    def list(self, *, cache_ttl: float | None = None) -> ListKeysResponse:
        """List active keys for the authenticated user."""
        data = self._client._request(
            "POST",
            LIST_KEYS,
            body={},
            cache_resource=_RESOURCE,
            cache_op="list",
            cache_ttl=cache_ttl,
        )
        return ListKeysResponse.model_validate(data)

    def revoke(self, *, key: str) -> RevokeKeyResponse:
        """Revoke a key by ``sk-...`` value or ``key_alias``."""
        data = self._client._request("POST", REVOKE_KEY, body=_revoke_body(key))
        self._client._invalidate(_RESOURCE)
        return RevokeKeyResponse.model_validate(data)

    def get_config(self, *, key: str, cache_ttl: float | None = None) -> KeyConfig:
        """Return model configuration for one key."""
        data = self._client._request(
            "POST",
            GET_KEY_CONFIG,
            body=_get_config_body(key),
            cache_resource=_RESOURCE,
            cache_op="get_config",
            cache_args={"key": key},
            cache_ttl=cache_ttl,
        )
        return KeyConfig.model_validate(data)

    def update_model(
        self,
        *,
        key: str,
        models: _StrList,
        default_model: str | None = None,
    ) -> UpdateKeyModelResponse:
        """Update the model configuration for a key."""
        data = self._client._request(
            "POST",
            UPDATE_KEY_MODEL,
            body=_update_body(key, models, default_model),
        )
        self._client._invalidate(_RESOURCE)
        return UpdateKeyModelResponse.model_validate(data)


__all__ = ["AsyncKeysResource", "KeysResource"]
