"""Canonical key-to-object records for the content-addressed cache."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    parse_canonical_json,
    validate_hash,
    validate_json_value,
)

_RECORD_SCHEMA_VERSION = "1.0"
_NAMESPACE_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(frozen=True, slots=True)
class CacheRecord:
    """Canonical mapping from one namespace/key to a content-addressed object."""
    namespace: str
    key: str
    object_hash: str
    byte_length: int
    media_type: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = field(default=_RECORD_SCHEMA_VERSION, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, str) or _NAMESPACE_RE.fullmatch(self.namespace) is None:
            raise ArtifactValidationError("cache_record_invalid", "/namespace", "invalid cache namespace")
        validate_hash(self.key, "/key")
        validate_hash(self.object_hash, "/object_hash")
        if isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int) or self.byte_length < 0:
            raise ArtifactValidationError("cache_record_invalid", "/byte_length", "must be non-negative")
        if not isinstance(self.media_type, str) or not self.media_type or len(self.media_type) > 128:
            raise ArtifactValidationError("cache_record_invalid", "/media_type", "invalid media type")
        metadata = dict(self.metadata)
        validate_json_value(metadata, "/metadata")
        object.__setattr__(self, "metadata", metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "namespace": self.namespace,
            "key": self.key,
            "object_hash": self.object_hash,
            "byte_length": self.byte_length,
            "media_type": self.media_type,
            "metadata": dict(self.metadata),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CacheRecord":
        required = {
            "schema_version",
            "namespace",
            "key",
            "object_hash",
            "byte_length",
            "media_type",
            "metadata",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ArtifactValidationError("cache_record_invalid", "/", "record fields are not closed")
        if value["schema_version"] != _RECORD_SCHEMA_VERSION:
            raise ArtifactValidationError("cache_record_invalid", "/schema_version", "unsupported record schema")
        return cls(
            namespace=value["namespace"],
            key=value["key"],
            object_hash=value["object_hash"],
            byte_length=value["byte_length"],
            media_type=value["media_type"],
            metadata=dict(value["metadata"]),
        )

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "CacheRecord":
        try:
            parsed = parse_canonical_json(payload)
        except ValueError as exc:
            raise ArtifactValidationError("cache_record_invalid", "/", str(exc)) from exc
        if not isinstance(parsed, Mapping):
            raise ArtifactValidationError("cache_record_invalid", "/", "record must be an object")
        return cls.from_dict(parsed)


__all__ = ["CacheRecord"]
