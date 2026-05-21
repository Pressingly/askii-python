"""Shared base model for all askii Pydantic types."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AskiiModel(BaseModel):
    """Base for every request/response model in the askii client.

    ``extra="forbid"`` ensures CI flags schema drift the moment the upstream
    starts returning a field we haven't modeled. ``populate_by_name`` keeps
    forward-compatible renames cheap.
    """

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
        ser_json_timedelta="iso8601",
        ser_json_bytes="base64",
        validate_assignment=False,
        protected_namespaces=(),
    )


__all__ = ["AskiiModel"]
