"""Contract test for the centralized endpoint constants.

If anyone copy-pastes a constant by mistake, or deletes one that resources still
import, this test fails before pytest ever exercises the resource code.
"""

from __future__ import annotations

from askii import _endpoints


def test_all_endpoints_are_non_empty_platform_paths() -> None:
    exported = _endpoints.__all__
    assert exported, "_endpoints.__all__ must list every public constant"
    for name in exported:
        value = getattr(_endpoints, name)
        assert isinstance(value, str), f"{name} must be a str, got {type(value).__name__}"
        assert value, f"{name} must not be empty"
        assert value.startswith("/platform/"), f"{name}={value!r} must start with /platform/"


def test_endpoint_constants_are_unique() -> None:
    values = [getattr(_endpoints, name) for name in _endpoints.__all__]
    assert len(values) == len(set(values)), f"duplicate endpoint paths in _endpoints: {values}"


def test_expected_endpoints_present() -> None:
    """Every Platform Key Management endpoint the SDK wraps today is exported."""
    expected = {
        "PROVISION_KEY",
        "LIST_KEYS",
        "REVOKE_KEY",
        "AVAILABLE_MODELS",
        "GET_KEY_CONFIG",
        "UPDATE_KEY_MODEL",
    }
    assert expected.issubset(set(_endpoints.__all__))
