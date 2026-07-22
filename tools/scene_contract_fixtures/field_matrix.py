"""Declarative required, nullable, and discriminated-union mutations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from simplecadapi.scene import canonical_json_bytes, with_scene_revision

from .common import sha256_hex


Path = tuple[str | int, ...]


def _case(
    name: str,
    operation: str,
    path: Path,
    value: Any = None,
    *,
    recompute_revision: bool = False,
) -> dict[str, Any]:
    mutation = {"operation": operation, "path": list(path)}
    if operation != "delete":
        mutation["value"] = value
    return {
        "mutations": [mutation],
        "name": name,
        "recompute_revision": recompute_revision,
    }


def _missing_fields(path: Path, fields: Iterable[str]) -> Iterable[dict[str, Any]]:
    for field in fields:
        yield _case(
            "missing_" + "_".join((*map(str, path), field)),
            "delete",
            (*path, field),
        )


def scene_field_matrix(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Return compact mutations covering the frozen structural field matrix."""

    records: list[tuple[Path, tuple[str, ...]]] = [
        (
            (),
            (
                "schema_version", "extensions_used", "extensions_required",
                "extensions", "scene_id", "revision", "generator", "source",
                "coordinate_system", "compile_options", "definitions", "nodes",
                "geometry_assets", "edge_assets", "appearances", "entity_assets",
                "connectors", "cameras", "lights", "annotations", "diagnostics",
            ),
        ),
        (
            ("compile_options",),
            ("linear_tolerance", "angular_tolerance", "embed_source", "embed_presentation"),
        ),
        (
            ("definitions", 0),
            ("definition_id", "kind", "name", "source", "sdk_metadata"),
        ),
        (
            ("nodes", 0),
            (
                "node_id", "parent_node_id", "order", "definition_id", "name",
                "transform", "visible", "selectable", "appearance_override_id",
                "source", "sdk_metadata",
            ),
        ),
        (
            ("appearances", 0),
            (
                "appearance_id", "name", "source", "base_color", "metallic",
                "roughness", "alpha_mode", "double_sided", "edge_color", "sdk_metadata",
            ),
        ),
        (
            ("geometry_assets", 0),
            (
                "asset_id", "uri", "media_type", "byte_length", "content_hash",
                "scene_local_bounds", "asset_to_scene", "tessellation",
            ),
        ),
        (
            ("entity_assets", 0),
            ("entity_asset_id", "uri", "media_type", "byte_length", "content_hash"),
        ),
    ]
    result = [
        mutation
        for path, fields in records
        for mutation in _missing_fields(path, fields)
    ]
    result.extend(
        _case(name, "add", path, True)
        for name, path in (
            ("unknown_scene_field", ("unknown",)),
            ("unknown_generator_field", ("generator", "unknown")),
            ("unknown_compile_options_field", ("compile_options", "unknown")),
            ("unknown_definition_field", ("definitions", 0, "unknown")),
            ("unknown_node_field", ("nodes", 0, "unknown")),
            ("unknown_appearance_field", ("appearances", 0, "unknown")),
        )
    )
    result.extend(
        (
            _case("optional_presentation_source_null", "add", ("presentation_source",), None),
            _case("unknown_scene_source_kind", "set", ("source", "kind"), "unknown"),
            _case(
                "unknown_definition_source_kind",
                "set",
                ("definitions", 0, "source", "kind"),
                "unknown",
            ),
            _case("missing_node_source_kind", "delete", ("nodes", 0, "source", "kind")),
            _case("unsupported_scene_schema_version", "set", ("schema_version",), "2.0"),
            _case(
                "unsupported_generator_profile",
                "set",
                ("generator", "profile"),
                "scene-2.0",
            ),
            _case(
                "no_presentation_visibility_override",
                "set",
                ("nodes", 0, "visible"),
                False,
                recompute_revision=True,
            ),
            _case(
                "no_presentation_selectability_override",
                "set",
                ("nodes", 0, "selectable"),
                False,
                recompute_revision=True,
            ),
            _case(
                "no_presentation_appearance_override",
                "set",
                ("nodes", 0, "appearance_override_id"),
                scene["appearances"][0]["appearance_id"],
                recompute_revision=True,
            ),
            _case(
                "no_presentation_camera",
                "set",
                ("cameras",),
                [
                    {
                        "camera_id": "camera/fixture/overview",
                        "far": 1000,
                        "name": "overview",
                        "near": 1,
                        "parent_node_id": None,
                        "projection": "perspective",
                        "transform": {
                            "origin": [10, -10, 10],
                            "x_axis": [1, 0, 0],
                            "y_axis": [0, 1, 0],
                            "z_axis": [0, 0, 1],
                        },
                        "vertical_fov_degrees": 45,
                    }
                ],
                recompute_revision=True,
            ),
        )
    )
    return result


def apply_scene_field_case(scene: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Replay one mutation descriptor to produce its validator input."""

    result = deepcopy(scene)
    for mutation in case["mutations"]:
        path = mutation["path"]
        current: Any = result
        for part in path[:-1]:
            current = current[part]
        if mutation["operation"] == "delete":
            del current[path[-1]]
        else:
            current[path[-1]] = deepcopy(mutation.get("value"))
    if case.get("recompute_revision"):
        result = with_scene_revision(result)
    return result


def nullable_fields_nonnull_case(scene: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the multi-field valid nullable vector and its compact descriptor."""

    value = deepcopy(scene)
    value["nodes"][0]["name"] = "Named occurrence"
    value["appearances"][0]["name"] = "Named appearance"
    appearance = value["appearances"][0]
    draft = dict(appearance)
    draft.pop("appearance_id")
    appearance_id = "appearance/evaluated/" + sha256_hex(canonical_json_bytes(draft))
    appearance["appearance_id"] = appearance_id
    value["definitions"][0]["appearance_id"] = appearance_id
    descriptor = {
        "mutations": [
            {"operation": "set", "path": ["nodes", 0, "name"], "value": "Named occurrence"},
            {"operation": "set", "path": ["appearances", 0, "name"], "value": "Named appearance"},
            {"operation": "set", "path": ["appearances", 0, "appearance_id"], "value": appearance_id},
            {"operation": "set", "path": ["definitions", 0, "appearance_id"], "value": appearance_id},
        ],
        "name": "nullable_fields_nonnull",
        "recompute_revision": True,
    }
    return with_scene_revision(value), descriptor
