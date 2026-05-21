"""``client.models.*`` — available-models lookup."""

from __future__ import annotations

from typing import TYPE_CHECKING

from askii._endpoints import AVAILABLE_MODELS
from askii.models import AvailableModelsResponse
from askii.resources._base import _AsyncResource, _SyncResource

if TYPE_CHECKING:
    from askii._client.async_client import AsyncAskii  # noqa: F401 — used in string forward ref
    from askii._client.sync_client import Askii  # noqa: F401 — used in string forward ref


_RESOURCE = "models"


class AsyncModelsResource(_AsyncResource["AsyncAskii"]):
    """Async ``models`` namespace."""

    async def list(self, *, cache_ttl: float | None = None) -> AvailableModelsResponse:
        """List the LLM models available on the platform."""
        data = await self._client._arequest(
            "POST",
            AVAILABLE_MODELS,
            body={},
            cache_resource=_RESOURCE,
            cache_op="list",
            cache_ttl=cache_ttl,
        )
        return AvailableModelsResponse.model_validate(data)


class ModelsResource(_SyncResource["Askii"]):
    """Sync ``models`` namespace."""

    def list(self, *, cache_ttl: float | None = None) -> AvailableModelsResponse:
        """List the LLM models available on the platform."""
        data = self._client._request(
            "POST",
            AVAILABLE_MODELS,
            body={},
            cache_resource=_RESOURCE,
            cache_op="list",
            cache_ttl=cache_ttl,
        )
        return AvailableModelsResponse.model_validate(data)


__all__ = ["AsyncModelsResource", "ModelsResource"]
