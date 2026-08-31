"""Top-level external-reference assembly builder."""

from __future__ import annotations

import inspect
from dataclasses import replace
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Mapping, ParamSpec, Sequence, TypeVar

from ..artifacts.assembly_definition import AssemblyDefinition
from ..artifacts.assembly_io import (
    definition_archive_name,
    materialize_definition,
    validate_assembly_definition_graph,
)
from ..artifacts.canonical import (
    ArtifactValidationError,
    content_hash,
    sha256_bytes,
    validate_logical_id,
    validate_revision,
)
from ..artifacts.feature_graph import (
    FEATURE_GRAPH_MEDIA_TYPE,
    FeatureGraphArtifact,
    capture_feature_graph,
    encode_feature_graph_artifact,
)
from ..artifacts.part_definition import PartDefinition
from ..artifacts.references import (
    BlobRef,
    ConnectorInterface,
    InterfaceHashes,
    PartInstance,
    PartRef,
)
from ..artifacts.validation import validate_artifact_blobs
from ..cache.policy import CachePolicy, resolve_cache_policy
from ..recording.graph import GraphSession, get_active_session, record_operation_if_active
from ..product.assembly import Assembly, _component_occurrence_placements
from ..product.solver import inspect_assembly_constraints
from ..product.connector import ConnectorRef, resolve_connector_ref_placement
from ..product.part import Part
from ..product.placement import Placement
from .assembly_state import (
    AssemblyInterfaceSnapshot,
    load_latest_assembly_state,
    update_latest_assembly_state,
)
from .incremental_solver import solve_assembly_incrementally
from .keys import (
    builder_source_fingerprint,
    generator_profile,
    infer_project_root,
    normalize_bound_arguments,
)
from .results import AssemblyBuildResult, PartBuildResult
from ..topology import SemanticDelta, SemanticRef

_P = ParamSpec("_P")
_R = TypeVar("_R")
_SOLVER_PROFILE = "simplecad-assembly-solver-1"
_AUTHORED_PLACEMENTS_RUNTIME_KEY = "assembly.authored_component_placements"

Definition = PartDefinition | AssemblyDefinition


def _definition_value(value: Any) -> Definition:
    definition = (
        value
        if isinstance(value, (PartDefinition, AssemblyDefinition))
        else getattr(value, "definition", None)
    )
    if not isinstance(definition, (PartDefinition, AssemblyDefinition)):
        raise TypeError(
            "definitions must contain PartBuildResult, AssemblyBuildResult, "
            "PartDefinition, or AssemblyDefinition values"
        )
    return definition


def _runtime_value(value: Any, definition: Definition) -> Part | Assembly:
    runtime = getattr(value, "value", None)
    if isinstance(runtime, (Part, Assembly)):
        return runtime
    return materialize_definition(definition)


def _declared_definitions(
    values: Sequence[Any],
) -> tuple[tuple[Definition, ...], Mapping[str, Part | Assembly]]:
    by_id: dict[str, Definition] = {}
    runtime_by_id: dict[str, Part | Assembly] = {}
    for value in values:
        definition = _definition_value(value)
        prior = by_id.get(definition.definition_id)
        if prior is not None and (
            prior.definition_kind != definition.definition_kind
            or prior.content_hash != definition.content_hash
        ):
            raise ArtifactValidationError(
                "reference_identity_conflict",
                "/definitions",
                f"definition_id {definition.definition_id!r} has multiple identities",
            )
        by_id[definition.definition_id] = definition
        runtime = _runtime_value(value, definition)
        expected_id = (
            runtime.part_id if isinstance(runtime, Part) else runtime.assembly_id
        )
        if expected_id != definition.definition_id:
            raise ArtifactValidationError(
                "definition_id_mismatch",
                "/definitions",
                f"runtime value {expected_id!r} differs from definition {definition.definition_id!r}",
            )
        runtime_by_id[definition.definition_id] = runtime
    definitions = tuple(
        sorted(by_id.values(), key=lambda item: item.definition_id.encode("utf-8"))
    )
    return definitions, runtime_by_id


def _part_ref(definition: Definition) -> PartRef:
    from ..artifacts.assembly_io import _archive_bytes

    payload = _archive_bytes(definition)
    return PartRef(
        definition_id=definition.definition_id,
        definition_kind=definition.definition_kind,
        path=definition_archive_name(definition),
        revision=definition.revision,
        content_hash=definition.content_hash,
        byte_length=len(payload),
    )


def _public_connector_interface(
    assembly: Assembly,
    public: Any,
) -> ConnectorInterface:
    return ConnectorInterface(
        connector_id=public.public_connector_id,
        name=public.name,
        anchor_kind="public",
        local_frame=resolve_connector_ref_placement(
            assembly,
            ConnectorRef(public.component_id, public.connector_id),
        ).to_dict(),
        binding=None,
        source_component_id=public.component_id,
        source_connector_id=public.connector_id,
    )


def _solved_snapshot(assembly: Assembly) -> Mapping[str, Any]:
    report = inspect_assembly_constraints(assembly)
    if assembly.constraints and not report.solved:
        raise ArtifactValidationError(
            "assembly_unsolved",
            "/relations",
            "@assemble must return an assembly whose constraints pass residual verification",
        )
    return {
        "solver_profile": _SOLVER_PROFILE,
        "component_placements": [
            {
                "instance_id": component.component_id,
                "placement": component.placement.to_dict(),
            }
            for component in sorted(
                assembly.components,
                key=lambda item: item.component_id.encode("utf-8"),
            )
        ],
        "occurrence_placements": list(_component_occurrence_placements(assembly)),
        "constraint_report": report.to_dict(),
    }


def _authored_component_placements(
    assembly: Assembly,
) -> Mapping[str, Mapping[str, Any]]:
    current = {
        component.component_id: component.placement.to_dict()
        for component in assembly.components
    }
    authored = assembly._get_runtime(_AUTHORED_PLACEMENTS_RUNTIME_KEY)
    if authored is None:
        return current
    if not isinstance(authored, Mapping) or set(authored) != set(current):
        raise ArtifactValidationError(
            "assembly_provenance_invalid",
            "/instances",
            "authored component placements do not match assembly instances",
        )
    normalized: dict[str, Mapping[str, Any]] = {}
    for component_id, placement in authored.items():
        if not isinstance(placement, Mapping):
            raise ArtifactValidationError(
                "assembly_provenance_invalid",
                f"/instances/{component_id}/placement",
                "authored component placement must be a frame object",
            )
        try:
            normalized[str(component_id)] = Placement(**dict(placement)).to_dict()
        except (TypeError, ValueError) as exc:
            raise ArtifactValidationError(
                "assembly_provenance_invalid",
                f"/instances/{component_id}/placement",
                str(exc),
            ) from exc
    return normalized


def _assembly_geometry_hash(
    assembly: Assembly,
    definitions: Mapping[str, Definition],
    authored_placements: Mapping[str, Mapping[str, Any]],
) -> str:
    records = []
    for component in sorted(
        assembly.components,
        key=lambda item: item.component_id.encode("utf-8"),
    ):
        definition_id = (
            component.item.part_id
            if isinstance(component.item, Part)
            else component.item.assembly_id
        )
        definition = definitions[definition_id]
        records.append(
            {
                "instance_id": component.component_id,
                "definition_id": definition_id,
                "geometry_hash": definition.interface_hashes.geometry,
                "placement": dict(authored_placements[component.component_id]),
            }
        )
    return content_hash({"instances": records})


def _assembly_definition(
    *,
    assembly: Assembly,
    feature_graph: FeatureGraphArtifact,
    declared: tuple[Definition, ...],
    revision: str,
    tolerance_profile: str,
    generator: Mapping[str, str],
    arguments: Mapping[str, Any],
    source: Mapping[str, Any],
) -> AssemblyDefinition:
    definitions = {item.definition_id: item for item in declared}
    authored_placements = _authored_component_placements(assembly)
    used_ids: set[str] = set()
    instances: list[PartInstance] = []
    for component in sorted(
        assembly.components,
        key=lambda item: item.component_id.encode("utf-8"),
    ):
        definition_id = (
            component.item.part_id
            if isinstance(component.item, Part)
            else component.item.assembly_id
        )
        definition = definitions.get(definition_id)
        if definition is None:
            raise ArtifactValidationError(
                "reference_missing",
                f"/instances/{component.component_id}",
                f"component definition {definition_id!r} was not declared",
            )
        expected_kind = (
            "single_solid" if isinstance(component.item, Part) else "assembly"
        )
        if definition.definition_kind != expected_kind:
            raise ArtifactValidationError(
                "definition_kind_invalid",
                f"/instances/{component.component_id}",
                f"runtime component kind differs from definition {definition_id!r}",
            )
        used_ids.add(definition_id)
        instances.append(
            PartInstance(
                instance_id=component.component_id,
                definition_id=definition_id,
                name=component.name,
                placement=authored_placements[component.component_id],
            )
        )
    unused = sorted(set(definitions) - used_ids)
    if unused:
        raise ArtifactValidationError(
            "reference_unused",
            "/definition_refs",
            f"declared definition has no component instance: {unused[0]}",
        )
    connectors = tuple(
        sorted(
            (
                _public_connector_interface(assembly, public)
                for public in assembly.public_connectors
            ),
            key=lambda item: item.connector_id.encode("utf-8"),
        )
    )
    feature_payload = encode_feature_graph_artifact(feature_graph)
    feature_path = (
        "features/"
        + feature_graph.content_hash.removeprefix("sha256:")
        + ".feature-graph.zip"
    )
    definition = AssemblyDefinition(
        definition_id=assembly.assembly_id,
        revision=revision,
        tolerance_profile=tolerance_profile,
        generator=generator,
        definition_refs=tuple(_part_ref(item) for item in declared),
        instances=tuple(instances),
        relations=tuple(
            constraint.to_dict()
            for constraint in sorted(
                assembly.constraints,
                key=lambda item: item.constraint_id.encode("utf-8"),
            )
        ),
        grounded_instance_ids=tuple(
            sorted(
                assembly.grounded_component_ids,
                key=lambda item: item.encode("utf-8"),
            )
        ),
        public_connectors=connectors,
        interface_hashes=InterfaceHashes(
            geometry=_assembly_geometry_hash(
                assembly,
                definitions,
                authored_placements,
            ),
            connectors={item.connector_id: item.interface_hash for item in connectors},
            bindings={item.connector_id: item.binding_hash for item in connectors},
            material=None,
        ),
        solved_snapshot=_solved_snapshot(assembly),
        feature_graph_ref=BlobRef(
            path=feature_path,
            sha256=sha256_bytes(feature_payload),
            byte_length=len(feature_payload),
            media_type=FEATURE_GRAPH_MEDIA_TYPE,
        ),
        metadata={
            "name": assembly.name,
            "arguments": dict(arguments),
            "project_source": dict(source),
        },
        blobs={feature_path: feature_payload},
        resolved_definitions=definitions,
    )
    validate_artifact_blobs(definition.to_dict(), definition.blobs)
    validate_assembly_definition_graph(definition)
    return definition


def assemble(
    func: Callable[_P, _R] | None = None,
    *,
    id: str | None = None,
    revision: str = "1.0.0",
    definitions: Sequence[Any] = (),
    cache: CachePolicy | Mapping[str, Any] | str | None = None,
    project_root: str | Path | None = None,
    tolerance_profile: str = "simplecad-default",
) -> (
    Callable[[Callable[_P, _R]], Callable[_P, AssemblyBuildResult]]
    | Callable[_P, AssemblyBuildResult]
):
    """Decorate one assembly builder with explicit external definitions."""

    def decorate(function: Callable[_P, _R]) -> Callable[_P, AssemblyBuildResult]:
        if inspect.iscoroutinefunction(function):
            raise TypeError("@assemble does not support async functions")
        definition_id = validate_logical_id(id or function.__name__, "/definition_id")
        revision_value = validate_revision(revision)
        if not isinstance(tolerance_profile, str) or not tolerance_profile:
            raise ValueError("tolerance_profile must be a non-empty string")
        declared, runtime_by_id = _declared_definitions(tuple(definitions))
        for index, definition in enumerate(declared):
            if definition.tolerance_profile != tolerance_profile:
                raise ArtifactValidationError(
                    "profile_incompatible",
                    f"/definitions/{index}/tolerance_profile",
                    "referenced definition tolerance profile differs",
                )
        root = infer_project_root(function, project_root)
        explicit_policy: CachePolicy | Mapping[str, Any] | None
        if isinstance(cache, str):
            mode = "read_write" if cache == "auto" else cache
            explicit_policy = {"mode": mode}
        else:
            explicit_policy = cache

        @wraps(function)
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> AssemblyBuildResult:
            if get_active_session() is not None:
                raise RuntimeError(
                    "@assemble cannot be nested inside an active GraphSession"
                )
            session = GraphSession(
                graph_id=definition_id,
                allow_external_definitions=True,
            )
            with session:
                for definition in declared:
                    session.register_external_definition(
                        value=runtime_by_id[definition.definition_id],
                        definition_kind=definition.definition_kind,
                        definition_id=definition.definition_id,
                        revision=definition.revision,
                        content_hash=definition.content_hash,
                    )
                raw = function(*args, **kwargs)
                if not isinstance(raw, Assembly):
                    raise ArtifactValidationError(
                        "assembly_cardinality_invalid",
                        "/result",
                        "@assemble builder must return exactly one Assembly",
                    )
                if raw.assembly_id != definition_id:
                    raise ArtifactValidationError(
                        "definition_id_mismatch",
                        "/result/assembly_id",
                        f"expected {definition_id!r}, got {raw.assembly_id!r}",
                    )
                for component in raw.components:
                    item_id = (
                        component.item.part_id
                        if isinstance(component.item, Part)
                        else component.item.assembly_id
                    )
                    declared_runtime = runtime_by_id.get(item_id)
                    if declared_runtime is None:
                        continue
                    if isinstance(component.item, Part) != isinstance(
                        declared_runtime, Part
                    ):
                        raise ArtifactValidationError(
                            "definition_kind_invalid",
                            f"/instances/{component.component_id}",
                            "runtime component kind differs from declared definition",
                        )
                    expected_hash = declared_runtime._get_runtime(
                        "definition.content_hash"
                    )
                    actual_hash = component.item._get_runtime("definition.content_hash")
                    if expected_hash is None or actual_hash != expected_hash:
                        raise ArtifactValidationError(
                            "reference_identity_mismatch",
                            f"/instances/{component.component_id}",
                            "runtime component does not carry the declared definition identity",
                        )
            policy = resolve_cache_policy(explicit_policy, project_root=root)
            state_path = policy.root.parent / "state" / "latest-assemblies.json"
            previous = (
                load_latest_assembly_state(state_path).get(definition_id)
                if policy.can_read
                else None
            )
            solved, solve_report = solve_assembly_incrementally(
                raw,
                {item.definition_id: item for item in declared},
                tolerance_profile=tolerance_profile,
                policy=policy,
                previous=previous,
            )
            solved_snapshot = _solved_snapshot(solved)
            with session:
                record_operation_if_active(
                    "evaluate_assembly_definition",
                    dict(solved_snapshot),
                    outputs=solved,
                    input_shapes=[raw],
                    semantic_delta=SemanticDelta(
                        modified=(
                            SemanticRef(
                                graph_id="pending",
                                node_id="pending",
                                entity_type="Assembly",
                                entity_id=definition_id,
                            ),
                        ),
                        metadata={"solver_profile": _SOLVER_PROFILE},
                    ),
                    source={},
                )
                session.capture_result(value=solved)
            if len(session.result_node_ids) != 1:
                raise ArtifactValidationError(
                    "assembly_cardinality_invalid",
                    "/result_node_ids",
                    "@assemble must capture exactly one result node",
                )
            feature_graph = capture_feature_graph(
                session=session,
                owner_definition_kind="assembly",
                owner_definition_id=definition_id,
                owner_revision=revision_value,
                project_root=root,
                external_definitions=tuple(
                    {
                        "definition_kind": definition.definition_kind,
                        "definition_id": definition.definition_id,
                        "revision": definition.revision,
                        "content_hash": definition.content_hash,
                    }
                    for definition in declared
                ),
            )
            arguments = normalize_bound_arguments(function, args, kwargs)
            source = builder_source_fingerprint(function, project_root=root)
            definition = _assembly_definition(
                assembly=solved,
                feature_graph=feature_graph,
                declared=declared,
                revision=revision_value,
                tolerance_profile=tolerance_profile,
                generator=generator_profile(),
                arguments=arguments,
                source=source,
            )
            current_snapshot = AssemblyInterfaceSnapshot.from_definition(definition)
            if policy.can_write:
                update_latest_assembly_state(
                    state_path,
                    snapshot=current_snapshot,
                )
            public_changed = ()
            if previous is not None:
                before = previous.public_interface.connectors
                after = current_snapshot.public_interface.connectors
                public_changed = tuple(
                    sorted(
                        {
                            connector_id
                            for connector_id in set(before) | set(after)
                            if before.get(connector_id) != after.get(connector_id)
                        }
                    )
                )
                if public_changed:
                    solve_report = replace(
                        solve_report,
                        public_connector_changed=public_changed,
                        propagated_paths=tuple(
                            f"{definition_id}.{connector_id}"
                            for connector_id in public_changed
                        ),
                    )
            return AssemblyBuildResult(
                value=solved,
                definition=definition,
                feature_graph=feature_graph,
                solve_report=solve_report,
            )

        return wrapped

    if func is None:
        return decorate
    return decorate(func)


__all__ = ["assemble"]
