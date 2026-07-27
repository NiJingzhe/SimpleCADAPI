"""Scene package provenance and connector-binding fixture builders."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable

from simplecadapi.scene import with_scene_revision

from .common import (
    JsonObject,
    ScenePackage,
    inline_package_case,
    replace_entity_sidecar,
    set_product_material_appearance,
)


def build_source_scene_package(
    base_scene: JsonObject,
    base_entity: JsonObject,
    base_blobs: dict[str, bytes],
    variant: str,
) -> ScenePackage:
    scene = deepcopy(base_scene)
    entity = deepcopy(base_entity)
    definition = scene["definitions"][0]
    source_for: Callable[[JsonObject], JsonObject]
    status_for: Callable[[JsonObject], str]

    if variant == "imported_shape":
        definition_id = "definition/root/shape/imported/element"
        scene["scene_id"] = "imported_fixture"
        scene["source"] = {
            "artifact_hash": "sha256:" + "1" * 64,
            "format": "step",
            "kind": "imported",
        }
        definition.update(
            {
                "definition_id": definition_id,
                "kind": "shape",
                "source": {
                    "kind": "imported",
                    "root_id": "root",
                    "source_element_id": "element",
                },
            }
        )
        source_for = lambda record: {
            "kind": "imported_primitive",
            "source_element_id": record["entity_id"],
        }
        status_for = lambda record: (
            "not_applicable" if record["kind"] == "solid" else "owner_not_part"
        )
    else:
        definition_kind = "part" if variant == "model_part" else "shape"
        definition_id = (
            "definition/root/part/model_part"
            if definition_kind == "part"
            else "definition/root/shape/model/graph/body/0"
        )
        scene["scene_id"] = f"{variant}_fixture"
        scene["source"] = {
            "artifact_hash": "sha256:" + "2" * 64,
            "graph_id": "graph",
            "kind": "model",
            "model_schema_version": "2.0",
        }
        definition_source: JsonObject = {
            "graph_id": "graph",
            "kind": "product_model" if definition_kind == "part" else "model_output",
            "node_id": "body",
            "output_slot": 0,
            "root_id": "root",
        }
        if definition_kind == "part":
            definition_source.update(
                {"semantic_id": "model_part", "semantic_type": "Part"}
            )
        definition.update(
            {
                "definition_id": definition_id,
                "kind": definition_kind,
                "source": definition_source,
            }
        )
        topology_kind = {
            "solid": "SOLID",
            "face": "FACE",
            "edge": "EDGE",
            "vertex": "VERTEX",
        }
        if variant == "model_part":
            source_for = lambda record: {
                "graph_id": "graph",
                "kind": "model_topology",
                "node_id": "body",
                "output_slot": 0,
                "topo_id": record["entity_id"],
                "topology_kind": topology_kind[record["kind"]],
            }
            statuses = iter(
                ["supported", "selector_ambiguous", "selector_unstable", "supported"]
            )

            def status_for(record: JsonObject) -> str:
                return (
                    "not_applicable"
                    if record["kind"] == "solid"
                    else next(statuses, "supported")
                )

        else:
            source_for = lambda _record: {
                "graph_id": "graph",
                "kind": "model_output",
                "node_id": "body",
                "output_slot": 0,
            }
            status_for = lambda record: (
                "not_applicable"
                if record["kind"] == "solid"
                else "owner_not_part"
            )

    if definition["kind"] == "part":
        scene["nodes"][0]["source"] = {
            "component_path": [],
            "kind": "product_occurrence",
            "root_id": "root",
        }
    scene["nodes"][0]["definition_id"] = definition_id
    entity["definition_id"] = definition_id
    for record in entity["entities"]:
        record["source"] = source_for(record)
        record["connector_binding_status"] = status_for(record)
    if variant == "model_part":
        edge = next(record for record in entity["entities"] if record["kind"] == "edge")
        edge["sdk_connector_frame"] = None
        edge["connector_binding_status"] = "frame_undefined"
    scene, entity, blobs = replace_entity_sidecar(
        scene, entity, dict(base_blobs)
    )
    if definition["kind"] == "part":
        set_product_material_appearance(scene)
    return with_scene_revision(scene), entity, blobs


def build_package_matrix_cases(
    scene: JsonObject,
    entity: JsonObject,
    blobs: dict[str, bytes],
    scene_packages: dict[str, ScenePackage],
    blob_pool: dict[str, str],
) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for variant in ("imported_shape", "model_shape", "model_part"):
        package = build_source_scene_package(scene, entity, blobs, variant)
        cases.append(
            inline_package_case(
                f"valid_{variant}", package[0], package[2], blob_pool
            )
        )

    nested = scene_packages["nested_assembly"]
    model_part = build_source_scene_package(scene, entity, blobs, "model_part")
    status_mutations = [
        (
            "solid_status_precedence",
            (deepcopy(scene), deepcopy(entity), dict(blobs)),
            "solid",
            "supported",
        ),
        (
            "owner_not_part_status_precedence",
            (deepcopy(scene), deepcopy(entity), dict(blobs)),
            "face",
            "source_not_model",
        ),
        (
            "source_not_model_status_precedence",
            deepcopy(nested),
            "face",
            "supported",
        ),
        (
            "frame_undefined_status_precedence",
            deepcopy(model_part),
            "edge",
            "owner_not_part",
        ),
    ]
    for name, package, kind, status in status_mutations:
        status_scene, status_entity, status_blobs = package
        target = next(
            record for record in status_entity["entities"] if record["kind"] == kind
        )
        target["connector_binding_status"] = status
        status_scene, _status_entity, status_blobs = replace_entity_sidecar(
            status_scene, status_entity, status_blobs
        )
        cases.append(
            inline_package_case(
                name, with_scene_revision(status_scene), status_blobs, blob_pool
            )
        )

    forwarded_scene, _forwarded_entity, forwarded_blobs = deepcopy(nested)
    root_connector = next(
        record
        for record in forwarded_scene["connectors"]
        if record["connector_id"] == "root_mount"
    )
    root_connector["local_transform"]["origin"] = [0, 0, 6]
    cases.append(
        inline_package_case(
            "forwarded_transform_mismatch",
            with_scene_revision(forwarded_scene),
            forwarded_blobs,
            blob_pool,
        )
    )

    missing_child_scene, _missing_child_entity, missing_child_blobs = deepcopy(nested)
    root_connector = next(
        record
        for record in missing_child_scene["connectors"]
        if record["connector_id"] == "root_mount"
    )
    root_connector["forwarded_from"]["source_component_id"] = "missing"
    cases.append(
        inline_package_case(
            "forwarded_direct_child_missing",
            with_scene_revision(missing_child_scene),
            missing_child_blobs,
            blob_pool,
        )
    )

    part_owner_scene, _part_owner_entity, part_owner_blobs = deepcopy(nested)
    root_connector = next(
        record
        for record in part_owner_scene["connectors"]
        if record["connector_id"] == "root_mount"
    )
    root_connector["owner_definition_id"] = "definition/root/part/shared_part"
    root_connector["connector_snapshot_id"] = (
        "connector/root/part/shared_part/root_mount"
    )
    part_owner_scene["connectors"].sort(
        key=lambda record: record["connector_snapshot_id"]
    )
    cases.append(
        inline_package_case(
            "forwarded_owner_not_assembly",
            with_scene_revision(part_owner_scene),
            part_owner_blobs,
            blob_pool,
        )
    )
    return cases
