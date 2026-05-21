"""Pydantic models for the ``available-models`` endpoint."""

from __future__ import annotations

from pydantic import Field

from askii.models._base import AskiiModel


class AvailableModel(AskiiModel):
    """One model exposed by ``POST /platform/available-models``."""

    model_name: str


class AvailableModelsResponse(AskiiModel):
    """Response from ``POST /platform/available-models``."""

    models: list[AvailableModel] = Field(default_factory=list)


__all__ = ["AvailableModel", "AvailableModelsResponse"]
