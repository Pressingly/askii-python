"""Resource namespaces — the high-level surface of the askii client."""

from askii.resources.keys import AsyncKeysResource, KeysResource
from askii.resources.models import AsyncModelsResource, ModelsResource

__all__ = [
    "AsyncKeysResource",
    "KeysResource",
    "AsyncModelsResource",
    "ModelsResource",
]
