"""Canonical occurrence graph derived from durable Part/Assembly definitions."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .artifacts.assembly_definition import AssemblyDefinition
from .artifacts.canonical import canonical_bytes, content_hash, parse_canonical_json
from .artifacts.part_definition import PartDefinition
from .placement import identity_placement

Definition = PartDefinition | AssemblyDefinition


class ProductOccurrenceError(ValueError):
    """Raised when an occurrence graph is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ProductOccurrenceGraph:
    """Definition-derived product occurrences, connectors, joints, and grounding."""

    manifest: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))
        _validate_manifest(self.manifest)

    @property
    def root_definition_id(self) -> str:
        return str(self.manifest["root_definition_id"])

    @property
    def root_node_id(self) -> str:
        return str(self.manifest["root_node_id"])

    @property
    def nodes(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.manifest["nodes"])

    @property
    def connectors(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.manifest["connectors"])

    @property
    def joints(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.manifest["joints"])

    @property
    def ground_edges(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.manifest["ground_edges"])

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_bytes(dict(self.manifest))

    @classmethod
    def from_bytes(cls, payload: bytes | bytearray | memoryview) -> "ProductOccurrenceGraph":
        value = parse_canonical_json(bytes(payload))
        if not isinstance(value, Mapping):
            raise ProductOccurrenceError("occurrence graph must be an object")
        return cls(value)


def _node_id(path: tuple[str, ...]) -> str:
    return "node/" + "/".join(path)


def _connector_snapshot_id(node_id: str, connector_id: str) -> str:
    return f"connector/{node_id.removeprefix('node/')}/{connector_id}"


def _definition_closure(root: Definition) -> dict[str, Definition]:
    definitions: dict[str, Definition] = {}

    def visit(definition: Definition) -> None:
        existing = definitions.get(definition.definition_id)
        if existing is not None:
            if (
                existing.definition_kind != definition.definition_kind
                or existing.content_hash != definition.content_hash
            ):
                raise ProductOccurrenceError(
                    f"definition_id {definition.definition_id!r} has multiple identities"
                )
            return
        definitions[definition.definition_id] = definition
        if isinstance(definition, AssemblyDefinition):
            for ref in definition.definition_refs:
                child = definition.resolved_definitions.get(ref.definition_id)
                if not isinstance(child, (PartDefinition, AssemblyDefinition)):
                    raise ProductOccurrenceError(
                        f"assembly {definition.definition_id!r} has unresolved "
                        f"definition {ref.definition_id!r}"
                    )
                visit(child)

    visit(root)
    return definitions


def compile_product_occurrence_graph(root: Definition) -> ProductOccurrenceGraph:
    """Derive a deterministic occurrence graph without compiling geometry or Scene assets."""

    if not isinstance(root, (PartDefinition, AssemblyDefinition)):
        raise TypeError("root must be a PartDefinition or AssemblyDefinition")
    definitions = _definition_closure(root)
    nodes: list[dict[str, Any]] = []
    occurrences: dict[str, list[str]] = {}
    children: dict[tuple[str, str], str] = {}

    def visit(
        definition: Definition,
        path: tuple[str, ...],
        parent_node_id: str | None,
        transform: Mapping[str, Any],
        component_id: str | None,
        instance_id: str | None,
        display_name: str | None,
    ) -> str:
        node_id = _node_id(path)
        occurrences.setdefault(definition.definition_id, []).append(node_id)
        is_part = isinstance(definition, PartDefinition)
        nodes.append(
            {
                "node_id": node_id,
                "parent_node_id": parent_node_id,
                "display_name": display_name or definition.definition_id,
                "node_kind": "part" if is_part else "assembly",
                "definition_id": definition.definition_id,
                "definition_kind": definition.definition_kind,
                "component_id": component_id,
                "instance_id": instance_id,
                "transform": dict(transform),
                "material_id": (
                    definition.material_ref.material_id
                    if is_part and definition.material_ref is not None
                    else None
                ),
                "properties": {
                    "content_hash": definition.content_hash,
                    "revision": definition.revision,
                },
            }
        )
        if isinstance(definition, AssemblyDefinition):
            for instance in definition.instances:
                child = definitions[instance.definition_id]
                child_path = (*path, instance.instance_id)
                child_node = visit(
                    child,
                    child_path,
                    node_id,
                    instance.placement,
                    instance.instance_id,
                    _node_id(child_path),
                    instance.name,
                )
                children[(node_id, instance.instance_id)] = child_node
        return node_id

    root_node_id = visit(
        root,
        (root.definition_id,),
        None,
        identity_placement().to_dict(),
        None,
        None,
        root.metadata.get("name"),
    )
    for values in occurrences.values():
        values.sort()

    connectors: list[dict[str, Any]] = []
    for definition_id in sorted(definitions):
        definition = definitions[definition_id]
        interfaces = (
            definition.connectors
            if isinstance(definition, PartDefinition)
            else definition.public_connectors
        )
        for node_id in occurrences.get(definition_id, []):
            for interface in interfaces:
                is_public = isinstance(definition, AssemblyDefinition)
                source_snapshot_id = None
                if is_public:
                    source_node_id = f"{node_id}/{interface.source_component_id}"
                    source_snapshot_id = _connector_snapshot_id(
                        source_node_id, interface.source_connector_id
                    )
                connectors.append(
                    {
                        "connector_snapshot_id": _connector_snapshot_id(
                            node_id, interface.connector_id
                        ),
                        "node_id": node_id,
                        "definition_id": definition_id,
                        "definition_kind": definition.definition_kind,
                        "component_id": (
                            None
                            if node_id == root_node_id
                            else node_id.rsplit("/", 1)[-1]
                        ),
                        "connector_id": interface.connector_id,
                        "name": interface.name or interface.connector_id,
                        "anchor_kind": "public" if is_public else interface.anchor_kind,
                        "local_frame": dict(interface.local_frame),
                        "binding": (
                            dict(interface.binding)
                            if interface.binding is not None
                            else None
                        ),
                        "source_connector_snapshot_id": source_snapshot_id,
                    }
                )
    connectors.sort(key=lambda item: item["connector_snapshot_id"])
    connector_ids = {
        str(item["connector_snapshot_id"]): item for item in connectors
    }

    joints: list[dict[str, Any]] = []
    ground_edges: list[dict[str, Any]] = []
    for definition_id in sorted(definitions):
        definition = definitions[definition_id]
        if not isinstance(definition, AssemblyDefinition):
            continue
        for assembly_node in occurrences[definition_id]:
            for grounded_id in definition.grounded_instance_ids:
                child_node = children[(assembly_node, grounded_id)]
                ground_edges.append(
                    {
                        "parent_node_id": assembly_node,
                        "child_node_id": child_node,
                        "instance_id": grounded_id,
                    }
                )
            for relation in definition.relations:
                constraint_id = str(relation["constraint_id"])

                def endpoint(side: str) -> dict[str, Any]:
                    ref = relation[side]
                    component_id = str(ref["component_id"])
                    child_node = children[(assembly_node, component_id)]
                    connector_id = str(ref["connector_id"])
                    snapshot_id = _connector_snapshot_id(child_node, connector_id)
                    if snapshot_id not in connector_ids:
                        raise ProductOccurrenceError(
                            f"joint {constraint_id!r} references missing connector "
                            f"{component_id!r}/{connector_id!r}"
                        )
                    return {
                        "definition_id": str(
                            next(
                                item["definition_id"]
                                for item in nodes
                                if item["node_id"] == child_node
                            )
                        ),
                        "component_id": component_id,
                        "instance_id": child_node,
                        "connector_id": connector_id,
                        "connector_snapshot_id": snapshot_id,
                    }

                parameters = {
                    key: relation.get(key)
                    for key in (
                        "drive_distance",
                        "drive_angle_degrees",
                        "pitch_radius_a",
                        "pitch_radius_b",
                        "pulley_radius_a",
                        "pulley_radius_b",
                        "pitch_radius",
                        "phase_offset",
                    )
                    if relation.get(key) is not None
                }
                limits = {
                    key: relation.get(key)
                    for key in ("distance_limit", "angle_limit")
                    if relation.get(key) is not None
                }
                occurrence_path = assembly_node.removeprefix("node/")
                joints.append(
                    {
                        "joint_id": f"joint/{occurrence_path}/{constraint_id}",
                        "assembly_definition_id": definition_id,
                        "joint_type": str(relation["constraint_kind"]),
                        "connector_a": endpoint("connector_a"),
                        "connector_b": endpoint("connector_b"),
                        "parameters": parameters,
                        "limits": limits or None,
                    }
                )
    joints.sort(key=lambda item: item["joint_id"])
    ground_edges.sort(key=lambda item: (item["parent_node_id"], item["child_node_id"]))
    manifest = {
        "schema_version": "1.0",
        "artifact_kind": "product_occurrence_graph",
        "root_definition_id": root.definition_id,
        "root_node_id": root_node_id,
        "definitions": [
            {
                "definition_id": item.definition_id,
                "definition_kind": item.definition_kind,
                "revision": item.revision,
                "content_hash": item.content_hash,
            }
            for item in sorted(definitions.values(), key=lambda value: value.definition_id)
        ],
        "nodes": sorted(nodes, key=lambda item: item["node_id"]),
        "connectors": connectors,
        "joints": joints,
        "ground_edges": ground_edges,
    }
    manifest["content_hash"] = content_hash(manifest, omit=())
    return ProductOccurrenceGraph(manifest)


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "artifact_kind",
        "root_definition_id",
        "root_node_id",
        "definitions",
        "nodes",
        "connectors",
        "joints",
        "ground_edges",
        "content_hash",
    }
    if set(manifest) != required:
        raise ProductOccurrenceError("occurrence graph fields are not closed")
    if manifest["schema_version"] != "1.0" or manifest["artifact_kind"] != "product_occurrence_graph":
        raise ProductOccurrenceError("unsupported occurrence graph schema")
    expected_hash = content_hash(
        {key: value for key, value in manifest.items() if key != "content_hash"},
        omit=(),
    )
    if manifest["content_hash"] != expected_hash:
        raise ProductOccurrenceError("occurrence graph content_hash is invalid")

    definitions = list(manifest["definitions"])
    definition_by_id = {str(item["definition_id"]): item for item in definitions}
    if len(definition_by_id) != len(definitions):
        raise ProductOccurrenceError("occurrence definition IDs are not unique")
    root_definition_id = str(manifest["root_definition_id"])
    if root_definition_id not in definition_by_id:
        raise ProductOccurrenceError("occurrence root definition does not resolve")

    nodes = list(manifest["nodes"])
    node_by_id = {str(item["node_id"]): item for item in nodes}
    if len(node_by_id) != len(nodes):
        raise ProductOccurrenceError("occurrence node IDs are not unique")
    root_node_id = str(manifest["root_node_id"])
    root_node = node_by_id.get(root_node_id)
    if root_node is None or root_node["parent_node_id"] is not None:
        raise ProductOccurrenceError("occurrence root node is invalid")
    if str(root_node["definition_id"]) != root_definition_id:
        raise ProductOccurrenceError("occurrence root node definition differs")
    for node in nodes:
        node_id = str(node["node_id"])
        definition_id = str(node["definition_id"])
        definition = definition_by_id.get(definition_id)
        if definition is None:
            raise ProductOccurrenceError(f"node {node_id!r} definition does not resolve")
        if node["definition_kind"] != definition["definition_kind"]:
            raise ProductOccurrenceError(f"node {node_id!r} definition kind differs")
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            raise ProductOccurrenceError(f"node {node_id!r} properties are invalid")
        if properties.get("content_hash") != definition["content_hash"] or properties.get("revision") != definition["revision"]:
            raise ProductOccurrenceError(f"node {node_id!r} definition identity differs")
        parent = node["parent_node_id"]
        if parent is not None and str(parent) not in node_by_id:
            raise ProductOccurrenceError(f"node {node_id!r} parent does not resolve")

    for node_id in node_by_id:
        seen: set[str] = set()
        current = node_id
        while True:
            if current in seen:
                raise ProductOccurrenceError("occurrence node hierarchy contains a cycle")
            seen.add(current)
            parent = node_by_id[current]["parent_node_id"]
            if parent is None:
                break
            current = str(parent)

    connector_records = list(manifest["connectors"])
    connector_by_id = {
        str(item["connector_snapshot_id"]): item for item in connector_records
    }
    if len(connector_by_id) != len(connector_records):
        raise ProductOccurrenceError("connector snapshot IDs are not unique")
    for connector in connector_records:
        node_id = str(connector["node_id"])
        node = node_by_id.get(node_id)
        if node is None:
            raise ProductOccurrenceError("connector node does not resolve")
        if connector["definition_id"] != node["definition_id"] or connector["definition_kind"] != node["definition_kind"]:
            raise ProductOccurrenceError("connector definition identity differs")
        source_id = connector["source_connector_snapshot_id"]
        if source_id is not None and str(source_id) not in connector_by_id:
            raise ProductOccurrenceError("connector source does not resolve")
    for connector_id in connector_by_id:
        seen: set[str] = set()
        current = connector_id
        while True:
            if current in seen:
                raise ProductOccurrenceError("connector forwarding graph contains a cycle")
            seen.add(current)
            source = connector_by_id[current]["source_connector_snapshot_id"]
            if source is None:
                break
            current = str(source)

    joints = list(manifest["joints"])
    joint_ids = [str(item["joint_id"]) for item in joints]
    if len(joint_ids) != len(set(joint_ids)):
        raise ProductOccurrenceError("joint IDs are not unique")
    connector_ids = set(connector_by_id)
    for joint in joints:
        assembly_id = str(joint["assembly_definition_id"])
        if assembly_id not in definition_by_id or definition_by_id[assembly_id]["definition_kind"] != "assembly":
            raise ProductOccurrenceError("joint assembly definition does not resolve")
        for side in ("connector_a", "connector_b"):
            endpoint = joint[side]
            if str(endpoint["connector_snapshot_id"]) not in connector_ids:
                raise ProductOccurrenceError("joint connector does not resolve")
            endpoint_node = node_by_id.get(str(endpoint["instance_id"]))
            if endpoint_node is None or endpoint["definition_id"] != endpoint_node["definition_id"]:
                raise ProductOccurrenceError("joint endpoint identity does not resolve")

    ground_edges = list(manifest["ground_edges"])
    edge_ids = {(str(item["parent_node_id"]), str(item["child_node_id"])) for item in ground_edges}
    if len(edge_ids) != len(ground_edges):
        raise ProductOccurrenceError("ground edges are not unique")
    for edge in ground_edges:
        parent_id = str(edge["parent_node_id"])
        child_id = str(edge["child_node_id"])
        if parent_id not in node_by_id or child_id not in node_by_id:
            raise ProductOccurrenceError("ground edge does not resolve")
        if node_by_id[child_id]["parent_node_id"] != parent_id:
            raise ProductOccurrenceError("ground edge child is not a direct occurrence")


def encode_product_occurrence_graph(graph: ProductOccurrenceGraph) -> bytes:
    if not isinstance(graph, ProductOccurrenceGraph):
        raise TypeError("graph must be a ProductOccurrenceGraph")
    return graph.canonical_bytes


def read_product_occurrence_graph(
    data: bytes | bytearray | memoryview | str,
) -> ProductOccurrenceGraph:
    if isinstance(data, str):
        from pathlib import Path

        payload = Path(data).read_bytes()
    else:
        payload = bytes(data)
    return ProductOccurrenceGraph.from_bytes(payload)


__all__ = [
    "ProductOccurrenceError",
    "ProductOccurrenceGraph",
    "compile_product_occurrence_graph",
    "encode_product_occurrence_graph",
    "read_product_occurrence_graph",
]
