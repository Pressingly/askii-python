"""Centralized URL paths for the Askii Platform API.

Resources import paths from here so a future rename or version-prefix change is
a single-file edit. The low-level :meth:`askii.AsyncAskii.request` escape hatch
still accepts raw paths for endpoints not yet wrapped.
"""

from __future__ import annotations

PROVISION_KEY = "/platform/provision-key"
LIST_KEYS = "/platform/list-keys"
REVOKE_KEY = "/platform/revoke-key"
AVAILABLE_MODELS = "/platform/available-models"
GET_KEY_CONFIG = "/platform/get-key-config"
UPDATE_KEY_MODEL = "/platform/update-key-model"

__all__ = [
    "PROVISION_KEY",
    "LIST_KEYS",
    "REVOKE_KEY",
    "AVAILABLE_MODELS",
    "GET_KEY_CONFIG",
    "UPDATE_KEY_MODEL",
]
