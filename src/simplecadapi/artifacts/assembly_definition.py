"""Persistent external-reference AssemblyDefinition contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import (
    ARTIFACT_SCHEMA_VERSION,
    ASSEMBLY_DEFINITION_PROFILE,
    ArtifactValidationError,
    canonical_bytes,
    content_hash,
    validate_hash,
    validate_json_value,
    validate_logical_id,
    validate_revision,
)
from .references import BlobRef, ConnectorInterface, InterfaceHashes, PartInstance, PartRef


@dataclass(frozen=True, slots=True)
class AssemblyDefinition:
    """Canonical assembly relations and external definition references."""

    definition_id: str
    revision: str
    tolerance_profile: str
    generator: Mapping[str, Any]
    definition_refs: tuple[PartRef, ...]
    instances: tuple[PartInstance, ...]
    relations: tuple[Mapping[str, Any], ...]
    grounded_instance_ids: tuple[str, ...]
    public_connectors: tuple[ConnectorInterface, ...]
    interface_hashes: InterfaceHashes
    solved_snapshot: Mapping[str, Any] | None = None
    model_ref: BlobRef | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    blobs: Mapping[str, bytes] = field(default_factory=dict, compare=False, repr=False)
    resolved_definitions: Mapping[str, Any] = field(default_factory=dict, compare=False, repr=False)

    schema_version: str = field(default=ARTIFACT_SCHEMA_VERSION, init=False)
    artifact_kind: str = field(default="assembly_definition", init=False)
    definition_kind: str = field(default="assembly", init=False)
    units: str = field(default="mm", init=False)
    profile: str = field(default=ASSEMBLY_DEFINITION_PROFILE, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "definition_id", validate_logical_id(self.definition_id, "/definition_id"))
        object.__setattr__(self, "revision", validate_revision(self.revision))
        if not isinstance(self.tolerance_profile, str) or not self.tolerance_profile or len(self.tolerance_profile) > 128:
            raise ArtifactValidationError("profile_invalid", "/tolerance_profile", "invalid tolerance profile")
        refs = tuple(self.definition_refs)
        if not all(isinstance(item, PartRef) for item in refs):
            raise ArtifactValidationError("reference_invalid", "/definition_refs", "expected PartRef values")
        ref_ids = [item.definition_id for item in refs]
        if len(set(ref_ids)) != len(ref_ids) or ref_ids != sorted(ref_ids, key=lambda item: item.encode("utf-8")):
            raise ArtifactValidationError("array_order_invalid", "/definition_refs", "refs must be unique and sorted")
        object.__setattr__(self, "definition_refs", refs)
        instances = tuple(self.instances)
        instance_ids = [item.instance_id for item in instances]
        if len(set(instance_ids)) != len(instance_ids):
            raise ArtifactValidationError("instance_invalid", "/instances", "instance IDs must be unique")
        if any(item.definition_id not in set(ref_ids) for item in instances):
            raise ArtifactValidationError("reference_missing", "/instances", "instance references an unknown definition")
        object.__setattr__(self, "instances", instances)
        relations = tuple(MappingProxyType(dict(item)) for item in self.relations)
        relation_ids: set[str] = set()
        valid_instances = set(instance_ids)
        for index, relation in enumerate(relations):
            validate_json_value(relation, f"/relations/{index}")
            relation_id = validate_logical_id(relation.get("constraint_id"), f"/relations/{index}/constraint_id")
            if relation_id in relation_ids:
                raise ArtifactValidationError("relation_invalid", f"/relations/{index}", "duplicate constraint ID")
            relation_ids.add(relation_id)
            for side in ("connector_a", "connector_b"):
                value = relation.get(side)
                if not isinstance(value, Mapping) or set(value) != {"component_id", "connector_id"}:
                    raise ArtifactValidationError("relation_invalid", f"/relations/{index}/{side}", "invalid connector ref")
                if value["component_id"] not in valid_instances:
                    raise ArtifactValidationError("reference_missing", f"/relations/{index}/{side}/component_id", "unknown instance")
                validate_logical_id(value["connector_id"], f"/relations/{index}/{side}/connector_id")
        object.__setattr__(self, "relations", relations)
        grounded = tuple(self.grounded_instance_ids)
        if len(set(grounded)) != len(grounded) or grounded != tuple(sorted(grounded, key=lambda item: item.encode("utf-8"))):
            raise ArtifactValidationError("array_order_invalid", "/grounded_instance_ids", "IDs must be unique and sorted")
        if not set(grounded).issubset(valid_instances):
            raise ArtifactValidationError("reference_missing", "/grounded_instance_ids", "unknown grounded instance")
        object.__setattr__(self, "grounded_instance_ids", grounded)
        connectors = tuple(self.public_connectors)
        connector_ids = [item.connector_id for item in connectors]
        if len(set(connector_ids)) != len(connector_ids):
            raise ArtifactValidationError("connector_invalid", "/public_connectors", "connector IDs must be unique")
        if any(item.anchor_kind != "forwarded" for item in connectors):
            raise ArtifactValidationError("connector_invalid", "/public_connectors", "assembly connectors must be forwarded")
        object.__setattr__(self, "public_connectors", connectors)
        if not isinstance(self.interface_hashes, InterfaceHashes):
            raise ArtifactValidationError("interface_invalid", "/interface_hashes", "expected InterfaceHashes")
        expected_connectors = {item.connector_id: item.interface_hash for item in connectors}
        expected_bindings = {item.connector_id: item.binding_hash for item in connectors}
        if dict(self.interface_hashes.connectors) != expected_connectors or dict(self.interface_hashes.bindings) != expected_bindings:
            raise ArtifactValidationError("interface_invalid", "/interface_hashes", "public connector hashes differ")
        if self.interface_hashes.material is not None:
            raise ArtifactValidationError("material_invalid", "/interface_hashes/material", "assembly cannot own material")
        if self.solved_snapshot is not None:
            validate_json_value(self.solved_snapshot, "/solved_snapshot")
        if self.model_ref is not None and not isinstance(self.model_ref, BlobRef):
            raise ArtifactValidationError("reference_invalid", "/model_ref", "expected BlobRef or null")
        generator = dict(self.generator)
        expected_generator = {"simplecadapi_version", "ocp_version", "python_abi", "platform_tag", "semantic_registry_version"}
        if set(generator) != expected_generator or not all(isinstance(value, str) and value for value in generator.values()):
            raise ArtifactValidationError("generator_invalid", "/generator", "generator fields are incomplete")
        object.__setattr__(self, "generator", MappingProxyType(generator))
        metadata = dict(self.metadata)
        validate_json_value(metadata, "/metadata")
        object.__setattr__(self, "metadata", MappingProxyType(metadata))
        object.__setattr__(self, "blobs", MappingProxyType({str(k): bytes(v) for k, v in self.blobs.items()}))
        object.__setattr__(self, "resolved_definitions", MappingProxyType(dict(self.resolved_definitions)))
        expected_hash = content_hash(self._manifest(content_hash_value="", solved_snapshot=None))
        if self.content_hash and validate_hash(self.content_hash, "/content_hash") != expected_hash:
            raise ArtifactValidationError("hash_invalid", "/content_hash", "content hash does not match definition")
        object.__setattr__(self, "content_hash", expected_hash)

    def _manifest(self, *, content_hash_value: str, solved_snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind,
            "definition_kind": self.definition_kind,
            "definition_id": self.definition_id,
            "revision": self.revision,
            "content_hash": content_hash_value,
            "units": self.units,
            "tolerance_profile": self.tolerance_profile,
            "profile": self.profile,
            "generator": dict(self.generator),
            "definition_refs": [item.to_dict() for item in self.definition_refs],
            "instances": [item.to_dict() for item in self.instances],
            "relations": [dict(item) for item in self.relations],
            "grounded_instance_ids": list(self.grounded_instance_ids),
            "public_connectors": [item.to_dict() for item in self.public_connectors],
            "interface_hashes": self.interface_hashes.to_dict(),
            "solved_snapshot": dict(solved_snapshot) if solved_snapshot is not None else None,
            "model_ref": self.model_ref.to_dict() if self.model_ref is not None else None,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self._manifest(content_hash_value=self.content_hash, solved_snapshot=self.solved_snapshot)

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(self.to_dict())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, blobs: Mapping[str, bytes] | None = None) -> "AssemblyDefinition":
        from .validation import validate_manifest

        validate_manifest(data, "assembly_definition")
        return cls(
            definition_id=str(data["definition_id"]),
            revision=str(data["revision"]),
            tolerance_profile=str(data["tolerance_profile"]),
            generator=dict(data["generator"]),
            definition_refs=tuple(PartRef.from_dict(item, f"/definition_refs/{index}") for index, item in enumerate(data["definition_refs"])),
            instances=tuple(PartInstance.from_dict(item, f"/instances/{index}") for index, item in enumerate(data["instances"])),
            relations=tuple(dict(item) for item in data["relations"]),
            grounded_instance_ids=tuple(str(item) for item in data["grounded_instance_ids"]),
            public_connectors=tuple(ConnectorInterface.from_dict(item, f"/public_connectors/{index}") for index, item in enumerate(data["public_connectors"])),
            interface_hashes=InterfaceHashes.from_dict(data["interface_hashes"]),
            solved_snapshot=dict(data["solved_snapshot"]) if data["solved_snapshot"] is not None else None,
            model_ref=BlobRef.from_dict(data["model_ref"], "/model_ref") if data["model_ref"] is not None else None,
            metadata=dict(data["metadata"]),
            content_hash=str(data["content_hash"]),
            blobs=blobs or {},
        )


__all__ = ["AssemblyDefinition"]
