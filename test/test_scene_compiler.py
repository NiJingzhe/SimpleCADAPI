from __future__ import annotations


import pytest

import simplecadapi as scad
from simplecadapi import _mesh
from simplecadapi import scene
from simplecadapi.scene import (
    export_scene,
    parse_canonical_json,
    preflight_zip_bytes,
    validate_scene_manifest,
    validate_scene_package,
    with_scene_revision,
)


def _manual_source() -> scene.SceneSource:
    return scene.SceneSource(kind="manual", source_id="main")



def test_compile_scene_is_deterministic_and_self_validating():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)
    roots = (scene.SceneRoot(root_id="main", value=solid),)

    first = scene.compile_scene(scene_id="box", roots=roots, source=_manual_source())
    second = scene.compile_scene(scene_id="box", roots=roots, source=_manual_source())

    assert first.manifest == second.manifest
    assert dict(first.blobs) == dict(second.blobs)
    assert validate_scene_package(first.manifest, first.blobs).valid
    assert first.manifest["revision"].startswith("sha256:")




def test_sphere_entity_uses_kernel_axis_directions():
    solid = scad.make_sphere_rsolid(radius=2.5, center=(1.0, 2.0, 3.0))
    package = scene.compile_scene(
        scene_id="sphere",
        roots=(scene.SceneRoot(root_id="main", value=solid),),
        source=_manual_source(),
    )
    entity_uri = package.manifest["entity_assets"][0]["uri"]
    entity_document = parse_canonical_json(package.blobs[entity_uri])
    sphere = next(
        entity
        for entity in entity_document["entities"]
        if entity["kind"] == "face"
    )

    assert sphere["geometry"] == {
        "type": "sphere",
        "center": [1.0, 2.0, 3.0],
        "axis": [0.0, 0.0, 1.0],
        "x_direction": [1.0, 0.0, 0.0],
        "radius": 2.5,
    }


def test_repeated_part_occurrences_reuse_definition_and_assets():
    part = scad.make_part_rpart(
        part_id="block",
        body=scad.make_box_rsolid(width=4.0, height=5.0, depth=6.0),
    )
    assembly = scad.make_assembly_rassembly(assembly_id="root")
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="first",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="second",
        placement=scad.make_placement_rplacement(origin=(10.0, 0.0, 0.0)),
    )

    package = scene.compile_scene(
        scene_id="repeated",
        roots=(scene.SceneRoot(root_id="main", value=assembly),),
        source=_manual_source(),
    )
    definitions = package.manifest["definitions"]
    nodes = package.manifest["nodes"]
    part_definitions = [item for item in definitions if item["kind"] == "part"]

    assert len(part_definitions) == 1
    assert [item["node_id"] for item in nodes] == [
        "instance/main",
        "instance/main/first",
        "instance/main/second",
    ]
    assert len(package.manifest["geometry_assets"]) == 1
    assert len(package.manifest["edge_assets"]) == 1
    assert len(package.manifest["entity_assets"]) == 1


def test_same_part_id_with_different_body_geometry_is_rejected():
    first = scad.make_part_rpart(
        part_id="shared",
        body=scad.make_box_rsolid(width=4.0, height=5.0, depth=6.0),
    )
    second = scad.make_part_rpart(
        part_id="shared",
        body=scad.make_box_rsolid(width=7.0, height=5.0, depth=6.0),
    )
    assembly = scad.make_assembly_rassembly(assembly_id="root")
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=first,
        component_id="first",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=second,
        component_id="second",
        placement=scad.identity_placement_rplacement(),
    )

    with pytest.raises(ValueError, match="conflicting Part body geometry"):
        scene.compile_scene(
            scene_id="conflict",
            roots=(scene.SceneRoot(root_id="main", value=assembly),),
            source=_manual_source(),
        )


def test_manual_face_connector_is_exported_with_entity_target():
    solid = scad.make_box_rsolid(width=4.0, height=5.0, depth=6.0)
    connector = scad.make_face_connector_rconnector(
        connector_id="mount",
        face=solid.get_faces()[0],
    )
    part = scad.make_part_rpart(part_id="block", body=solid)
    part = scad.add_connector_rpart(part=part, connector=connector)

    package = scene.compile_scene(
        scene_id="connector",
        roots=(scene.SceneRoot(root_id="main", value=part),),
        source=_manual_source(),
    )
    snapshot = package.manifest["connectors"][0]

    assert snapshot["anchor_kind"] == "geometry"
    assert snapshot["target"]["entity_id"].startswith("entity/face/")
    assert snapshot["target"]["entity_asset_id"] == package.manifest["definitions"][0]["entity_asset_id"]
    assert snapshot["source"] == {"kind": "manual", "source_id": "main"}


def test_render_and_collision_use_the_same_default_mesh_object():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)
    cached = _mesh.cached_mesh(solid)
    assert cached is not None

    render = scene.build_render_mesh(
        solid,
        face_entity_ids=[f"entity/face/{index}" for index in range(len(solid.get_faces()))],
        linear_tolerance=0.35,
        angular_tolerance=0.22,
    )

    assert _mesh.cached_mesh(solid) is cached
    assert len(render.indices) == cached.triangle_count * 3


def test_edge_mesh_uses_angular_tolerance_for_curved_edges():
    solid = scad.make_cylinder_rsolid(radius=2.0, height=5.0)
    edge_ids = [f"edge-{index}" for index, _edge in enumerate(solid.get_edges())]

    default = scene.build_edge_mesh(
        solid,
        edge_entity_ids=edge_ids,
        linear_tolerance=0.35,
        angular_tolerance=0.22,
    )
    finer = scene.build_edge_mesh(
        solid,
        edge_entity_ids=edge_ids,
        linear_tolerance=0.35,
        angular_tolerance=0.1,
    )

    default_counts = sorted(len(block.segments) for block in default.blocks)
    finer_counts = sorted(len(block.segments) for block in finer.blocks)
    assert default_counts == [1, 29, 29]
    assert finer_counts == [1, 63, 63]


def test_edge_mesh_default_angular_tolerance_preserves_public_call_shape():
    solid = scad.make_cylinder_rsolid(radius=2.0, height=5.0)
    edge_ids = [f"edge-{index}" for index, _edge in enumerate(solid.get_edges())]

    mesh = scene.build_edge_mesh(
        solid,
        edge_entity_ids=edge_ids,
        linear_tolerance=0.35,
    )

    assert sorted(len(block.segments) for block in mesh.blocks) == [1, 29, 29]


def test_compiler_declares_angular_edge_render_profile():
    package = scene.compile_scene(
        scene_id="edge-profile",
        roots=(
            scene.SceneRoot(
                root_id="main",
                value=scad.make_cylinder_rsolid(radius=2.0, height=5.0),
            ),
        ),
        source=_manual_source(),
    )

    assert package.manifest["generator"]["profile"] == "scene-1.0-ocp-glb-2"
    assert package.manifest["geometry_assets"][0]["tessellation"] == {
        "linear_tolerance": 0.1,
        "angular_tolerance": 0.08,
    }
    assert package.manifest["edge_assets"][0]["tessellation"] == {
        "linear_tolerance": 0.1
    }
    assert validate_scene_package(package.manifest, package.blobs).valid


def test_validator_keeps_profile_1_scene_packages_readable(tmp_path):
    package = scene.compile_scene(
        scene_id="legacy-profile",
        roots=(
            scene.SceneRoot(
                root_id="main",
                value=scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0),
            ),
        ),
        source=_manual_source(),
    )
    path = tmp_path / "legacy-profile.scene.zip"
    export_scene(package=package, path=path)
    archive = preflight_zip_bytes(path.read_bytes())
    manifest = parse_canonical_json(archive.members["scene.json"])
    manifest["generator"]["profile"] = "scene-1.0-ocp-glb-1"
    manifest = with_scene_revision(manifest)

    assert validate_scene_package(manifest, package.blobs).valid


def test_export_scene_is_canonical_and_round_trips_through_archive_preflight(tmp_path):
    package = scene.compile_scene(
        scene_id="archive",
        roots=(scene.SceneRoot(root_id="main", value=scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)),),
        source=_manual_source(),
    )
    first_path = tmp_path / "first.scene.zip"
    second_path = tmp_path / "second.scene.zip"
    export_scene(package=package, path=first_path)
    export_scene(package=package, path=second_path)

    first_bytes = first_path.read_bytes()
    assert first_bytes == second_path.read_bytes()
    archive = preflight_zip_bytes(first_bytes)
    manifest = parse_canonical_json(archive.members["scene.json"])
    blobs = {name: payload for name, payload in archive.members.items() if name != "scene.json"}
    report = validate_scene_package(manifest, blobs)
    assert report.valid, report.issues


def test_forwarded_connector_is_finalized_after_its_source_connector():
    part = scad.make_part_rpart(
        part_id="inner",
        body=scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0),
    )
    part = scad.add_connector_rpart(
        part=part,
        connector=scad.make_placement_connector_rconnector(
            connector_id="axis",
            placement=scad.make_placement_rplacement(origin=(1.0, 0.0, 0.0)),
        ),
    )
    child = scad.make_assembly_rassembly(assembly_id="child")
    child = scad.add_component_rassembly(
        assembly=child,
        item=part,
        component_id="inner",
        placement=scad.make_placement_rplacement(origin=(5.0, 0.0, 0.0)),
    )
    child = scad.forward_connector_rassembly(
        assembly=child,
        connector_id="public",
        source_component_id="inner",
        source_connector_id="axis",
    )
    root = scad.make_assembly_rassembly(assembly_id="root")
    root = scad.add_component_rassembly(
        assembly=root,
        item=child,
        component_id="child",
        placement=scad.identity_placement_rplacement(),
    )

    package = scene.compile_scene(
        scene_id="forwarded",
        roots=(scene.SceneRoot(root_id="main", value=root),),
        source=_manual_source(),
    )

    forwarded = next(item for item in package.manifest["connectors"] if item["connector_id"] == "public")
    source = next(item for item in package.manifest["connectors"] if item["connector_id"] == "axis")
    assert forwarded["forwarded_from"]["source_connector_snapshot_id"] == source["connector_snapshot_id"]
    assert validate_scene_package(package.manifest, package.blobs).valid
