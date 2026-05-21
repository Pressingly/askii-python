"""Tests for the logging helpers — redaction, correlation IDs, formatter."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator

import pytest

from askii import bind_correlation_id, configure_logging, get_correlation_id, reset_correlation_id
from askii._logging import (
    LOGGER_NAME,
    CorrelationIdFilter,
    JsonFormatter,
    RedactionFilter,
)


@pytest.fixture
def captured_logger() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())
    handler.addFilter(RedactionFilter())
    logger = logging.getLogger("askii.tests.cap")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    yield logger, stream
    logger.handlers = []


def _records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def test_redaction_masks_known_keys(captured_logger: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = captured_logger
    logger.info("auth", extra={"mpass_token": "ey.jwt.token", "api_key": "sk-real-secret-123abc"})
    record = _records(stream)[0]
    assert record["mpass_token"] == "***redacted***"
    assert record["api_key"] == "***redacted***"


def test_redaction_masks_inline_sk_in_message(captured_logger: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = captured_logger
    logger.info("provisioned key sk-abcdef0123456789abc for user")
    record = _records(stream)[0]
    assert "sk-abc" not in record["message"]
    assert "***redacted***" in record["message"]


def test_redaction_masks_jwt_pattern(captured_logger: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = captured_logger
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJ4eHh4IjoieXl5eXkifQ.signature"
    logger.info(f"got token {jwt}")
    record = _records(stream)[0]
    assert "eyJ" not in record["message"]


def test_redaction_handles_nested_dicts(captured_logger: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = captured_logger
    logger.info("nested", extra={"body": {"authorization": "Bearer real", "ok": "yes"}})
    record = _records(stream)[0]
    body = record["body"]
    assert isinstance(body, dict)
    assert body["authorization"] == "***redacted***"
    assert body["ok"] == "yes"


def test_correlation_id_is_attached_to_record(captured_logger: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = captured_logger
    token = bind_correlation_id("corr-42")
    try:
        logger.info("hello")
    finally:
        reset_correlation_id(token)
    record = _records(stream)[0]
    assert record["correlation_id"] == "corr-42"


def test_correlation_id_is_missing_when_unbound(captured_logger: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = captured_logger
    logger.info("hello")
    record = _records(stream)[0]
    assert "correlation_id" not in record


def test_bind_correlation_id_generates_uuid_when_omitted() -> None:
    token = bind_correlation_id()
    try:
        cid = get_correlation_id()
        assert cid is not None
        assert len(cid) >= 16  # uuid4 hex is 32 chars
    finally:
        reset_correlation_id(token)


def test_configure_logging_installs_json_handler() -> None:
    logger = configure_logging(level="DEBUG", json=True, propagate=False)
    assert logger.name == LOGGER_NAME
    assert any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers)
    assert logger.level == logging.DEBUG
    # Idempotent — call again and the handler list stays at 1.
    configure_logging(level="DEBUG", json=True, propagate=False)
    assert len(logger.handlers) == 1


def test_configure_logging_can_use_plain_format() -> None:
    logger = configure_logging(level="INFO", json=False, propagate=False)
    assert logger.handlers
    handler = logger.handlers[0]
    assert handler.formatter is not None
    assert not isinstance(handler.formatter, JsonFormatter)


def test_exception_info_appears_in_json() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(CorrelationIdFilter())
    logger = logging.getLogger("askii.tests.exc")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception("caught")
    payload = json.loads(stream.getvalue().splitlines()[0])
    assert "boom" in payload["exception"]
    logger.handlers = []
