"""Enums and small value types shared across resource models."""

from __future__ import annotations

from enum import Enum


class MemoryMode(str, Enum):
    """Backing memory engine for an Askii virtual key."""

    PKG = "pkg"
    CKG = "ckg"
    ALL = "all"


__all__ = ["MemoryMode"]
