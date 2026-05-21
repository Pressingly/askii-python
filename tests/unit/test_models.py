"""Tests for the Pydantic request/response models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from askii import (
    AvailableModelsResponse,
    KeyConfig,
    KeyInfo,
    ListKeysResponse,
    MemoryMode,
    ProvisionKeyRequest,
    ProvisionKeyResponse,
    RevokeKeyResponse,
    UpdateKeyModelResponse,
)


def test_memory_mode_enum_values() -> None:
    assert MemoryMode.PKG.value == "pkg"
    assert MemoryMode.CKG.value == "ckg"
    assert MemoryMode.ALL.value == "all"


def test_provision_key_request_defaults() -> None:
    req = ProvisionKeyRequest()
    assert req.duration_days == 90
    assert req.memory_enabled is False
    assert req.memory_mode is None
    assert req.models is None
    assert req.default_model is None
    assert req.key_alias is None


def test_provision_key_request_duration_lower_bound() -> None:
    with pytest.raises(ValidationError):
        ProvisionKeyRequest(duration_days=0)


def test_provision_key_request_duration_upper_bound() -> None:
    with pytest.raises(ValidationError):
        ProvisionKeyRequest(duration_days=366)


def test_provision_key_request_dump_excludes_none() -> None:
    req = ProvisionKeyRequest(key_alias="x", duration_days=10)
    dumped = req.model_dump(exclude_none=True, mode="json")
    assert "memory_mode" not in dumped
    assert "models" not in dumped
    assert "default_model" not in dumped
    assert dumped["key_alias"] == "x"
    assert dumped["duration_days"] == 10


def test_provision_key_response_secret_str_is_obscured_in_repr() -> None:
    resp = ProvisionKeyResponse(
        api_key="sk-abc123abc123abc123",
        key_name="key-1",
        user_id="user-1",
    )
    assert "sk-abc" not in repr(resp)
    assert resp.api_key.get_secret_value() == "sk-abc123abc123abc123"


def test_extra_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ListKeysResponse(user_id="u", keys=[], surprise="bonus")  # type: ignore[call-arg]


def test_key_info_round_trip() -> None:
    payload = {
        "key_name": "n",
        "key_alias": "a",
        "spend": 1.5,
        "models": ["gpt-4o"],
        "memory_enabled": True,
        "memory_mode": "ckg",
    }
    info = KeyInfo.model_validate(payload)
    assert info.spend == 1.5
    assert info.memory_mode is MemoryMode.CKG


def test_list_keys_response_parses_dates() -> None:
    payload = {
        "user_id": "u-1",
        "keys": [
            {
                "key_name": "n",
                "spend": 0.0,
                "models": [],
                "memory_enabled": False,
                "created_at": "2026-05-01T00:00:00Z",
                "expires": "2026-08-01T00:00:00Z",
            }
        ],
    }
    parsed = ListKeysResponse.model_validate(payload)
    assert parsed.keys[0].created_at is not None
    assert parsed.keys[0].expires is not None


def test_revoke_key_response_parses() -> None:
    resp = RevokeKeyResponse.model_validate({"revoked": True, "detail": "ok"})
    assert resp.revoked is True


def test_key_config_parses() -> None:
    cfg = KeyConfig.model_validate({"key_name": "n", "models": [], "memory_enabled": False})
    assert cfg.memory_enabled is False
    assert cfg.models == []


def test_update_key_model_response_parses() -> None:
    resp = UpdateKeyModelResponse.model_validate(
        {"updated": True, "key_name": "n", "models": ["gpt-4o"], "default_model": "gpt-4o"}
    )
    assert resp.updated is True
    assert resp.default_model == "gpt-4o"


def test_available_models_response_parses_model_name() -> None:
    resp = AvailableModelsResponse.model_validate(
        {"models": [{"model_name": "gpt-4o"}, {"model_name": "claude-sonnet-4"}]}
    )
    assert [m.model_name for m in resp.models] == ["gpt-4o", "claude-sonnet-4"]
