"""Minimal, nested, and repeated-instance Scene fixture builders."""

from __future__ import annotations

from copy import deepcopy

from simplecadapi.scene import with_scene_revision

from .common import (
    IDENTITY,
    JsonObject,
    ScenePackage,
    replace_entity_sidecar,
    set_product_material_appearance,
    transform,
)


def _product_definition(
    definition_id: str,
    kind: str,
    semantic_id: str,
    renderable: JsonObject | None = None,
) -> JsonObject:
    definition: JsonObject = {
        "definition_id": definition_id,
        "kind": kind,
        "name": semantic_id.replace("_", " ").title(),
        "sdk_metadata": {},
        "source": {
            "kind": "product_manual",
            "root_id": "root",
            "semantic_id": semantic_id,
            "semantic_type": "Part" if kind == "part" else "Assembly",
        },
    }
    if renderable is not None:
        definition.update(
            {
                field: renderable[field]
                for field in (
                    "appearance_id",
                    "edge_asset_id",
                    "entity_asset_id",
                    "geometry_asset_id",
                )
            }
        )
    return definition


def _product_node(
    component_path: list[str],
    definition_id: str,
    order: int,
    local_transform: JsonObject | None = None,
) -> JsonObject:
    node_id = "instance/root" + "".join(f"/{part}" for part in component_path)
    parent_id = (
        None
        if not component_path
        else "instance/root" + "".join(f"/{part}" for part in component_path[:-1])
    )
    return {
        "appearance_override_id": None,
        "definition_id": definition_id,
        "name": component_path[-1] if component_path else "root",
        "node_id": node_id,
        "order": order,
        "parent_node_id": parent_id,
        "sdk_metadata": {},
        "selectable": True,
        "source": {
            "component_path": component_path,
            "kind": "product_occurrence",
            "root_id": "root",
        },
        "transform": deepcopy(local_transform or IDENTITY),
        "visible": True,
    }


def _manual_connector(
    owner_definition_id: str,
    owner_kind: str,
    owner_semantic_id: str,
    connector_id: str,
    anchor_kind: str,
    local_transform: JsonObject,
    *,
    forwarded_from: JsonObject | None = None,
) -> JsonObject:
    connector: JsonObject = {
        "anchor_kind": anchor_kind,
        "connector_id": connector_id,
        "connector_snapshot_id": (
            f"connector/root/{owner_kind}/{owner_semantic_id}/{connector_id}"
        ),
        "local_transform": local_transform,
        "name": connector_id.replace("_", " ").title(),
        "owner_definition_id": owner_definition_id,
        "sdk_metadata": {},
        "source": {"kind": "manual", "source_id": "fixture"},
    }
    if forwarded_from is not None:
        connector["forwarded_from"] = forwarded_from
    return connector


def build_product_scene_package(
    base_scene: JsonObject,
    base_entity: JsonObject,
    base_blobs: dict[str, bytes],
    *,
    nested: bool,
) -> ScenePackage:
    scene = deepcopy(base_scene)
    entity = deepcopy(base_entity)
    root_definition_id = "definition/root/assembly/root_assembly"
    part_definition_id = "definition/root/part/shared_part"
    renderable = deepcopy(scene["definitions"][0])
    definitions = [
        _product_definition(root_definition_id, "assembly", "root_assembly"),
        _product_definition(part_definition_id, "part", "shared_part", renderable),
    ]
    nodes = [_product_node([], root_definition_id, 0)]
    connectors: list[JsonObject] = []

    if nested:
        nested_definition_id = "definition/root/assembly/nested_assembly"
        definitions.append(
            _product_definition(
                nested_definition_id, "assembly", "nested_assembly"
            )
        )
        nodes.extend(
            [
                _product_node(["subassembly"], nested_definition_id, 0),
                _product_node(["subassembly", "part"], part_definition_id, 0),
            ]
        )
        part_connector = _manual_connector(
            part_definition_id,
            "part",
            "shared_part",
            "mount",
            "placement",
            transform(),
        )
        nested_connector = _manual_connector(
            nested_definition_id,
            "assembly",
            "nested_assembly",
            "nested_mount",
            "forwarded",
            transform(),
            forwarded_from={
                "offset": None,
                "source_component_id": "part",
                "source_connector_id": "mount",
                "source_connector_snapshot_id": part_connector[
                    "connector_snapshot_id"
                ],
                "source_definition_id": part_definition_id,
            },
        )
        root_offset = transform([0, 0, 5])
        root_connector = _manual_connector(
            root_definition_id,
            "assembly",
            "root_assembly",
            "root_mount",
            "forwarded",
            deepcopy(root_offset),
            forwarded_from={
                "offset": root_offset,
                "source_component_id": "subassembly",
                "source_connector_id": "nested_mount",
                "source_connector_snapshot_id": nested_connector[
                    "connector_snapshot_id"
                ],
                "source_definition_id": nested_definition_id,
            },
        )
        connectors = [part_connector, nested_connector, root_connector]
        scene["scene_id"] = "nested_fixture"
    else:
        nodes.extend(
            [
                _product_node(
                    ["left"], part_definition_id, 0, transform([-1000, 0, 0])
                ),
                _product_node(
                    ["right"], part_definition_id, 1, transform([1000, 0, 0])
                ),
            ]
        )
        scene["scene_id"] = "repeated_fixture"

    scene["definitions"] = sorted(
        definitions, key=lambda value: value["definition_id"].encode("utf-8")
    )
    scene["nodes"] = sorted(
        nodes, key=lambda value: value["node_id"].encode("utf-8")
    )
    scene["connectors"] = sorted(
        connectors,
        key=lambda value: value["connector_snapshot_id"].encode("utf-8"),
    )
    entity["definition_id"] = part_definition_id
    for record in entity["entities"]:
        if record["kind"] != "solid":
            record["connector_binding_status"] = "source_not_model"
    scene, entity, blobs = replace_entity_sidecar(
        scene, entity, dict(base_blobs)
    )
    set_product_material_appearance(scene)
    return with_scene_revision(scene), entity, blobs
