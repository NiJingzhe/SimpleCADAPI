"""Canonical latest-assembly state for precise dirty propagation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from ..artifacts.assembly_definition import AssemblyDefinition
from ..artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    content_hash,
    parse_canonical_json,
    validate_hash,
    validate_json_value,
    validate_logical_id,
)
from ..artifacts.interface import _atomic_write, _state_lock
from ..artifacts.part_definition import PartDefinition
from ..artifacts.references import InterfaceHashes


Definition = PartDefinition | AssemblyDefinition


def effective_interface_hashes(definition: Definition) -> InterfaceHashes:
    """Expose nested material dependencies without assigning material to assemblies."""

    if isinstance(definition, PartDefinition):
        return definition.interface_hashes
    material_records = []
    has_material = False
    for instance in definition.instances:
        child = definition.resolved_definitions[instance.definition_id]
        child_material = effective_interface_hashes(child).material
        has_material = has_material or child_material is not None
        material_records.append(
            {
                "instance_id": instance.instance_id,
                "definition_id": instance.definition_id,
                "material": child_material,
            }
        )
    material_hash = (
        content_hash({"instances": material_records}) if has_material else None
    )
    return InterfaceHashes(
        geometry=definition.interface_hashes.geometry,
        connectors=definition.interface_hashes.connectors,
        bindings=definition.interface_hashes.bindings,
        material=material_hash,
    )


@dataclass(frozen=True, slots=True)
class AssemblyInterfaceSnapshot:
    """Authored structure and dependency interfaces from one assembly build."""

    definition_id: str
    definition_hash: str
    dependency_interfaces: Mapping[str, InterfaceHashes]
    public_interface: InterfaceHashes
    instances: Mapping[str, Mapping[str, Any]]
    relations: Mapping[str, Mapping[str, Any]]
    grounded_instance_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            validate_logical_id(self.definition_id, "/definition_id"),
        )
        object.__setattr__(
            self,
            "definition_hash",
            validate_hash(self.definition_hash, "/definition_hash"),
        )
        dependencies = dict(self.dependency_interfaces)
        for definition_id, interface_hashes in dependencies.items():
            validate_logical_id(
                definition_id,
                f"/dependency_interfaces/{definition_id}",
            )
            if not isinstance(interface_hashes, InterfaceHashes):
                raise ArtifactValidationError(
                    "interface_invalid",
                    f"/dependency_interfaces/{definition_id}",
                    "expected InterfaceHashes",
                )
        if not isinstance(self.public_interface, InterfaceHashes):
            raise ArtifactValidationError(
                "interface_invalid",
                "/public_interface",
                "expected InterfaceHashes",
            )
        instances = {str(key): dict(value) for key, value in self.instances.items()}
        relations = {str(key): dict(value) for key, value in self.relations.items()}
        validate_json_value(instances, "/instances")
        validate_json_value(relations, "/relations")
        grounded = tuple(self.grounded_instance_ids)
        if grounded != tuple(sorted(set(grounded), key=lambda item: item.encode("utf-8"))):
            raise ArtifactValidationError(
                "state_invalid",
                "/grounded_instance_ids",
                "IDs must be unique and sorted",
            )
        object.__setattr__(
            self,
            "dependency_interfaces",
            MappingProxyType(dependencies),
        )
        object.__setattr__(self, "instances", MappingProxyType(instances))
        object.__setattr__(self, "relations", MappingProxyType(relations))
        object.__setattr__(self, "grounded_instance_ids", grounded)

    @classmethod
    def from_definition(
        cls,
        definition: AssemblyDefinition,
    ) -> "AssemblyInterfaceSnapshot":
        if not isinstance(definition, AssemblyDefinition):
            raise TypeError("definition must be an AssemblyDefinition")
        return cls(
            definition_id=definition.definition_id,
            definition_hash=definition.content_hash,
            dependency_interfaces={
                definition_id: effective_interface_hashes(child)
                for definition_id, child in definition.resolved_definitions.items()
            },
            public_interface=definition.interface_hashes,
            instances={
                item.instance_id: {
                    "definition_id": item.definition_id,
                    "placement": dict(item.placement),
                }
                for item in definition.instances
            },
            relations={
                str(item["constraint_id"]): dict(item)
                for item in definition.relations
            },
            grounded_instance_ids=definition.grounded_instance_ids,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_hash": self.definition_hash,
            "dependency_interfaces": {
                definition_id: interface.to_dict()
                for definition_id, interface in sorted(
                    self.dependency_interfaces.items()
                )
            },
            "public_interface": self.public_interface.to_dict(),
            "instances": {
                instance_id: dict(item)
                for instance_id, item in sorted(self.instances.items())
            },
            "relations": {
                relation_id: dict(item)
                for relation_id, item in sorted(self.relations.items())
            },
            "grounded_instance_ids": list(self.grounded_instance_ids),
        }

    @classmethod
    def from_dict(
        cls,
        definition_id: str,
        value: Mapping[str, Any],
    ) -> "AssemblyInterfaceSnapshot":
        required = {
            "definition_hash",
            "dependency_interfaces",
            "public_interface",
            "instances",
            "relations",
            "grounded_instance_ids",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ArtifactValidationError(
                "state_invalid",
                f"/assemblies/{definition_id}",
                "state entry fields are not closed",
            )
        dependencies = value["dependency_interfaces"]
        if not isinstance(dependencies, Mapping):
            raise ArtifactValidationError(
                "state_invalid",
                f"/assemblies/{definition_id}/dependency_interfaces",
                "must be an object",
            )
        if not isinstance(value["instances"], Mapping) or not isinstance(
            value["relations"], Mapping
        ):
            raise ArtifactValidationError(
                "state_invalid",
                f"/assemblies/{definition_id}",
                "instances and relations must be objects",
            )
        if not isinstance(value["grounded_instance_ids"], list):
            raise ArtifactValidationError(
                "state_invalid",
                f"/assemblies/{definition_id}/grounded_instance_ids",
                "must be an array",
            )
        return cls(
            definition_id=definition_id,
            definition_hash=str(value["definition_hash"]),
            dependency_interfaces={
                str(child_id): InterfaceHashes.from_dict(
                    interface,
                    f"/assemblies/{definition_id}/dependency_interfaces/{child_id}",
                )
                for child_id, interface in dependencies.items()
            },
            public_interface=InterfaceHashes.from_dict(
                value["public_interface"],
                f"/assemblies/{definition_id}/public_interface",
            ),
            instances={
                str(instance_id): dict(item)
                for instance_id, item in value["instances"].items()
            },
            relations={
                str(relation_id): dict(item)
                for relation_id, item in value["relations"].items()
            },
            grounded_instance_ids=tuple(
                str(item) for item in value["grounded_instance_ids"]
            ),
        )


def load_latest_assembly_state(
    path: str | Path,
) -> dict[str, AssemblyInterfaceSnapshot]:
    """Load canonical latest-assembly state without creating it."""

    source = Path(path)
    try:
        payload = source.read_bytes()
    except FileNotFoundError:
        return {}
    try:
        value = parse_canonical_json(payload)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ArtifactValidationError("state_invalid", "/", str(exc)) from exc
    if canonical_bytes(value) != payload:
        raise ArtifactValidationError(
            "state_invalid",
            "/",
            "state bytes are not canonical",
        )
    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "assemblies",
    }:
        raise ArtifactValidationError(
            "state_invalid",
            "/",
            "state fields are not closed",
        )
    if value["schema_version"] != "1.0" or not isinstance(
        value["assemblies"], Mapping
    ):
        raise ArtifactValidationError(
            "state_invalid",
            "/",
            "unsupported state schema",
        )
    return {
        str(definition_id): AssemblyInterfaceSnapshot.from_dict(
            str(definition_id),
            entry,
        )
        for definition_id, entry in value["assemblies"].items()
    }


def update_latest_assembly_state(
    path: str | Path,
    *,
    snapshot: AssemblyInterfaceSnapshot,
) -> AssemblyInterfaceSnapshot | None:
    """Atomically replace one latest assembly entry and return its predecessor."""

    if not isinstance(snapshot, AssemblyInterfaceSnapshot):
        raise TypeError("snapshot must be an AssemblyInterfaceSnapshot")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _state_lock(destination):
        assemblies = load_latest_assembly_state(destination)
        previous = assemblies.get(snapshot.definition_id)
        if previous == snapshot:
            return previous
        assemblies[snapshot.definition_id] = snapshot
        payload = {
            "schema_version": "1.0",
            "assemblies": {
                definition_id: item.to_dict()
                for definition_id, item in sorted(assemblies.items())
            },
        }
        _atomic_write(destination, canonical_bytes(payload))
        return previous


__all__ = [
    "AssemblyInterfaceSnapshot",
    "effective_interface_hashes",
    "load_latest_assembly_state",
    "update_latest_assembly_state",
]
