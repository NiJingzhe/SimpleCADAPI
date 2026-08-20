"""Typed references shared by PartDefinition and AssemblyDefinition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..placement import Placement
from .canonical import (
    ArtifactValidationError,
    content_hash,
    validate_hash,
    validate_logical_id,
    validate_relative_path,
    validate_revision,
)


def _closed(data: Mapping[str, Any], required: set[str], path: str) -> None:
    if not isinstance(data, Mapping):
        raise ArtifactValidationError("type_invalid", path, "expected an object")
    actual = set(data)
    if actual != required:
        missing = sorted(required - actual)
        unknown = sorted(actual - required)
        detail = f"missing={missing}, unknown={unknown}"
        raise ArtifactValidationError("fields_invalid", path, detail)


@dataclass(frozen=True, slots=True)
class BlobRef:
    path: str
    sha256: str
    byte_length: int
    media_type: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", validate_relative_path(self.path, "/blob/path"))
        object.__setattr__(self, "sha256", validate_hash(self.sha256, "/blob/sha256"))
        if isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int) or self.byte_length < 0:
            raise ArtifactValidationError("size_invalid", "/blob/byte_length", "must be a non-negative integer")
        if not isinstance(self.media_type, str) or not self.media_type or len(self.media_type) > 128:
            raise ArtifactValidationError("media_type_invalid", "/blob/media_type", "invalid media type")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "media_type": self.media_type,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/blob") -> "BlobRef":
        _closed(data, {"path", "sha256", "byte_length", "media_type"}, path)
        try:
            return cls(str(data["path"]), str(data["sha256"]), data["byte_length"], str(data["media_type"]))
        except ArtifactValidationError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactValidationError("blob_ref_invalid", path, str(exc)) from exc


@dataclass(frozen=True, slots=True)
class FileInputSnapshot:
    path: str
    byte_length: int
    sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", validate_relative_path(self.path, "/file_input/path"))
        if isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int) or self.byte_length < 0:
            raise ArtifactValidationError("size_invalid", "/file_input/byte_length", "must be non-negative")
        object.__setattr__(self, "sha256", validate_hash(self.sha256, "/file_input/sha256"))

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "byte_length": self.byte_length, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/file_input") -> "FileInputSnapshot":
        _closed(data, {"path", "byte_length", "sha256"}, path)
        return cls(str(data["path"]), data["byte_length"], str(data["sha256"]))


@dataclass(frozen=True, slots=True)
class MaterialRef:
    material_id: str
    path: str
    revision: str
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "material_id", validate_logical_id(self.material_id, "/material_ref/material_id"))
        object.__setattr__(self, "path", validate_relative_path(self.path, "/material_ref/path"))
        object.__setattr__(self, "revision", validate_revision(self.revision, "/material_ref/revision"))
        object.__setattr__(self, "sha256", validate_hash(self.sha256, "/material_ref/sha256"))
        if isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int) or self.byte_length < 0:
            raise ArtifactValidationError("size_invalid", "/material_ref/byte_length", "must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "path": self.path,
            "revision": self.revision,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/material_ref") -> "MaterialRef":
        _closed(data, {"material_id", "path", "revision", "sha256", "byte_length"}, path)
        return cls(
            str(data["material_id"]),
            str(data["path"]),
            str(data["revision"]),
            str(data["sha256"]),
            data["byte_length"],
        )


@dataclass(frozen=True, slots=True)
class ConnectorInterface:
    connector_id: str
    name: str | None
    anchor_kind: str
    local_frame: Mapping[str, Any]
    binding: Mapping[str, Any] | None
    source_component_id: str | None = None
    source_connector_id: str | None = None
    interface_hash: str = ""
    binding_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "connector_id", validate_logical_id(self.connector_id, "/connector/connector_id"))
        if self.name is not None and (not isinstance(self.name, str) or not self.name.strip()):
            raise ArtifactValidationError("name_invalid", "/connector/name", "name must be null or non-empty")
        if self.anchor_kind not in {"geometry", "placement", "public"}:
            raise ArtifactValidationError("connector_invalid", "/connector/anchor_kind", "unsupported anchor kind")
        try:
            frame = Placement(**dict(self.local_frame)).to_dict()
        except (TypeError, ValueError) as exc:
            raise ArtifactValidationError("frame_invalid", "/connector/local_frame", str(exc)) from exc
        object.__setattr__(self, "local_frame", frame)
        if self.anchor_kind == "geometry" and self.binding is None:
            raise ArtifactValidationError("connector_invalid", "/connector/binding", "geometry connector requires binding")
        if self.anchor_kind != "geometry" and self.binding is not None:
            raise ArtifactValidationError("connector_invalid", "/connector/binding", "only geometry connector accepts binding")
        if self.anchor_kind == "public":
            if self.source_component_id is None or self.source_connector_id is None:
                raise ArtifactValidationError("connector_invalid", "/connector/source_component_id", "public connector requires a source")
            object.__setattr__(self, "source_component_id", validate_logical_id(self.source_component_id, "/connector/source_component_id"))
            object.__setattr__(self, "source_connector_id", validate_logical_id(self.source_connector_id, "/connector/source_connector_id"))
        elif self.source_component_id is not None or self.source_connector_id is not None:
            raise ArtifactValidationError("connector_invalid", "/connector/source_component_id", "source is only valid for public connectors")
        interface_payload = {
            "connector_id": self.connector_id,
            "name": self.name,
            "anchor_kind": self.anchor_kind,
            "local_frame": frame,
            "source_component_id": self.source_component_id,
            "source_connector_id": self.source_connector_id,
            "units": "mm",
        }
        binding_payload = dict(self.binding) if self.binding is not None else None
        expected_interface = content_hash(interface_payload)
        expected_binding = content_hash({"binding": binding_payload})
        if self.interface_hash and self.interface_hash != expected_interface:
            raise ArtifactValidationError("hash_invalid", "/connector/interface_hash", "hash does not match interface")
        if self.binding_hash and self.binding_hash != expected_binding:
            raise ArtifactValidationError("hash_invalid", "/connector/binding_hash", "hash does not match binding")
        object.__setattr__(self, "interface_hash", expected_interface)
        object.__setattr__(self, "binding_hash", expected_binding)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "connector_id": self.connector_id,
            "name": self.name,
            "anchor_kind": self.anchor_kind,
            "local_frame": dict(self.local_frame),
            "binding": dict(self.binding) if self.binding is not None else None,
            "interface_hash": self.interface_hash,
            "binding_hash": self.binding_hash,
        }
        if self.anchor_kind == "public":
            payload["source_component_id"] = self.source_component_id
            payload["source_connector_id"] = self.source_connector_id
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/connector") -> "ConnectorInterface":
        base = {
            "connector_id", "name", "anchor_kind", "local_frame", "binding",
            "interface_hash", "binding_hash",
        }
        actual = set(data)
        missing = sorted(base - actual)
        if missing:
            raise ArtifactValidationError("fields_invalid", path, f"missing={missing}")
        extra = actual - base
        allowed_source = {"source_component_id", "source_connector_id"}
        if extra and extra != allowed_source:
            raise ArtifactValidationError("fields_invalid", path, f"unknown={sorted(extra)}")
        anchor_kind = str(data["anchor_kind"])
        if anchor_kind == "public" and extra != allowed_source:
            raise ArtifactValidationError("fields_invalid", path, "public connector source fields are required")
        if anchor_kind != "public" and extra:
            raise ArtifactValidationError("fields_invalid", path, "source fields are only valid for public connectors")
        return cls(
            connector_id=str(data["connector_id"]),
            name=data["name"],
            anchor_kind=anchor_kind,
            local_frame=dict(data["local_frame"]),
            binding=dict(data["binding"]) if data["binding"] is not None else None,
            source_component_id=(str(data["source_component_id"]) if "source_component_id" in data else None),
            source_connector_id=(str(data["source_connector_id"]) if "source_connector_id" in data else None),
            interface_hash=str(data["interface_hash"]),
            binding_hash=str(data["binding_hash"]),
        )


@dataclass(frozen=True, slots=True)
class PartRef:
    definition_id: str
    definition_kind: str
    path: str
    revision: str
    content_hash: str
    byte_length: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition_id", validate_logical_id(self.definition_id, "/part_ref/definition_id"))
        if self.definition_kind not in {"single_solid", "assembly"}:
            raise ArtifactValidationError("definition_kind_invalid", "/part_ref/definition_kind", "unsupported definition kind")
        object.__setattr__(self, "path", validate_relative_path(self.path, "/part_ref/path"))
        object.__setattr__(self, "revision", validate_revision(self.revision, "/part_ref/revision"))
        object.__setattr__(self, "content_hash", validate_hash(self.content_hash, "/part_ref/content_hash"))
        if isinstance(self.byte_length, bool) or not isinstance(self.byte_length, int) or self.byte_length < 0:
            raise ArtifactValidationError("size_invalid", "/part_ref/byte_length", "must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "definition_kind": self.definition_kind,
            "path": self.path,
            "revision": self.revision,
            "content_hash": self.content_hash,
            "byte_length": self.byte_length,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/part_ref") -> "PartRef":
        _closed(data, {"definition_id", "definition_kind", "path", "revision", "content_hash", "byte_length"}, path)
        return cls(
            str(data["definition_id"]),
            str(data["definition_kind"]),
            str(data["path"]),
            str(data["revision"]),
            str(data["content_hash"]),
            data["byte_length"],
        )


@dataclass(frozen=True, slots=True)
class PartInstance:
    instance_id: str
    definition_id: str
    name: str | None
    placement: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "instance_id", validate_logical_id(self.instance_id, "/instance/instance_id"))
        object.__setattr__(self, "definition_id", validate_logical_id(self.definition_id, "/instance/definition_id"))
        if self.name is not None and (not isinstance(self.name, str) or not self.name.strip()):
            raise ArtifactValidationError("name_invalid", "/instance/name", "name must be null or non-empty")
        try:
            object.__setattr__(self, "placement", Placement(**dict(self.placement)).to_dict())
        except (TypeError, ValueError) as exc:
            raise ArtifactValidationError("frame_invalid", "/instance/placement", str(exc)) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "definition_id": self.definition_id,
            "name": self.name,
            "placement": dict(self.placement),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/instance") -> "PartInstance":
        _closed(data, {"instance_id", "definition_id", "name", "placement"}, path)
        return cls(str(data["instance_id"]), str(data["definition_id"]), data["name"], dict(data["placement"]))


@dataclass(frozen=True, slots=True)
class InterfaceHashes:
    geometry: str
    connectors: Mapping[str, str]
    bindings: Mapping[str, str]
    material: str | None

    def __post_init__(self) -> None:
        validate_hash(self.geometry, "/interface_hashes/geometry")
        for key, value in self.connectors.items():
            validate_logical_id(key, "/interface_hashes/connectors")
            validate_hash(value, f"/interface_hashes/connectors/{key}")
        for key, value in self.bindings.items():
            validate_logical_id(key, "/interface_hashes/bindings")
            validate_hash(value, f"/interface_hashes/bindings/{key}")
        if self.material is not None:
            validate_hash(self.material, "/interface_hashes/material")

    def to_dict(self) -> dict[str, Any]:
        return {
            "geometry": self.geometry,
            "connectors": dict(sorted(self.connectors.items())),
            "bindings": dict(sorted(self.bindings.items())),
            "material": self.material,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], path: str = "/interface_hashes") -> "InterfaceHashes":
        _closed(data, {"geometry", "connectors", "bindings", "material"}, path)
        return cls(
            str(data["geometry"]),
            {str(k): str(v) for k, v in dict(data["connectors"]).items()},
            {str(k): str(v) for k, v in dict(data["bindings"]).items()},
            str(data["material"]) if data["material"] is not None else None,
        )


__all__ = [
    "BlobRef",
    "ConnectorInterface",
    "FileInputSnapshot",
    "InterfaceHashes",
    "MaterialRef",
    "PartInstance",
    "PartRef",
]
