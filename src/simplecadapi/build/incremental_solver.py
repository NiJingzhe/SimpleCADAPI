"""Constraint-component solve keys, dirty propagation, and verified cache reuse."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from ..artifacts.assembly_definition import AssemblyDefinition
from ..artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    content_hash,
    parse_canonical_json,
)
from ..artifacts.part_definition import PartDefinition
from ..cache.policy import CacheMode, CachePolicy
from ..cache.store import ContentAddressedStore
from ..assembly import (
    Assembly,
    _component_occurrence_placements,
    _restore_component_occurrence_placements,
    _with_component_path_placement,
)
from ..assembly_solver import (
    constraint_reports_match,
    inspect_assembly_constraints,
    solve_assembly_constraints,
)
from ..constraint import ConstraintReport
from ..placement import Placement
from .assembly_state import AssemblyInterfaceSnapshot, effective_interface_hashes
from .dependency_graph import (
    AssemblyDependencyGraph,
    ConstraintComponent,
    build_assembly_dependency_graph,
)


Definition = PartDefinition | AssemblyDefinition
_ASSEMBLY_NAMESPACE = "assembly"
_SOLVE_CACHE_PROFILE = "simplecad-assembly-component-cache-1"
_SOLVER_PROFILE = "simplecad-assembly-solver-1"
_AUTHORED_PLACEMENTS_RUNTIME_KEY = "assembly.authored_component_placements"
_CACHE_MEDIA_TYPE = "application/vnd.simplecad.assembly-component+json"


def _utf8(value: str) -> bytes:
    return value.encode("utf-8")


@dataclass(frozen=True, slots=True)
class ComponentSolveResult:
    """Cache and residual outcome for one connected constraint component."""

    component_id: str
    solve_key: str
    instance_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    cache_hit: bool
    solved: bool
    miss_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AssemblySolveReport:
    """Structured incremental solve and dirty-propagation evidence."""

    mode: str
    component_lookups: int
    component_hits: int
    component_misses: int
    corrupt_entries: int
    dirty_instances: tuple[str, ...] = ()
    geometry_dirty_instances: tuple[str, ...] = ()
    material_dirty_instances: tuple[str, ...] = ()
    binding_dirty_endpoints: tuple[str, ...] = ()
    dirty_connectors: tuple[str, ...] = ()
    dirty_relations: tuple[str, ...] = ()
    dirty_components: tuple[str, ...] = ()
    public_connector_changed: tuple[str, ...] = ()
    propagated_paths: tuple[str, ...] = ()
    component_results: tuple[ComponentSolveResult, ...] = ()

    @property
    def hit(self) -> bool:
        return (
            self.component_lookups > 0 and self.component_hits == self.component_lookups
        )


@dataclass(frozen=True, slots=True)
class DirtyPropagation:
    instance_ids: tuple[str, ...] = ()
    geometry_instance_ids: tuple[str, ...] = ()
    material_instance_ids: tuple[str, ...] = ()
    binding_endpoints: tuple[str, ...] = ()
    connector_endpoints: tuple[str, ...] = ()
    relation_ids: tuple[str, ...] = ()
    component_ids: tuple[str, ...] = ()
    reasons: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", MappingProxyType(dict(self.reasons)))


def _instance_definition_ids(
    assembly: Assembly,
) -> dict[str, str]:
    return {
        component.component_id: (
            component.item.part_id
            if hasattr(component.item, "part_id")
            else component.item.assembly_id
        )
        for component in assembly.components
    }


def _interface_changes(before: Any, after: Any) -> dict[str, tuple[str, ...] | bool]:
    before_connectors = dict(before.connectors)
    after_connectors = dict(after.connectors)
    before_bindings = dict(before.bindings)
    after_bindings = dict(after.bindings)
    common = set(before_connectors) & set(after_connectors)
    return {
        "geometry": before.geometry != after.geometry,
        "material": before.material != after.material,
        "connectors": tuple(
            sorted(
                {
                    connector_id
                    for connector_id in common
                    if before_connectors[connector_id] != after_connectors[connector_id]
                }
                | (set(before_connectors) ^ set(after_connectors)),
                key=_utf8,
            )
        ),
        "bindings": tuple(
            sorted(
                connector_id
                for connector_id in common
                if before_bindings.get(connector_id) != after_bindings.get(connector_id)
            )
        ),
    }


def propagate_assembly_dirty_state(
    assembly: Assembly,
    definitions: Mapping[str, Definition],
    graph: AssemblyDependencyGraph,
    previous: AssemblyInterfaceSnapshot | None,
) -> DirtyPropagation:
    """Classify direct interface and authored-structure changes."""

    if previous is None:
        constrained = tuple(
            component.component_id
            for component in graph.components
            if component.relation_ids
        )
        return DirtyPropagation(
            instance_ids=tuple(sorted(assembly.component_ids(), key=_utf8)),
            relation_ids=tuple(sorted(assembly.constraint_ids(), key=_utf8)),
            component_ids=tuple(sorted(constrained, key=_utf8)),
            reasons={"cold_start": tuple(sorted(constrained, key=_utf8))},
        )

    definition_by_instance = _instance_definition_ids(assembly)
    current_instances = {
        component.component_id: {
            "definition_id": definition_by_instance[component.component_id],
            "placement": component.placement.to_dict(),
        }
        for component in assembly.components
    }
    current_relations = {
        relation.constraint_id: relation.to_dict() for relation in assembly.constraints
    }
    dirty_instances: set[str] = set()
    geometry_instances: set[str] = set()
    material_instances: set[str] = set()
    binding_endpoints: set[str] = set()
    connector_endpoints: set[str] = set()
    dirty_relations: set[str] = set()
    reasons: dict[str, set[str]] = {}

    all_instance_ids = set(previous.instances) | set(current_instances)
    for instance_id in all_instance_ids:
        before_instance = previous.instances.get(instance_id)
        after_instance = current_instances.get(instance_id)
        if before_instance != after_instance:
            dirty_instances.add(instance_id)
            reasons.setdefault("instance_changed", set()).add(instance_id)
            component_id = graph.instance_to_component.get(instance_id)
            if component_id is not None:
                dirty_relations.update(graph.component(component_id).relation_ids)

    for definition_id in set(previous.dependency_interfaces) | set(definitions):
        before_interface = previous.dependency_interfaces.get(definition_id)
        child = definitions.get(definition_id)
        after_interface = (
            effective_interface_hashes(child) if child is not None else None
        )
        affected_instances = {
            instance_id
            for instance_id, current in current_instances.items()
            if current["definition_id"] == definition_id
        }
        if before_interface is None or after_interface is None:
            dirty_instances.update(affected_instances)
            geometry_instances.update(affected_instances)
            material_instances.update(affected_instances)
            reasons.setdefault("definition_changed", set()).update(affected_instances)
            for instance_id in affected_instances:
                component_id = graph.instance_to_component[instance_id]
                dirty_relations.update(graph.component(component_id).relation_ids)
            continue
        changes = _interface_changes(before_interface, after_interface)
        if changes["geometry"]:
            geometry_instances.update(affected_instances)
            reasons.setdefault("geometry_changed", set()).update(affected_instances)
        if changes["material"]:
            material_instances.update(affected_instances)
            reasons.setdefault("material_changed", set()).update(affected_instances)
        for instance_id in affected_instances:
            for connector_id in changes["bindings"]:
                endpoint = f"{instance_id}.{connector_id}"
                binding_endpoints.add(endpoint)
            for connector_id in changes["connectors"]:
                endpoint = f"{instance_id}.{connector_id}"
                connector_endpoints.add(endpoint)
                dirty_relations.update(
                    graph.endpoint_to_relations.get(
                        (instance_id, connector_id),
                        (),
                    )
                )

    for relation_id in set(previous.relations) | set(current_relations):
        if previous.relations.get(relation_id) != current_relations.get(relation_id):
            dirty_relations.add(relation_id)
            reasons.setdefault("relation_changed", set()).add(relation_id)

    if previous.grounded_instance_ids != tuple(
        sorted(assembly.grounded_component_ids, key=_utf8)
    ):
        changed_grounding = set(previous.grounded_instance_ids) ^ set(
            assembly.grounded_component_ids
        )
        for instance_id in changed_grounding:
            component_id = graph.instance_to_component.get(instance_id)
            if component_id is not None:
                dirty_relations.update(graph.component(component_id).relation_ids)
        reasons.setdefault("grounding_changed", set()).update(changed_grounding)

    dirty_components = {
        graph.relation_to_component[relation_id]
        for relation_id in dirty_relations
        if relation_id in graph.relation_to_component
    }
    return DirtyPropagation(
        instance_ids=tuple(sorted(dirty_instances, key=_utf8)),
        geometry_instance_ids=tuple(sorted(geometry_instances, key=_utf8)),
        material_instance_ids=tuple(sorted(material_instances, key=_utf8)),
        binding_endpoints=tuple(sorted(binding_endpoints, key=_utf8)),
        connector_endpoints=tuple(sorted(connector_endpoints, key=_utf8)),
        relation_ids=tuple(sorted(dirty_relations, key=_utf8)),
        component_ids=tuple(sorted(dirty_components, key=_utf8)),
        reasons={
            reason: tuple(sorted(values, key=_utf8))
            for reason, values in sorted(reasons.items())
        },
    )


def _component_assembly(
    assembly: Assembly,
    component: ConstraintComponent,
) -> Assembly:
    instance_set = set(component.instance_ids)
    relation_set = set(component.relation_ids)
    return Assembly(
        assembly_id=assembly.assembly_id,
        name=assembly.name,
        components=tuple(
            item for item in assembly.components if item.component_id in instance_set
        ),
        constraints=tuple(
            item for item in assembly.constraints if item.constraint_id in relation_set
        ),
        grounded_component_ids=component.grounded_instance_ids,
    )


def _authored_assembly(
    assembly: Assembly,
) -> tuple[Assembly, dict[str, dict[str, Any]]]:
    current = {
        component.component_id: component.placement.to_dict()
        for component in assembly.components
    }
    raw = assembly._get_runtime(_AUTHORED_PLACEMENTS_RUNTIME_KEY)
    if raw is None:
        return assembly, current
    if not isinstance(raw, Mapping) or set(raw) != set(current):
        raise ArtifactValidationError(
            "assembly_provenance_invalid",
            "/instances",
            "authored component placements do not match assembly instances",
        )
    authored = {
        str(component_id): Placement(**dict(placement)).to_dict()
        for component_id, placement in raw.items()
    }
    restored = assembly
    for component_id, placement in authored.items():
        restored = restored.with_component_placement(
            component_id,
            Placement(**placement),
        )
    restored._set_runtime(_AUTHORED_PLACEMENTS_RUNTIME_KEY, authored)
    return restored, authored


def assembly_component_solve_key(
    assembly: Assembly,
    component: ConstraintComponent,
    definitions: Mapping[str, Definition],
    *,
    tolerance_profile: str,
) -> str:
    """Hash every input that can affect one component's solved placements."""

    by_id = _instance_definition_ids(assembly)
    relation_by_id = {
        relation.constraint_id: relation for relation in assembly.constraints
    }
    instance_by_id = {item.component_id: item for item in assembly.components}
    connector_records = []
    for instance_id, connector_id in component.connector_endpoints:
        definition = definitions[by_id[instance_id]]
        interface = effective_interface_hashes(definition)
        connector_hash = interface.connectors.get(connector_id)
        if connector_hash is None:
            raise ArtifactValidationError(
                "reference_missing",
                f"/instances/{instance_id}/connectors/{connector_id}",
                "constraint connector is absent from the referenced definition",
            )
        connector_records.append(
            {
                "instance_id": instance_id,
                "connector_id": connector_id,
                "interface_hash": connector_hash,
            }
        )
    payload = {
        "profile": _SOLVE_CACHE_PROFILE,
        "solver_profile": _SOLVER_PROFILE,
        "units": "mm",
        "tolerance_profile": tolerance_profile,
        "placement_tolerance": 1.0e-7,
        "angle_tolerance_degrees": 1.0e-6,
        "instances": [
            {
                "instance_id": instance_id,
                "definition_id": by_id[instance_id],
                "authored_placement": instance_by_id[instance_id].placement.to_dict(),
            }
            for instance_id in component.instance_ids
        ],
        "connectors": connector_records,
        "relations": [
            relation_by_id[relation_id].to_dict()
            for relation_id in component.relation_ids
        ],
        "grounded_instance_ids": list(component.grounded_instance_ids),
    }
    return content_hash(payload)


def _encode_component_result(
    component: ConstraintComponent,
    solve_key: str,
    solved: Assembly,
) -> bytes:
    report = inspect_assembly_constraints(solved)
    payload = {
        "schema_version": "1.0",
        "profile": _SOLVE_CACHE_PROFILE,
        "solver_profile": _SOLVER_PROFILE,
        "solve_key": solve_key,
        "component_id": component.component_id,
        "instance_ids": list(component.instance_ids),
        "relation_ids": list(component.relation_ids),
        "placements": [
            {
                "instance_id": instance_id,
                "placement": solved.get_component(instance_id).placement.to_dict(),
            }
            for instance_id in component.instance_ids
        ],
        "occurrence_placements": list(_component_occurrence_placements(solved)),
        "constraint_report": report.to_dict(),
    }
    return canonical_bytes(payload)


def _apply_component_payload(
    authored: Assembly,
    component: ConstraintComponent,
    solve_key: str,
    payload: bytes,
) -> Assembly:
    try:
        value = parse_canonical_json(payload)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/",
            str(exc),
        ) from exc
    legacy_required = {
        "schema_version",
        "profile",
        "solver_profile",
        "solve_key",
        "component_id",
        "instance_ids",
        "relation_ids",
        "placements",
        "constraint_report",
    }
    required = legacy_required | {"occurrence_placements"}
    if not isinstance(value, Mapping) or set(value) not in (
        legacy_required,
        required,
    ):
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/",
            "component cache fields are not closed",
        )
    if canonical_bytes(value) != payload:
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/",
            "component cache payload is not canonical",
        )
    expected_header = {
        "schema_version": "1.0",
        "profile": _SOLVE_CACHE_PROFILE,
        "solver_profile": _SOLVER_PROFILE,
        "solve_key": solve_key,
        "component_id": component.component_id,
        "instance_ids": list(component.instance_ids),
        "relation_ids": list(component.relation_ids),
    }
    for key, expected in expected_header.items():
        if value[key] != expected:
            raise ArtifactValidationError(
                "assembly_cache_invalid",
                f"/{key}",
                "cached component identity differs",
            )
    placements = value["placements"]
    if not isinstance(placements, list):
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/placements",
            "placements must be an array",
        )
    by_id: dict[str, Mapping[str, Any]] = {}
    for index, item in enumerate(placements):
        if not isinstance(item, Mapping) or set(item) != {
            "instance_id",
            "placement",
        }:
            raise ArtifactValidationError(
                "assembly_cache_invalid",
                f"/placements/{index}",
                "placement fields are not closed",
            )
        instance_id = str(item["instance_id"])
        if instance_id in by_id or not isinstance(item["placement"], Mapping):
            raise ArtifactValidationError(
                "assembly_cache_invalid",
                f"/placements/{index}",
                "duplicate instance or invalid placement",
            )
        by_id[instance_id] = item["placement"]
    if set(by_id) != set(component.instance_ids):
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/placements",
            "cached placement instances differ",
        )
    try:
        occurrence_placements = value.get("occurrence_placements")
        if occurrence_placements is not None:
            if not isinstance(occurrence_placements, list):
                raise ValueError("occurrence placements must be an array")
            candidate = _restore_component_occurrence_placements(
                authored,
                occurrence_placements,
            )
        else:
            candidate = authored
            for instance_id in component.instance_ids:
                candidate = candidate.with_component_placement(
                    instance_id,
                    Placement(**dict(by_id[instance_id])),
                )
        if any(
            candidate.get_component(instance_id).placement.to_dict()
            != dict(by_id[instance_id])
            for instance_id in component.instance_ids
        ):
            raise ValueError("top-level and occurrence placements differ")
        report = inspect_assembly_constraints(candidate)
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/placements",
            str(exc),
        ) from exc
    if not report.solved or not constraint_reports_match(
        report.to_dict(), value["constraint_report"]
    ):
        raise ArtifactValidationError(
            "assembly_cache_invalid",
            "/constraint_report",
            "cached placements failed residual verification",
        )
    return candidate


def solve_assembly_incrementally(
    assembly: Assembly,
    definitions: Mapping[str, Definition],
    *,
    tolerance_profile: str,
    policy: CachePolicy,
    previous: AssemblyInterfaceSnapshot | None = None,
) -> tuple[Assembly, AssemblySolveReport]:
    """Solve each independent relation component with verified CAS reuse."""

    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    if not isinstance(policy, CachePolicy):
        raise TypeError("policy must be a CachePolicy")
    assembly, authored_placements = _authored_assembly(assembly)
    graph = build_assembly_dependency_graph(assembly)
    dirty = propagate_assembly_dirty_state(
        assembly,
        definitions,
        graph,
        previous,
    )
    store = ContentAddressedStore(policy)
    result = assembly
    component_results: list[ComponentSolveResult] = []
    lookups = hits = misses = corrupt = 0

    for component in graph.components:
        if not component.relation_ids:
            continue
        lookups += 1
        solve_key = assembly_component_solve_key(
            assembly,
            component,
            definitions,
            tolerance_profile=tolerance_profile,
        )
        authored_component = _component_assembly(assembly, component)
        restored: Assembly | None = None
        miss_reason = (
            "refresh"
            if policy.mode == CacheMode.REFRESH
            else (
                "cache_mode_bypass"
                if policy.mode == CacheMode.OFF
                else "record_missing"
            )
        )
        if policy.can_read:
            entry = store.get(_ASSEMBLY_NAMESPACE, solve_key)
            if entry is not None:
                try:
                    restored = _apply_component_payload(
                        authored_component,
                        component,
                        solve_key,
                        entry.payload,
                    )
                except ArtifactValidationError:
                    corrupt += 1
                    store.discard(
                        _ASSEMBLY_NAMESPACE,
                        solve_key,
                        reason="assembly-component",
                    )
                    miss_reason = "constraint_component_invalid"
                else:
                    hits += 1
                    miss_reason = None
        if restored is None:
            misses += 1
            computed: dict[str, Assembly] = {}

            def compute() -> bytes:
                solved = solve_assembly_constraints(authored_component, strict=True)
                computed["value"] = solved
                return _encode_component_result(component, solve_key, solved)

            if policy.can_write:
                entry, concurrent_hit = store.get_or_compute(
                    _ASSEMBLY_NAMESPACE,
                    solve_key,
                    compute,
                    media_type=_CACHE_MEDIA_TYPE,
                    metadata={
                        "assembly_id": assembly.assembly_id,
                        "component_id": component.component_id,
                    },
                )
                if concurrent_hit:
                    restored = _apply_component_payload(
                        authored_component,
                        component,
                        solve_key,
                        entry.payload,
                    )
                    hits += 1
                    misses -= 1
                    miss_reason = None
                else:
                    restored = computed["value"]
            else:
                restored = solve_assembly_constraints(
                    authored_component,
                    strict=True,
                )
        for record in _component_occurrence_placements(restored):
            result = _with_component_path_placement(
                result,
                tuple(record["component_path"]),
                Placement(**dict(record["placement"])),
            )
        component_results.append(
            ComponentSolveResult(
                component_id=component.component_id,
                solve_key=solve_key,
                instance_ids=component.instance_ids,
                relation_ids=component.relation_ids,
                cache_hit=miss_reason is None,
                solved=True,
                miss_reason=miss_reason,
            )
        )

    report = inspect_assembly_constraints(result)
    if assembly.constraints and not report.solved:
        raise ArtifactValidationError(
            "assembly_unsolved",
            "/relations",
            "incremental solve failed final residual verification",
        )
    result._set_runtime("constraint_report", report.to_dict())
    result._set_runtime(
        _AUTHORED_PLACEMENTS_RUNTIME_KEY,
        authored_placements,
    )
    return result, AssemblySolveReport(
        mode=policy.mode.value,
        component_lookups=lookups,
        component_hits=hits,
        component_misses=misses,
        corrupt_entries=corrupt,
        dirty_instances=dirty.instance_ids,
        geometry_dirty_instances=dirty.geometry_instance_ids,
        material_dirty_instances=dirty.material_instance_ids,
        binding_dirty_endpoints=dirty.binding_endpoints,
        dirty_connectors=dirty.connector_endpoints,
        dirty_relations=dirty.relation_ids,
        dirty_components=dirty.component_ids,
        component_results=tuple(component_results),
    )


__all__ = [
    "AssemblySolveReport",
    "ComponentSolveResult",
    "DirtyPropagation",
    "assembly_component_solve_key",
    "propagate_assembly_dirty_state",
    "solve_assembly_incrementally",
]
