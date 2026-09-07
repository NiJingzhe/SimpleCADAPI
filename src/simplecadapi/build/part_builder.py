"""Top-level single-solid part builder and whole-part cache."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import replace
import inspect
from functools import wraps
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Hashable, Mapping, ParamSpec, Sequence, TypeVar, cast, overload

from ..artifacts.assembly_io import materialize_definition
from ..artifacts.brep import write_brep_bytes
from ..artifacts.feature_graph import (
    FEATURE_GRAPH_MEDIA_TYPE,
    FeatureGraphArtifact,
    capture_feature_graph,
    encode_feature_graph_artifact,
)
from ..artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    parse_canonical_json,
    sha256_bytes,
    validate_logical_id,
    validate_revision,
)
from ..artifacts.geometry_interface import geometry_interface_fingerprint
from ..artifacts.interface import (
    PartInterfaceDiff,
    diff_part_interfaces,
    load_latest_part_state,
    update_latest_part_state,
)
from ..artifacts.part_definition import (
    PartDefinition,
    mark_part_definition_validated,
    validated_part_feature_graph,
)
from ..artifacts.part_io import encode_part_definition, load_part_definition
from ..artifacts.references import (
    BlobRef,
    ConnectorInterface,
    InterfaceHashes,
    MaterialRef,
)
from ..artifacts.topology_snapshot import (
    encode_topology_snapshot,
    resolve_geometry_entity_ref,
    validate_connector_entity_bindings,
)
from ..artifacts.validation import validate_artifact_blobs
from ..cache.policy import CacheMode, CachePolicy, resolve_cache_policy
from ..cache.store import ContentAddressedStore
from ..core import Solid
from ..recording.graph import (
    GraphSession,
    attach_graph_node,
    attach_semantic_graph_node,
    get_active_session,
)
from ..operators import make_part_rpart
from ..product.connector import Connector, resolve_connector_placement
from ..product.material import Material
from ..product.part import Part
from ..scene.archive import canonical_zip_bytes, preflight_zip_bytes
from .dependencies import FileInput, snapshot_file_inputs
from .keys import (
    PART_CACHE_PROFILE,
    builder_source_fingerprint,
    generator_profile,
    infer_project_root,
    normalize_bound_arguments,
    part_build_key,
)
from .results import CacheReport, PartBuildResult

_P = ParamSpec("_P")
_R = TypeVar("_R")
_PART_NAMESPACE = "part"
_CACHE_MANIFEST = "cache.json"
_CACHE_MEDIA_TYPE = "application/vnd.simplecad.part-cache+zip"
_CACHE_BUNDLE_VERSION = "3.0"


def _memory_hit_result(result: PartBuildResult) -> PartBuildResult:

    return replace(
        result,
        cache_report=replace(
            result.cache_report,
            part_lookups=0,
            part_hits=1,
            part_misses=0,
            corrupt_entries=0,
            miss_reason=None,
            bytes_read=0,
            bytes_written=0,
        ),
        interface_diff=None,
    )


def _memoized_part_call(
    *,
    key: Hashable,
    memo: dict[Hashable, Future[PartBuildResult]],
    lock: Lock,
    build: Callable[[], PartBuildResult],
    valid: Callable[[PartBuildResult], bool],
) -> PartBuildResult:
    """Compute one valid build key once, replacing stale in-process source snapshots."""

    while True:
        with lock:
            future = memo.get(key)
            if future is None:
                future = Future()
                memo[key] = future
                owner = True
            else:
                owner = False
        if owner:
            break
        result = future.result()
        if valid(result):
            return _memory_hit_result(result)
        with lock:
            if memo.get(key) is future:
                del memo[key]
    try:
        result = build()
    except BaseException as exc:
        future.set_exception(exc)
        with lock:
            if memo.get(key) is future:
                del memo[key]
        raise
    future.set_result(result)
    return result


def _blob_ref(path: str, payload: bytes, media_type: str) -> BlobRef:
    return BlobRef(
        path=path,
        sha256=sha256_bytes(payload),
        byte_length=len(payload),
        media_type=media_type,
    )


def _material_ref(
    material: Material | None,
) -> tuple[MaterialRef | None, dict[str, bytes]]:
    if material is None:
        return None, {}
    payload = canonical_bytes({"schema_version": "1.0", **material.to_dict()})
    digest = sha256_bytes(payload)
    path = f"material/{digest.removeprefix('sha256:')}.json"
    return (
        MaterialRef(
            material_id=material.material_id,
            path=path,
            revision=digest.removeprefix("sha256:")[:32],
            sha256=digest,
            byte_length=len(payload),
        ),
        {path: payload},
    )


def _connector_interface(connector: Connector, body: Solid) -> ConnectorInterface:
    anchor = cast(Any, connector.anchor)
    frame = resolve_connector_placement(connector).to_dict()
    binding: Mapping[str, Any] | None = None
    if anchor.anchor_kind == "geometry":
        geometry_ref = anchor.geometry_ref
        binding = {
            **geometry_ref.to_dict(),
            "resolved_entities": [resolve_geometry_entity_ref(body, geometry_ref)],
        }
    return ConnectorInterface(
        connector_id=connector.connector_id,
        name=connector.name,
        anchor_kind=anchor.anchor_kind,
        local_frame=frame,
        binding=binding,
    )


def _part_definition(
    *,
    part: Part,
    feature_graph: FeatureGraphArtifact,
    revision: str,
    tolerance_profile: str,
    file_inputs: tuple[Any, ...],
    generator: Mapping[str, str],
) -> PartDefinition:
    feature_payload = encode_feature_graph_artifact(feature_graph)
    body_payload = write_brep_bytes(part.body)
    topology_payload = encode_topology_snapshot(part.body)
    feature_path = (
        "features/"
        + feature_graph.content_hash.removeprefix("sha256:")
        + ".feature-graph.zip"
    )
    body_path = f"body/{sha256_bytes(body_payload).removeprefix('sha256:')}.brep"
    topology_path = (
        f"topology/{sha256_bytes(topology_payload).removeprefix('sha256:')}.json"
    )
    material_ref, material_blobs = _material_ref(part.material)
    connectors = tuple(
        sorted(
            (_connector_interface(item, part.body) for item in part.connectors),
            key=lambda item: item.connector_id.encode("utf-8"),
        )
    )
    interface_hashes = InterfaceHashes(
        geometry=geometry_interface_fingerprint(
            part.body,
            tolerance_profile=tolerance_profile,
        ),
        connectors={item.connector_id: item.interface_hash for item in connectors},
        bindings={item.connector_id: item.binding_hash for item in connectors},
        material=material_ref.sha256 if material_ref is not None else None,
    )
    blobs = {
        feature_path: feature_payload,
        body_path: body_payload,
        topology_path: topology_payload,
        **material_blobs,
    }
    definition = PartDefinition(
        definition_id=part.part_id,
        revision=revision,
        tolerance_profile=tolerance_profile,
        generator=generator,
        feature_graph_ref=_blob_ref(
            feature_path,
            feature_payload,
            FEATURE_GRAPH_MEDIA_TYPE,
        ),
        solid_cache_ref=_blob_ref(
            body_path, body_payload, "application/vnd.opencascade.brep"
        ),
        topology_snapshot_ref=_blob_ref(
            topology_path, topology_payload, "application/json"
        ),
        connectors=connectors,
        material_ref=material_ref,
        file_inputs=tuple(file_inputs),
        interface_hashes=interface_hashes,
        metadata={"name": part.name},
        blobs=blobs,
    )
    validate_artifact_blobs(definition.to_dict(), definition.blobs)
    validate_connector_entity_bindings(part.body, definition.connectors)
    mark_part_definition_validated(
        definition,
        body=part.body,
        feature_graph=feature_graph,
    )
    return definition


def _cache_payload(
    *,
    definition: PartDefinition,
    build_record: Mapping[str, Any],
) -> bytes:
    definition_member = "definition/part-definition.zip"
    definition_payload = encode_part_definition(definition)
    members = {definition_member: definition_payload}
    manifest = {
        "schema_version": _CACHE_BUNDLE_VERSION,
        "profile": PART_CACHE_PROFILE,
        "definition_member": definition_member,
        "build_record": dict(build_record),
        "member_hashes": {
            definition_member: sha256_bytes(definition_payload),
        },
    }
    members[_CACHE_MANIFEST] = canonical_bytes(manifest)
    return canonical_zip_bytes(members, manifest_name=_CACHE_MANIFEST)


def _load_cache_payload(
    payload: bytes,
) -> tuple[Part, PartDefinition, FeatureGraphArtifact]:
    archive = preflight_zip_bytes(payload, manifest_name=_CACHE_MANIFEST)
    manifest = parse_canonical_json(archive.members[_CACHE_MANIFEST])
    required = {
        "schema_version",
        "profile",
        "definition_member",
        "build_record",
        "member_hashes",
    }
    if not isinstance(manifest, Mapping) or set(manifest) != required:
        raise ArtifactValidationError(
            "part_cache_invalid", "/", "cache manifest fields are not closed"
        )
    if (
        manifest["schema_version"] != _CACHE_BUNDLE_VERSION
        or manifest["profile"] != PART_CACHE_PROFILE
    ):
        raise ArtifactValidationError(
            "part_cache_invalid", "/profile", "unsupported cache profile"
        )
    member_hashes = manifest["member_hashes"]
    definition_member = str(manifest["definition_member"])
    if (
        not isinstance(member_hashes, Mapping)
        or set(member_hashes) != {definition_member}
        or set(archive.members) != {_CACHE_MANIFEST, definition_member}
    ):
        raise ArtifactValidationError(
            "part_cache_invalid", "/members", "cache member set differs"
        )
    definition_payload = archive.members[definition_member]
    if sha256_bytes(definition_payload) != member_hashes[definition_member]:
        raise ArtifactValidationError(
            "blob_hash_mismatch",
            f"/member_hashes/{definition_member}",
            "member digest differs",
        )
    definition = load_part_definition(definition_payload)
    feature_graph = validated_part_feature_graph(definition)
    if not isinstance(feature_graph, FeatureGraphArtifact):
        raise ArtifactValidationError(
            "part_cache_invalid",
            "/definition/feature_graph_ref",
            "validated feature graph is unavailable",
        )
    materialized = materialize_definition(definition)
    if not isinstance(materialized, Part):
        raise ArtifactValidationError(
            "part_cache_invalid",
            "/definition_id",
            "part definition materialized as assembly",
        )
    if (
        geometry_interface_fingerprint(
            materialized.body,
            tolerance_profile=definition.tolerance_profile,
        )
        != definition.interface_hashes.geometry
    ):
        raise ArtifactValidationError(
            "geometry_mismatch", "/interface_hashes/geometry", "body interface differs"
        )
    return _attach_feature_graph_result(materialized, feature_graph), definition, feature_graph


def _attach_feature_graph_result(
    part: Part,
    feature_graph: FeatureGraphArtifact,
) -> Part:
    session = feature_graph.restore_session()
    result_node_id = feature_graph.result_node_ids[0]
    node = session.graph.get_node(result_node_id)
    if node is None:
        raise ArtifactValidationError(
            "result_invalid", "/result_node_ids/0", "result node does not exist"
        )
    attach_graph_node(part.body, node, graph_id=session.graph.graph_id)
    attach_semantic_graph_node(part, node, graph_id=session.graph.graph_id)
    session._captured_values.append(part)
    session.validate_graph_ownership(part)
    return part


def _latest_part_diff(
    *,
    policy: CachePolicy,
    definition: PartDefinition,
    build_key: str,
) -> PartInterfaceDiff | None:
    if not policy.can_read and not policy.can_write:
        return None
    state_path = policy.root.parent / "state" / "latest-parts.json"
    if policy.can_write:
        previous = update_latest_part_state(
            state_path,
            definition=definition,
            build_key=build_key,
        )
    else:
        previous = load_latest_part_state(state_path).get(definition.definition_id)
    if previous is None:
        return None
    diff = diff_part_interfaces(
        previous,
        definition,
        after_build_key=build_key,
    )
    return diff if diff.build_key_changed or diff.interface_changed else None


def _coerce_part(value: Any, definition_id: str) -> Part:
    if isinstance(value, Solid):
        return make_part_rpart(part_id=definition_id, body=value)
    if isinstance(value, Part):
        if value.part_id != definition_id:
            raise ArtifactValidationError(
                "definition_id_mismatch",
                "/result/part_id",
                f"expected {definition_id!r}, got {value.part_id!r}",
            )
        return value
    raise ArtifactValidationError(
        "solid_cardinality_invalid",
        "/result",
        "@part builder must return exactly one Solid or one Part",
    )


def _cold_build(
    function: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
    *,
    definition_id: str,
    revision: str,
    tolerance_profile: str,
    file_inputs: tuple[Any, ...],
    generator: Mapping[str, str],
    project_root: Path,
) -> tuple[Part, PartDefinition, FeatureGraphArtifact]:
    session = GraphSession(graph_id=definition_id)
    with session:
        raw = function(*args, **dict(kwargs))
        part = _coerce_part(raw, definition_id)
        session.validate_graph_ownership(part)
        session.capture_result(value=part)
        if len(session.result_node_ids) != 1:
            raise ArtifactValidationError(
                "solid_cardinality_invalid",
                "/result_node_ids",
                "@part must capture exactly one result node",
            )
    feature_graph = capture_feature_graph(
        session=session,
        owner_definition_kind="single_solid",
        owner_definition_id=definition_id,
        owner_revision=revision,
        project_root=project_root,
    )
    definition = _part_definition(
        part=part,
        feature_graph=feature_graph,
        revision=revision,
        tolerance_profile=tolerance_profile,
        file_inputs=file_inputs,
        generator=generator,
    )
    part = _attach_feature_graph_result(part, feature_graph)
    return part, definition, feature_graph


@overload
def part(func: Callable[_P, _R]) -> Callable[_P, PartBuildResult]: ...

@overload
def part(
    *,
    id: str | None = ...,
    revision: str = ...,
    inputs: Sequence[FileInput] = ...,
    cache: CachePolicy | Mapping[str, Any] | str | None = ...,
    project_root: str | Path | None = ...,
    tolerance_profile: str = ...,
) -> Callable[[Callable[_P, _R]], Callable[_P, PartBuildResult]]: ...

def part(
    func: Callable[_P, _R] | None = None,
    *,
    id: str | None = None,
    revision: str = "1.0.0",
    inputs: Sequence[FileInput] = (),
    cache: CachePolicy | Mapping[str, Any] | str | None = None,
    project_root: str | Path | None = None,
    tolerance_profile: str = "simplecad-default",
) -> Callable[[Callable[_P, _R]], Callable[_P, PartBuildResult]] | Callable[_P, PartBuildResult]:
    """Decorate one synchronous builder as a cached single-solid product part."""

    def decorate(function: Callable[_P, _R]) -> Callable[_P, PartBuildResult]:
        if inspect.iscoroutinefunction(function):
            raise TypeError("@part does not support async functions")
        definition_id = validate_logical_id(id or function.__name__, "/definition_id")
        revision_value = validate_revision(revision)
        if not isinstance(tolerance_profile, str) or not tolerance_profile:
            raise ValueError("tolerance_profile must be a non-empty string")
        declared_inputs = tuple(inputs)
        if not all(isinstance(item, FileInput) for item in declared_inputs):
            raise TypeError("inputs must contain values returned by file_input()")
        root = infer_project_root(function, project_root)
        explicit_policy: CachePolicy | Mapping[str, Any] | None
        if isinstance(cache, str):
            mode = "read_write" if cache == "auto" else cache
            explicit_policy = {"mode": mode}
        else:
            explicit_policy = cache

        memo: dict[Hashable, Future[PartBuildResult]] = {}
        memo_lock = Lock()

        @wraps(function)
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> PartBuildResult:
            if get_active_session() is not None:
                raise RuntimeError("@part cannot be nested inside an active GraphSession")
            arguments = normalize_bound_arguments(function, args, kwargs)
            snapshots = snapshot_file_inputs(declared_inputs, project_root=root)
            source = builder_source_fingerprint(function, project_root=root)
            generator = generator_profile()
            key, build_record = part_build_key(
                definition_id=definition_id,
                revision=revision_value,
                tolerance_profile=tolerance_profile,
                arguments=arguments,
                source=source,
                file_inputs=snapshots,
                generator=generator,
            )
            policy = resolve_cache_policy(explicit_policy, project_root=root)

            def build_once() -> PartBuildResult:
                store = ContentAddressedStore(policy)
                corrupt_entries = 0
                miss_reason = "refresh" if policy.mode == CacheMode.REFRESH else None
                if policy.can_read:
                    entry = store.get(_PART_NAMESPACE, key)
                    if entry is not None:
                        try:
                            part_value, definition, feature_graph = _load_cache_payload(
                                entry.payload
                            )
                            if feature_graph.source_dependencies_match(project_root=root):
                                interface_diff = _latest_part_diff(
                                    policy=policy,
                                    definition=definition,
                                    build_key=key,
                                )
                                return PartBuildResult(
                                    value=part_value,
                                    definition=definition,
                                    feature_graph=feature_graph,
                                    cache_report=CacheReport(
                                        mode=policy.mode.value,
                                        build_key=key,
                                        part_lookups=1,
                                        part_hits=1,
                                        part_misses=0,
                                        bytes_read=len(entry.payload),
                                    ),
                                    interface_diff=interface_diff,
                                )
                            miss_reason = "source_changed"
                        except (
                            ArtifactValidationError,
                            UnicodeError,
                            ValueError,
                            KeyError,
                            TypeError,
                        ):
                            corrupt_entries = 1
                            miss_reason = "corrupt_entry"
                            store.discard(_PART_NAMESPACE, key, reason="part-payload")
                    elif miss_reason is None:
                        miss_reason = "record_missing"
                elif miss_reason is None:
                    miss_reason = "cache_mode_bypass"

                part_value, definition, feature_graph = _cold_build(
                    function,
                    args,
                    kwargs,
                    definition_id=definition_id,
                    revision=revision_value,
                    tolerance_profile=tolerance_profile,
                    file_inputs=snapshots,
                    generator=generator,
                    project_root=root,
                )
                payload = _cache_payload(
                    definition=definition,
                    build_record=build_record,
                )
                bytes_written = 0
                if policy.can_write:
                    store.put(
                        _PART_NAMESPACE,
                        key,
                        payload,
                        media_type=_CACHE_MEDIA_TYPE,
                        metadata={
                            "definition_id": definition_id,
                            "definition_hash": definition.content_hash,
                            "profile": PART_CACHE_PROFILE,
                        },
                    )
                    bytes_written = len(payload)
                interface_diff = _latest_part_diff(
                    policy=policy,
                    definition=definition,
                    build_key=key,
                )
                return PartBuildResult(
                    value=part_value,
                    definition=definition,
                    feature_graph=feature_graph,
                    cache_report=CacheReport(
                        mode=policy.mode.value,
                        build_key=key,
                        part_lookups=1 if policy.can_read else 0,
                        part_hits=0,
                        part_misses=1,
                        corrupt_entries=corrupt_entries,
                        miss_reason=miss_reason,
                        bytes_written=bytes_written,
                    ),
                    interface_diff=interface_diff,
                )

            if not policy.can_read:
                return build_once()
            memo_key = (policy, key)
            return _memoized_part_call(
                key=memo_key,
                memo=memo,
                lock=memo_lock,
                build=build_once,
                valid=lambda result: result.feature_graph.source_dependencies_match(
                    project_root=root
                ),
            )

        return wrapped

    if func is None:
        return decorate
    return decorate(func)


__all__ = ["part"]
