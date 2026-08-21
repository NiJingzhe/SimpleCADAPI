"""Deterministic connector, relation, and constraint-component dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from ..artifacts.canonical import canonical_bytes, sha256_bytes

from ..assembly import Assembly


Endpoint = tuple[str, str]


def _utf8(value: str) -> bytes:
    return value.encode("utf-8")


@dataclass(frozen=True, slots=True)
class ConstraintComponent:
    """One relation-connected set of assembly instances."""

    component_id: str
    instance_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    connector_endpoints: tuple[Endpoint, ...]
    grounded_instance_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssemblyDependencyGraph:
    """Stable dependency indexes for one runtime assembly."""

    assembly_id: str
    components: tuple[ConstraintComponent, ...]
    relation_to_component: Mapping[str, str]
    endpoint_to_relations: Mapping[Endpoint, tuple[str, ...]]
    instance_to_component: Mapping[str, str]
    public_connector_sources: Mapping[str, Endpoint]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relation_to_component",
            MappingProxyType(dict(self.relation_to_component)),
        )
        object.__setattr__(
            self,
            "endpoint_to_relations",
            MappingProxyType(dict(self.endpoint_to_relations)),
        )
        object.__setattr__(
            self,
            "instance_to_component",
            MappingProxyType(dict(self.instance_to_component)),
        )
        object.__setattr__(
            self,
            "public_connector_sources",
            MappingProxyType(dict(self.public_connector_sources)),
        )

    def component(self, component_id: str) -> ConstraintComponent:
        for component in self.components:
            if component.component_id == component_id:
                return component
        raise KeyError(f"dependency graph has no component {component_id!r}")


def build_assembly_dependency_graph(assembly: Assembly) -> AssemblyDependencyGraph:
    """Build relation-connected components, including coupling relations."""

    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")

    instance_ids = tuple(sorted(assembly.component_ids(), key=_utf8))
    adjacency = {instance_id: set() for instance_id in instance_ids}
    relation_instances: dict[str, tuple[str, str]] = {}
    endpoint_relations: dict[Endpoint, list[str]] = {}

    for relation in assembly.constraints:
        first = relation.connector_a.component_id
        second = relation.connector_b.component_id
        adjacency[first].add(second)
        adjacency[second].add(first)
        relation_instances[relation.constraint_id] = (first, second)
        for endpoint in (
            (first, relation.connector_a.connector_id),
            (second, relation.connector_b.connector_id),
        ):
            endpoint_relations.setdefault(endpoint, []).append(
                relation.constraint_id
            )

    groups: list[tuple[str, ...]] = []
    unvisited = set(instance_ids)
    while unvisited:
        first = min(unvisited, key=_utf8)
        pending = [first]
        found: set[str] = set()
        while pending:
            instance_id = pending.pop()
            if instance_id in found:
                continue
            found.add(instance_id)
            pending.extend(
                sorted(adjacency[instance_id] - found, key=_utf8, reverse=True)
            )
        unvisited.difference_update(found)
        groups.append(tuple(sorted(found, key=_utf8)))

    groups.sort(key=lambda item: tuple(_utf8(value) for value in item))
    components: list[ConstraintComponent] = []
    relation_to_component: dict[str, str] = {}
    instance_to_component: dict[str, str] = {}
    grounded = set(assembly.grounded_component_ids)
    for group in groups:
        digest = sha256_bytes(canonical_bytes({"instance_ids": list(group)}))
        component_id = "component_" + digest.removeprefix("sha256:")[:16]
        relation_ids = tuple(
            sorted(
                (
                    relation_id
                    for relation_id, endpoints in relation_instances.items()
                    if endpoints[0] in group
                ),
                key=_utf8,
            )
        )
        relation_id_set = set(relation_ids)
        endpoint_set = {
            endpoint
            for endpoint, relation_ids_for_endpoint in endpoint_relations.items()
            if any(
                relation_id in relation_id_set
                for relation_id in relation_ids_for_endpoint
            )
        }
        component = ConstraintComponent(
            component_id=component_id,
            instance_ids=group,
            relation_ids=relation_ids,
            connector_endpoints=tuple(
                sorted(endpoint_set, key=lambda item: (_utf8(item[0]), _utf8(item[1])))
            ),
            grounded_instance_ids=tuple(
                instance_id for instance_id in group if instance_id in grounded
            ),
        )
        components.append(component)
        for instance_id in group:
            instance_to_component[instance_id] = component_id
        for relation_id in relation_ids:
            relation_to_component[relation_id] = component_id

    public_sources: dict[str, Endpoint] = {
        public.public_connector_id: (
            public.component_id,
            public.connector_id,
        )
        for public in assembly.public_connectors
    }

    return AssemblyDependencyGraph(
        assembly_id=assembly.assembly_id,
        components=tuple(components),
        relation_to_component=relation_to_component,
        endpoint_to_relations={
            endpoint: tuple(sorted(relation_ids, key=_utf8))
            for endpoint, relation_ids in endpoint_relations.items()
        },
        instance_to_component=instance_to_component,
        public_connector_sources=public_sources,
    )


__all__ = [
    "AssemblyDependencyGraph",
    "ConstraintComponent",
    "Endpoint",
    "build_assembly_dependency_graph",
]
