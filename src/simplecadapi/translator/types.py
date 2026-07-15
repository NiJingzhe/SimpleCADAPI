"""Shared value types for translator backends."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional, Tuple, Union


class SupportLevel(str, Enum):
    """How faithfully a backend supports a canonical operation."""

    NATIVE = "native"
    EMULATED = "emulated"
    METADATA_ONLY = "metadata_only"
    UNSUPPORTED = "unsupported"


class TranslationOutputKind(str, Enum):
    """Storage form produced by a translation target."""

    TEXT = "text"
    BINARY = "binary"
    FILE = "file"


@dataclass(frozen=True)
class OperationCapability:
    """Declared support level for one canonical graph operation."""

    level: SupportLevel
    reason: Optional[str] = None


@dataclass(frozen=True)
class TranslationTarget:
    """One output target exposed by a translator backend."""

    target_id: str
    output_kind: TranslationOutputKind
    media_type: str
    extensions: Tuple[str, ...] = ()
    requires_external_runtime: bool = False
    option_names: Tuple[str, ...] = ()


@dataclass(frozen=True)
class BackendCapabilities:
    """Static, machine-readable capabilities of a translator backend."""

    backend_id: str
    display_name: str
    input_schema_versions: Tuple[str, ...]
    targets: Tuple[TranslationTarget, ...]
    operations: Mapping[str, OperationCapability]


@dataclass(frozen=True)
class TranslationArtifact:
    """In-memory artifact returned by a translator implementation."""

    backend_id: str
    target_id: str
    media_type: str
    suggested_suffix: str
    content: Union[str, bytes]
    metadata: Mapping[str, Any]


__all__ = [
    "BackendCapabilities",
    "OperationCapability",
    "SupportLevel",
    "TranslationArtifact",
    "TranslationOutputKind",
    "TranslationTarget",
]
