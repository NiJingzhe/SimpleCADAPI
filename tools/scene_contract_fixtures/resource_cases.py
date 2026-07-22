"""Resource-limit fixture case construction."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable

from simplecadapi.scene import (
    BASE_LIMITS,
    SceneResourceLimits,
    canonical_archive_size,
    json_resource_issues,
    preflight_aggregate_compression_ratio,
    preflight_archive_member_sizes,
    preflight_glb_counts,
    preflight_input_archive_size,
    preflight_member_compression_ratio,
    resource_count_issues,
    validate_scene_manifest,
    with_scene_revision,
)
from simplecadapi.scene.validation import (
    _compute_package_budget_totals,
    _package_budget_issues,
    _report,
)

from .common import JsonObject, first_issue


def _limits(overrides: dict[str, int]) -> SceneResourceLimits:
    return replace(BASE_LIMITS, **overrides)


def _preflight_case(
    name: str,
    operation: str,
    parameters: dict[str, object],
    callback: Callable[[], object],
) -> dict[str, object]:
    try:
        callback()
    except ValueError as exc:
        valid, error = False, str(exc)
    else:
        valid, error = True, None
    return {
        "error": error,
        "name": name,
        "operation": operation,
        "parameters": parameters,
        "valid": valid,
    }


def _issues_case(
    name: str,
    operation: str,
    parameters: dict[str, object],
    issues: tuple[Any, ...] | list[Any],
) -> dict[str, object]:
    first = issues[0] if issues else None
    return {
        "expected": (
            None if first is None else {"code": first.code, "path": first.path}
        ),
        "name": name,
        "operation": operation,
        "parameters": parameters,
        "valid": not issues,
    }


def _validation_case(
    name: str,
    operation: str,
    parameters: dict[str, object],
    report: Any,
) -> dict[str, object]:
    return {
        "expected": first_issue(report),
        "name": name,
        "operation": operation,
        "parameters": parameters,
        "valid": report.valid,
    }


def _input_size_case(name: str, size: int, overrides: dict[str, int]) -> dict[str, object]:
    parameters: dict[str, object] = {"limits": overrides, "size": size}
    return _preflight_case(
        name,
        "input_archive_size",
        parameters,
        lambda: preflight_input_archive_size(size, limits=_limits(overrides)),
    )


def _archive_sizes_case(
    name: str, sizes: dict[str, int], overrides: dict[str, int]
) -> dict[str, object]:
    parameters: dict[str, object] = {"limits": overrides, "sizes": sizes}
    return _preflight_case(
        name,
        "archive_member_sizes",
        parameters,
        lambda: preflight_archive_member_sizes(sizes, limits=_limits(overrides)),
    )


def _archive_count_case(
    name: str, count: int, overrides: dict[str, int]
) -> dict[str, object]:
    sizes = {"scene.json": 0}
    sizes.update({f"x/{index}": 0 for index in range(count - 1)})
    parameters: dict[str, object] = {"count": count, "limits": overrides}
    return _preflight_case(
        name,
        "archive_member_count",
        parameters,
        lambda: preflight_archive_member_sizes(sizes, limits=_limits(overrides)),
    )


def _compression_case(
    name: str,
    operation: str,
    uncompressed_size: int,
    compressed_size: int,
) -> dict[str, object]:
    overrides = {"compression_ratio": 2}
    parameters = {
        "compressed_size": compressed_size,
        "limits": overrides,
        "uncompressed_size": uncompressed_size,
    }
    if operation == "aggregate_compression_ratio":
        callback = lambda: preflight_aggregate_compression_ratio(
            uncompressed_size, compressed_size, limits=_limits(overrides)
        )
    else:
        callback = lambda: preflight_member_compression_ratio(
            uncompressed_size, compressed_size, limits=_limits(overrides)
        )
    return _preflight_case(name, operation, parameters, callback)


def _json_value(kind: str, text: str, field: str | None = None) -> object:
    if kind == "value":
        return {"value": text}
    if kind == "object_key":
        return {text: 0}
    if kind == "metadata_key":
        return {"metadata": {text: 0}}
    if kind == "sdk_metadata_key":
        return {"sdk_metadata": {text: 0}}
    if kind == "identifier":
        return {field or "node_id": text}
    if kind == "identifier_array":
        return {field or "component_path": [text]}
    if kind == "uri":
        return {"uri": text}
    raise AssertionError(kind)


def _json_domain_case(
    name: str,
    kind: str,
    text: str,
    overrides: dict[str, int],
    *,
    field: str | None = None,
) -> dict[str, object]:
    parameters: dict[str, object] = {
        "field": field,
        "kind": kind,
        "limits": overrides,
        "text": text,
    }
    issues = json_resource_issues(
        _json_value(kind, text, field), limits=_limits(overrides)
    )
    return _issues_case(name, "json_domain", parameters, issues)


def _nested_value(depth: int) -> object:
    value: dict[str, object] = {}
    current = value
    for _index in range(depth):
        current["x"] = {}
        current = current["x"]  # type: ignore[assignment]
    return value


def _json_depth_case(name: str, depth: int) -> dict[str, object]:
    overrides = {"json_depth": 2}
    parameters: dict[str, object] = {"depth": depth, "limits": overrides}
    issues = json_resource_issues(_nested_value(depth), limits=_limits(overrides))
    return _issues_case(name, "json_depth", parameters, issues)


def _resource_count_value(
    artifact: str, kind: str, count: int, field: str | None
) -> object:
    if kind == "collection":
        assert field is not None
        return {field: [None] * count}
    if kind == "hierarchy":
        return {"nodes": [{"source": {"component_path": ["x"] * count}}]}
    if kind == "forwarded":
        return {
            "connectors": [
                {
                    "anchor_kind": "forwarded",
                    "connector_snapshot_id": f"c{index}",
                    "forwarded_from": {
                        "source_connector_snapshot_id": f"c{index + 1}"
                    },
                }
                for index in range(count)
            ]
        }
    raise AssertionError((artifact, kind))


def _resource_count_case(
    name: str,
    artifact: str,
    kind: str,
    count: int,
    overrides: dict[str, int],
    *,
    field: str | None = None,
) -> dict[str, object]:
    parameters: dict[str, object] = {
        "artifact": artifact,
        "count": count,
        "field": field,
        "kind": kind,
        "limits": overrides,
    }
    issues = resource_count_issues(
        _resource_count_value(artifact, kind, count, field),
        artifact,
        limits=_limits(overrides),
    )
    return _issues_case(name, "resource_count", parameters, issues)


def _glb_count_case(
    name: str,
    kind: str,
    vertex_count: int,
    index_count: int,
    overrides: dict[str, int],
) -> dict[str, object]:
    parameters: dict[str, object] = {
        "index_count": index_count,
        "kind": kind,
        "limits": overrides,
        "vertex_count": vertex_count,
    }
    return _preflight_case(
        name,
        "glb_counts",
        parameters,
        lambda: preflight_glb_counts(
            kind,  # type: ignore[arg-type]
            vertex_count,
            index_count,
            limits=_limits(overrides),
        ),
    )


_BUDGET_FIELDS = {
    "entities_total": "entity_count",
    "line_segments_total": "line_segment_count",
    "line_vertices_total": "line_vertex_count",
    "static_decoded_buffer_bytes": "scene_json_bytes",
    "triangle_vertices_total": "triangle_vertex_count",
    "triangles_total": "triangle_count",
}


def _package_budget_case(
    name: str, limit_name: str, value: int
) -> dict[str, object]:
    contributions = {
        "scene_json_bytes": 0,
        "glb_decoded_buffer_bytes": 0,
        "entity_json_bytes": 0,
        "other_immutable_json_bytes": 0,
        "entity_count": 0,
        "entity_vertex_count": 0,
        "triangle_vertex_count": 0,
        "triangle_count": 0,
        "line_vertex_count": 0,
        "line_segment_count": 0,
    }
    contributions[_BUDGET_FIELDS[limit_name]] = value
    overrides = {limit_name: 2}
    totals = _compute_package_budget_totals(**contributions)
    budget_report = _report(
        _package_budget_issues(totals, limits=_limits(overrides)), artifact="package"
    )
    return _validation_case(
        name,
        "package_budget",
        {"contributions": contributions, "limits": overrides},
        budget_report,
    )


def build_resource_cases(
    scene: JsonObject,
    normalized_part: JsonObject,
) -> list[dict[str, object]]:
    input_limits = {"input_archive_bytes": 8}
    role_limits = {
        "canonical_archive_bytes": 1_000,
        "one_member_bytes": 100,
        "total_uncompressed_bytes": 100,
    }
    canonical_limits = {
        "canonical_archive_bytes": 256,
        "one_member_bytes": 100,
        "total_uncompressed_bytes": 100,
    }
    canonical_envelope = canonical_archive_size(
        {"geometry/a.glb": 0, "scene.json": 0}
    )
    canonical_payload = canonical_limits["canonical_archive_bytes"] - canonical_envelope
    one_member_limits = {
        "canonical_archive_bytes": 1_000,
        "one_member_bytes": 8,
        "total_uncompressed_bytes": 100,
    }
    total_limits = {
        "canonical_archive_bytes": 1_000,
        "one_member_bytes": 8,
        "total_uncompressed_bytes": 16,
    }
    count_limits = {"canonical_archive_bytes": 10_000, "zip_members": 3}
    cases = [
        _input_size_case("input_archive_exact_limit", 8, input_limits),
        _input_size_case("input_archive_over_limit", 9, input_limits),
        _archive_sizes_case(
            "scene_json_exact_limit",
            {"scene.json": 8},
            {**role_limits, "scene_json_bytes": 8},
        ),
        _archive_sizes_case(
            "scene_json_over_limit",
            {"scene.json": 9},
            {**role_limits, "scene_json_bytes": 8},
        ),
        _archive_sizes_case(
            "entity_json_exact_limit",
            {"entities/a.json": 8, "scene.json": 0},
            {**role_limits, "entity_json_bytes": 8},
        ),
        _archive_sizes_case(
            "entity_json_over_limit",
            {"entities/a.json": 9, "scene.json": 0},
            {**role_limits, "entity_json_bytes": 8},
        ),
        _archive_sizes_case(
            "model_json_exact_limit",
            {"model/model.json": 8, "scene.json": 0},
            {**role_limits, "model_json_bytes": 8},
        ),
        _archive_sizes_case(
            "model_json_over_limit",
            {"model/model.json": 9, "scene.json": 0},
            {**role_limits, "model_json_bytes": 8},
        ),
        _archive_sizes_case(
            "presentation_json_exact_limit",
            {"presentation/presentation.json": 8, "scene.json": 0},
            {**role_limits, "presentation_json_bytes": 8},
        ),
        _archive_sizes_case(
            "presentation_json_over_limit",
            {"presentation/presentation.json": 9, "scene.json": 0},
            {**role_limits, "presentation_json_bytes": 8},
        ),
        _archive_sizes_case(
            "canonical_archive_exact_limit",
            {"geometry/a.glb": canonical_payload, "scene.json": 0},
            canonical_limits,
        ),
        _archive_sizes_case(
            "canonical_archive_over_limit",
            {"geometry/a.glb": canonical_payload + 1, "scene.json": 0},
            canonical_limits,
        ),
        _archive_sizes_case(
            "one_member_exact_limit",
            {"geometry/a.glb": 8, "scene.json": 0},
            one_member_limits,
        ),
        _archive_sizes_case(
            "one_member_over_limit",
            {"geometry/a.glb": 9, "scene.json": 0},
            one_member_limits,
        ),
        _archive_sizes_case(
            "total_uncompressed_exact_limit",
            {"geometry/a.glb": 8, "geometry/b.glb": 8, "scene.json": 0},
            total_limits,
        ),
        _archive_sizes_case(
            "total_uncompressed_over_limit",
            {
                "geometry/a.glb": 8,
                "geometry/b.glb": 8,
                "geometry/c.glb": 1,
                "scene.json": 0,
            },
            total_limits,
        ),
        _archive_count_case("archive_member_count_exact_limit", 3, count_limits),
        _archive_count_case("archive_member_count_over_limit", 4, count_limits),
        _compression_case(
            "aggregate_compression_ratio_exact_limit",
            "aggregate_compression_ratio",
            4,
            2,
        ),
        _compression_case(
            "aggregate_compression_ratio_over_limit",
            "aggregate_compression_ratio",
            5,
            2,
        ),
        _compression_case(
            "member_compression_ratio_exact_limit",
            "member_compression_ratio",
            4,
            2,
        ),
        _compression_case(
            "member_compression_ratio_over_limit",
            "member_compression_ratio",
            5,
            2,
        ),
        _json_depth_case("json_depth_exact_limit", 2),
        _json_depth_case("json_depth_over_limit", 3),
    ]

    for kind, overrides in (
        ("value", {"json_string_bytes": 4}),
        ("object_key", {"json_string_bytes": 4}),
        (
            "metadata_key",
            {"json_string_bytes": 100, "structural_id_bytes": 4},
        ),
        (
            "sdk_metadata_key",
            {"json_string_bytes": 100, "structural_id_bytes": 4},
        ),
        ("uri", {"json_string_bytes": 100, "uri_bytes": 4}),
    ):
        cases.append(
            _json_domain_case(
                f"utf8_{kind}_exact_limit", kind, "éé", overrides
            )
        )
        cases.append(
            _json_domain_case(
                f"utf8_{kind}_over_limit", kind, "ééa", overrides
            )
        )

    identifier_fields = (
        "definition_ref",
        "node_id",
        "source_element_id",
        "topo_id",
    )
    for field in identifier_fields:
        overrides = {"json_string_bytes": 100, "structural_id_bytes": 4}
        cases.append(
            _json_domain_case(
                f"utf8_{field}_exact_limit",
                "identifier",
                "éé",
                overrides,
                field=field,
            )
        )
        cases.append(
            _json_domain_case(
                f"utf8_{field}_over_limit",
                "identifier",
                "ééa",
                overrides,
                field=field,
            )
        )

    for field in (
        "child_entity_ids",
        "component_path",
        "evaluated_tags",
        "grounded_component_ids",
        "parent_entity_ids",
        "semantic_binding_ids",
    ):
        overrides = {"json_string_bytes": 100, "structural_id_bytes": 4}
        cases.append(
            _json_domain_case(
                f"utf8_{field}_item_exact_limit",
                "identifier_array",
                "éé",
                overrides,
                field=field,
            )
        )
        cases.append(
            _json_domain_case(
                f"utf8_{field}_item_over_limit",
                "identifier_array",
                "ééa",
                overrides,
                field=field,
            )
        )

    collection_limits = (
        ("scene", "definitions", "definitions"),
        ("scene", "nodes", "nodes"),
        ("scene", "geometry_assets", "assets_per_kind"),
        ("scene", "edge_assets", "assets_per_kind"),
        ("scene", "entity_assets", "assets_per_kind"),
        ("scene", "appearances", "appearances"),
        ("scene", "connectors", "connectors"),
        ("scene", "cameras", "cameras"),
        ("entities", "entities", "entities_per_sidecar"),
        ("entities", "face_groups", "entities_per_sidecar"),
        ("entities", "edge_groups", "entities_per_sidecar"),
        ("presentation", "node_overrides", "nodes"),
        ("presentation", "appearances", "appearances"),
        ("presentation", "cameras", "cameras"),
    )
    for artifact, field, limit_name in collection_limits:
        overrides = {limit_name: 2}
        cases.append(
            _resource_count_case(
                f"{artifact}_{field}_exact_limit",
                artifact,
                "collection",
                2,
                overrides,
                field=field,
            )
        )
        cases.append(
            _resource_count_case(
                f"{artifact}_{field}_over_limit",
                artifact,
                "collection",
                3,
                overrides,
                field=field,
            )
        )

    cases.extend(
        [
            _resource_count_case(
                "hierarchy_depth_exact_limit",
                "scene",
                "hierarchy",
                2,
                {"hierarchy_depth": 2, "nodes": 10},
            ),
            _resource_count_case(
                "hierarchy_depth_over_limit",
                "scene",
                "hierarchy",
                3,
                {"hierarchy_depth": 2, "nodes": 10},
            ),
            _resource_count_case(
                "forwarded_connector_depth_exact_limit",
                "scene",
                "forwarded",
                2,
                {"connectors": 10, "forwarded_connector_depth": 2},
            ),
            _resource_count_case(
                "forwarded_connector_depth_over_limit",
                "scene",
                "forwarded",
                3,
                {"connectors": 10, "forwarded_connector_depth": 2},
            ),
            _glb_count_case(
                "triangle_vertices_per_asset_exact_limit",
                "triangle",
                2,
                3,
                {"triangle_vertices_per_asset": 2},
            ),
            _glb_count_case(
                "triangle_vertices_per_asset_over_limit",
                "triangle",
                3,
                3,
                {"triangle_vertices_per_asset": 2},
            ),
            _glb_count_case(
                "triangles_per_asset_exact_limit",
                "triangle",
                3,
                6,
                {"triangles_per_asset": 2},
            ),
            _glb_count_case(
                "triangles_per_asset_over_limit",
                "triangle",
                3,
                9,
                {"triangles_per_asset": 2},
            ),
            _glb_count_case(
                "line_vertices_per_asset_exact_limit",
                "line",
                2,
                2,
                {"line_vertices_per_asset": 2},
            ),
            _glb_count_case(
                "line_vertices_per_asset_over_limit",
                "line",
                3,
                2,
                {"line_vertices_per_asset": 2},
            ),
            _glb_count_case(
                "line_segments_per_asset_exact_limit",
                "line",
                2,
                4,
                {"line_segments_per_asset": 2},
            ),
            _glb_count_case(
                "line_segments_per_asset_over_limit",
                "line",
                2,
                6,
                {"line_segments_per_asset": 2},
            ),
        ]
    )

    for limit_name in _BUDGET_FIELDS:
        cases.append(
            _package_budget_case(f"{limit_name}_exact_limit", limit_name, 2)
        )
        cases.append(
            _package_budget_case(f"{limit_name}_over_limit", limit_name, 3)
        )

    for name, value_number in (
        ("safe_integer_exact_limit", 9_007_199_254_740_991),
        ("safe_integer_over_limit", 9_007_199_254_740_992),
    ):
        value = deepcopy(scene)
        value["geometry_assets"][0]["byte_length"] = value_number
        if value_number <= 9_007_199_254_740_991:
            value = with_scene_revision(value)
        cases.append(
            _validation_case(
                name,
                "scene_geometry_byte_length",
                {"value": str(value_number)},
                validate_scene_manifest(value),
            )
        )

    for name, field, value_number in (
        ("linear_tolerance_exact_max", "linear_tolerance", 1_000_000),
        ("linear_tolerance_over_max", "linear_tolerance", 1_000_001),
        ("angular_tolerance_exact_max", "angular_tolerance", 3.141592653589793),
        ("angular_tolerance_over_max", "angular_tolerance", 3.1415926535897936),
    ):
        value = deepcopy(scene)
        value["compile_options"][field] = value_number
        value["geometry_assets"][0]["tessellation"][field] = value_number
        if field == "linear_tolerance":
            value["edge_assets"][0]["tessellation"][field] = value_number
        value = with_scene_revision(value)
        cases.append(
            _validation_case(
                name,
                "scene_compile_option",
                {"field": field, "value": value_number},
                validate_scene_manifest(value),
            )
        )

    # Keep the argument in active use so fixture construction catches drift in
    # the valid normalized product even though resource probes are synthetic.
    assert normalized_part
    return cases
