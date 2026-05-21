"""Tests for the exception hierarchy and response → exception mapping."""

from __future__ import annotations

import httpx
import pytest

from askii import (
    AskiiAPIError,
    AskiiAuthError,
    AskiiNotFoundError,
    AskiiRateLimitError,
    AskiiServerError,
    AskiiValidationError,
    FieldError,
)
from askii._errors import map_response_to_error


def _make_response(status: int, body: object | None = None, headers: dict[str, str] | None = None) -> httpx.Response:
    import json

    request = httpx.Request("POST", "https://api.askii.test/x")
    content = b""
    final_headers = {"content-type": "application/json"}
    if headers:
        final_headers.update(headers)
    if body is not None:
        content = json.dumps(body).encode()
    return httpx.Response(status, headers=final_headers, content=content, request=request)


def test_field_error_path_dots_loc() -> None:
    fe = FieldError(loc=("body", "duration_days"), msg="too big", type="value_error")
    assert fe.path == "body.duration_days"


def test_field_error_path_handles_ints() -> None:
    fe = FieldError(loc=("body", 0, "key"), msg="x", type="t")
    assert fe.path == "body.0.key"


def test_maps_401_to_auth_error() -> None:
    err = map_response_to_error(_make_response(401, {"detail": "expired"}))
    assert isinstance(err, AskiiAuthError)
    assert err.status == 401


def test_maps_403_to_auth_error() -> None:
    err = map_response_to_error(_make_response(403, {"detail": "forbidden"}))
    assert isinstance(err, AskiiAuthError)


def test_maps_404_to_not_found() -> None:
    err = map_response_to_error(_make_response(404, {"detail": "missing"}))
    assert isinstance(err, AskiiNotFoundError)


def test_maps_422_to_validation_error_with_field_errors() -> None:
    body = {
        "detail": [
            {"loc": ["body", "duration_days"], "msg": "out of range", "type": "value_error"},
            {"loc": ["body", "key_alias"], "msg": "too short", "type": "string_too_short"},
        ]
    }
    err = map_response_to_error(_make_response(422, body))
    assert isinstance(err, AskiiValidationError)
    assert len(err.field_errors) == 2
    assert err.field_errors[0].path == "body.duration_days"
    assert err.field_errors[1].type == "string_too_short"


def test_maps_422_with_non_list_detail_yields_empty_field_errors() -> None:
    err = map_response_to_error(_make_response(422, {"detail": "boom"}))
    assert isinstance(err, AskiiValidationError)
    assert err.field_errors == []


def test_maps_429_to_rate_limit_with_retry_after() -> None:
    err = map_response_to_error(_make_response(429, {"detail": "slow down"}, {"retry-after": "5"}))
    assert isinstance(err, AskiiRateLimitError)
    assert err.retry_after == 5.0


def test_429_with_invalid_retry_after_is_none() -> None:
    err = map_response_to_error(_make_response(429, {"detail": "x"}, {"retry-after": "soon"}))
    assert isinstance(err, AskiiRateLimitError)
    assert err.retry_after is None


def test_maps_500_to_server_error() -> None:
    err = map_response_to_error(_make_response(500, {"detail": "boom"}))
    assert isinstance(err, AskiiServerError)


def test_maps_503_to_server_error() -> None:
    assert isinstance(map_response_to_error(_make_response(503)), AskiiServerError)


def test_maps_418_to_generic_api_error() -> None:
    err = map_response_to_error(_make_response(418, {"detail": "teapot"}))
    assert isinstance(err, AskiiAPIError)
    assert not isinstance(err, (AskiiAuthError, AskiiNotFoundError, AskiiValidationError))


def test_request_id_pulled_from_header() -> None:
    err = map_response_to_error(_make_response(500, {"detail": "x"}, {"x-request-id": "abc-123"}))
    assert err.request_id == "abc-123"


def test_request_id_falls_back_to_correlation_id_header() -> None:
    err = map_response_to_error(_make_response(500, {"detail": "x"}, {"x-correlation-id": "corr-42"}))
    assert err.request_id == "corr-42"


def test_non_json_body_is_preserved_as_text() -> None:
    request = httpx.Request("POST", "https://api.askii.test/x")
    response = httpx.Response(500, content=b"plain text boom", request=request)
    err = map_response_to_error(response)
    assert isinstance(err, AskiiServerError)
    assert "plain text boom" in str(err.detail)


def test_format_includes_request_id_when_present() -> None:
    err = map_response_to_error(_make_response(401, {"detail": "x"}, {"x-request-id": "rid"}))
    assert "rid" in str(err)


def test_validation_error_can_round_trip_field_errors() -> None:
    fe = FieldError(loc=("a",), msg="m", type="t")
    err = AskiiValidationError(422, "detail", field_errors=[fe])
    assert err.field_errors[0] is fe


def test_rate_limit_error_without_retry_after_is_none() -> None:
    err = AskiiRateLimitError(429, "rl")
    assert err.retry_after is None


def test_api_error_repr_includes_status() -> None:
    err = AskiiAPIError(418, {"detail": "teapot"})
    assert "418" in str(err)


def test_validation_error_with_dict_loc_handles_tuple_input() -> None:
    err = map_response_to_error(_make_response(422, {"detail": [{"loc": ("body", 1), "msg": "x", "type": "y"}]}))
    assert isinstance(err, AskiiValidationError)
    assert err.field_errors[0].loc == ("body", 1)


@pytest.mark.parametrize("status", [200, 201, 204, 299])
def test_2xx_doesnt_map_to_error(status: int) -> None:
    # map_response_to_error is only called for non-2xx; sanity check it still
    # produces *something* and doesn't blow up.
    err = map_response_to_error(_make_response(status, {"ok": True}))
    assert isinstance(err, AskiiAPIError)
