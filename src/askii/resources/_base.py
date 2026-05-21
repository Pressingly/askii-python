"""Resource base classes — wire a resource to its parent client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from askii._client.async_client import AsyncAskii
    from askii._client.sync_client import Askii


AsyncClientT = TypeVar("AsyncClientT", bound="AsyncAskii")
SyncClientT = TypeVar("SyncClientT", bound="Askii")


class _AsyncResource(Generic[AsyncClientT]):
    """Holds a reference to the parent async client. Subclasses add methods."""

    def __init__(self, client: AsyncClientT) -> None:
        self._client = client


class _SyncResource(Generic[SyncClientT]):
    """Holds a reference to the parent sync client. Subclasses add methods."""

    def __init__(self, client: SyncClientT) -> None:
        self._client = client


__all__ = ["_AsyncResource", "_SyncResource"]
