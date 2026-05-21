"""Logging utilities for the askii client.

The library never force-configures logging on import. Consumers call
:func:`configure_logging` once at boot time if they want askii's opinionated
JSON handler. Without that call, askii logs propagate to whatever the consumer
has configured.

Two filters do the security-sensitive work:

* :class:`RedactionFilter` masks known-secret keys and inline ``sk-`` tokens
  in log records.
* :class:`CorrelationIdFilter` attaches the current contextvar correlation ID
  to every record so JSON output and consumer filters can pivot on it.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

LOGGER_NAME = "askii"
_REDACTED = "***redacted***"
_REDACT_KEYS = frozenset(
    {
        "mpass_token",
        "api_key",
        "apikey",
        "authorization",
        "x-api-key",
        "token",
        "access_token",
        "refresh_token",
        "id_token",
    }
)
_INLINE_SECRETS = re.compile(r"sk-[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")

_correlation_id_var: ContextVar[str | None] = ContextVar("askii_correlation_id", default=None)

_STANDARD_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


def get_correlation_id() -> str | None:
    """Return the current correlation ID, if one is bound."""
    return _correlation_id_var.get()


def bind_correlation_id(value: str | None = None) -> Token[str | None]:
    """Bind a correlation ID for the current async/thread context.

    Returns a token that can be passed to :func:`reset_correlation_id` to
    restore the previous value.
    """
    return _correlation_id_var.set(value or uuid.uuid4().hex)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation ID to its prior value."""
    _correlation_id_var.reset(token)


class CorrelationIdFilter(logging.Filter):
    """Attach the current contextvar correlation ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_var.get()
        return True


class RedactionFilter(logging.Filter):
    """Mask known-secret fields in log records before they're formatted."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_inline(record.msg)
        if isinstance(record.args, dict):
            record.args = _redact_value(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(_redact_value(a) for a in record.args)
        for attr in list(record.__dict__):
            if attr in _STANDARD_RECORD_ATTRS or attr == "correlation_id":
                continue
            record.__dict__[attr] = _redact_value(record.__dict__[attr], top_key=attr)
        return True


def _redact_inline(text: str) -> str:
    return _INLINE_SECRETS.sub(_REDACTED, text)


def _redact_value(value: Any, *, top_key: str | None = None) -> Any:
    if top_key and top_key.lower() in _REDACT_KEYS and value is not None:
        return _REDACTED
    if isinstance(value, str):
        return _redact_inline(value)
    if isinstance(value, dict):
        return {k: _redact_value(v, top_key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        rendered = [_redact_value(v) for v in value]
        return type(value)(rendered) if isinstance(value, tuple) else rendered
    return value


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line.

    Picks up arbitrary ``extra={}`` fields, the bound correlation ID, exception
    info, and stack info.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if cid := getattr(record, "correlation_id", None):
            payload["correlation_id"] = cid
        for attr, value in record.__dict__.items():
            if attr in _STANDARD_RECORD_ATTRS or attr in payload or attr == "correlation_id":
                continue
            if attr.startswith("_"):
                continue
            payload[attr] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    *,
    level: str | int = "INFO",
    json: bool = True,
    include_payloads: bool = False,
    propagate: bool = False,
) -> logging.Logger:
    """Install askii's JSON handler on the ``askii`` logger.

    Idempotent: re-calling replaces the existing handler.

    Args:
        level: Log level for the ``askii`` logger.
        json: If True, use the JSON formatter. If False, use a single-line
            human-readable formatter.
        include_payloads: Stored on the logger as ``askii_include_payloads``
            so the transport can decide whether to emit request/response
            bodies at DEBUG.
        propagate: Whether to bubble askii records up to the root logger.
            Default False keeps consumer-app logs unmolested.

    Returns:
        The configured ``askii`` logger.
    """
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    handler = logging.StreamHandler()
    if json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(correlation_id)s] %(message)s"))
    handler.addFilter(CorrelationIdFilter())
    handler.addFilter(RedactionFilter())

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = propagate
    logger.askii_include_payloads = bool(include_payloads)  # type: ignore[attr-defined]
    return logger


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return a logger under the ``askii`` namespace."""
    return logging.getLogger(name)


__all__ = [
    "LOGGER_NAME",
    "JsonFormatter",
    "CorrelationIdFilter",
    "RedactionFilter",
    "bind_correlation_id",
    "reset_correlation_id",
    "get_correlation_id",
    "configure_logging",
    "get_logger",
]
