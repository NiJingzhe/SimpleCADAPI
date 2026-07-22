"""Scene shape, field-matrix, and two-pass revision corpus sections."""

from __future__ import annotations

from copy import deepcopy

from simplecadapi.scene import canonical_json_bytes, validate_scene_manifest

from .common import (
    JsonObject,
    ScenePackage,
    b64,
    content_hash,
    first_issue,
    scene_shape_case,
)
from .field_matrix import (
    apply_scene_field_case,
    nullable_fields_nonnull_case,
    scene_field_matrix,
)
from .scene_cases import build_product_scene_package


def build_scene_shape_cases(
    scene: JsonObject,
    entity: JsonObject,
    blobs: dict[str, bytes],
    blob_pool: dict[str, str],
) -> tuple[list[dict[str, object]], dict[str, ScenePackage]]:
    nested = build_product_scene_package(scene, entity, blobs, nested=True)
    repeated = build_product_scene_package(scene, entity, blobs, nested=False)
    packages = {
        "minimal_standalone_shape": (deepcopy(scene), deepcopy(entity), dict(blobs)),
        "nested_assembly": nested,
        "repeated_part_instance": repeated,
    }
    cases = [
        scene_shape_case(
            "minimal_standalone_shape",
            scene,
            blobs,
            {
                "definition_count": 1,
                "definition_occurrence_counts": {
                    "definition/root/shape/manual/fixture": 1
                },
                "edge_asset_count": 1,
                "entity_asset_count": 1,
                "geometry_asset_count": 1,
                "maximum_depth": 0,
                "node_count": 1,
                "root_node_ids": ["instance/root"],
            },
            blob_pool,
        ),
        scene_shape_case(
            "nested_assembly",
            nested[0],
            nested[2],
            {
                "definition_count": 3,
                "definition_occurrence_counts": {
                    "definition/root/assembly/nested_assembly": 1,
                    "definition/root/assembly/root_assembly": 1,
                    "definition/root/part/shared_part": 1,
                },
                "edge_asset_count": 1,
                "entity_asset_count": 1,
                "geometry_asset_count": 1,
                "maximum_depth": 2,
                "node_count": 3,
                "root_node_ids": ["instance/root"],
            },
            blob_pool,
        ),
        scene_shape_case(
            "repeated_part_instance",
            repeated[0],
            repeated[2],
            {
                "definition_count": 2,
                "definition_occurrence_counts": {
                    "definition/root/assembly/root_assembly": 1,
                    "definition/root/part/shared_part": 2,
                },
                "edge_asset_count": 1,
                "entity_asset_count": 1,
                "geometry_asset_count": 1,
                "maximum_depth": 1,
                "node_count": 3,
                "root_node_ids": ["instance/root"],
            },
            blob_pool,
        ),
    ]
    return cases, packages


def build_scene_field_cases(scene: JsonObject) -> list[dict[str, object]]:
    descriptors = scene_field_matrix(scene)
    nullable_value, nullable_descriptor = nullable_fields_nonnull_case(scene)
    descriptors.append(nullable_descriptor)
    result = []
    for descriptor in descriptors:
        value = (
            nullable_value
            if descriptor["name"] == "nullable_fields_nonnull"
            else apply_scene_field_case(scene, descriptor)
        )
        report = validate_scene_manifest(canonical_json_bytes(value))
        result.append(
            {
                **descriptor,
                "expected": first_issue(report),
                "valid": report.valid,
            }
        )
    return result


def build_revision_vectors(
    scene_packages: dict[str, ScenePackage],
) -> list[dict[str, object]]:
    vectors = []
    for name, (scene, _entity, _blobs) in scene_packages.items():
        draft = deepcopy(scene)
        revision = draft.pop("revision")
        draft_bytes = canonical_json_bytes(draft)
        scene_bytes = canonical_json_bytes(scene)
        vectors.append(
            {
                "canonical_base64": b64(scene_bytes),
                "draft_base64": b64(draft_bytes),
                "name": name,
                "revision": revision,
                "sha256": content_hash(scene_bytes),
            }
        )
    return vectors
