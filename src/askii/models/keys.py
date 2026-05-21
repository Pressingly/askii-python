"""Pydantic models for the Platform Key Management endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import Field, SecretStr

from askii.models._base import AskiiModel
from askii.models._shared import MemoryMode


class ProvisionKeyRequest(AskiiModel):
    """Body for ``POST /platform/provision-key`` (sans ``mpass_token``)."""

    key_alias: str | None = None
    duration_days: Annotated[int, Field(ge=1, le=365)] = 90
    memory_enabled: bool = False
    memory_mode: MemoryMode | None = None
    models: list[str] | None = None
    default_model: str | None = None


class ProvisionKeyResponse(AskiiModel):
    """Response from ``POST /platform/provision-key``.

    Note ``api_key`` is wrapped in :class:`pydantic.SecretStr` — call
    ``.get_secret_value()`` to read the raw ``sk-...`` value, and avoid logging
    or printing the unwrapped form.
    """

    api_key: SecretStr
    key_name: str
    user_id: str
    expires: datetime | None = None


class KeyInfo(AskiiModel):
    """One element of :class:`ListKeysResponse.keys`."""

    key_name: str
    key_alias: str | None = None
    created_at: datetime | None = None
    expires: datetime | None = None
    spend: float
    blocked: bool | None = None
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None
    memory_enabled: bool = False
    memory_mode: MemoryMode | None = None


class ListKeysResponse(AskiiModel):
    """Response from ``POST /platform/list-keys``."""

    user_id: str
    keys: list[KeyInfo] = Field(default_factory=list)


class RevokeKeyRequest(AskiiModel):
    """Body for ``POST /platform/revoke-key`` (sans ``mpass_token``)."""

    key: str


class RevokeKeyResponse(AskiiModel):
    """Response from ``POST /platform/revoke-key``."""

    revoked: bool
    detail: str


class GetKeyConfigRequest(AskiiModel):
    """Body for ``POST /platform/get-key-config`` (sans ``mpass_token``)."""

    key: str


class KeyConfig(AskiiModel):
    """Response from ``POST /platform/get-key-config``."""

    key_name: str
    key_alias: str | None = None
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None
    memory_enabled: bool
    memory_mode: MemoryMode | None = None


class UpdateKeyModelRequest(AskiiModel):
    """Body for ``POST /platform/update-key-model`` (sans ``mpass_token``)."""

    key: str
    models: list[str]
    default_model: str | None = None


class UpdateKeyModelResponse(AskiiModel):
    """Response from ``POST /platform/update-key-model``."""

    updated: bool
    key_name: str
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None


__all__ = [
    "ProvisionKeyRequest",
    "ProvisionKeyResponse",
    "KeyInfo",
    "ListKeysResponse",
    "RevokeKeyRequest",
    "RevokeKeyResponse",
    "GetKeyConfigRequest",
    "KeyConfig",
    "UpdateKeyModelRequest",
    "UpdateKeyModelResponse",
]
