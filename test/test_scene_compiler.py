from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi import _mesh
from simplecadapi.scene import (
    export_scene,
    parse_canonical_json,
    preflight_zip_bytes,
    validate_scene_manifest,
    validate_scene_package,
    with_scene_revision,
)


def _manual_source() -> scad.SceneSource:
    return scad.SceneSource(kind="manual", source_id="main")


def _mutable_package(package, tmp_path, name):
    archive_path = tmp_path / f"{name}.scene.zip"
    export_scene(package=package, path=archive_path)
    archive = preflight_zip_bytes(archive_path.read_bytes())
    manifest = parse_canonical_json(archive.members["scene.json"])
    blobs = {
        uri: payload
        for uri, payload in archive.members.items()
        if uri != "scene.json"
    }
    return manifest, blobs


def _replace_embedded_model(manifest, blobs, model):
    payload = json.dumps(model, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    blobs["model/model.json"] = payload
    manifest["source"]["artifact_hash"] = (
        "sha256:" + hashlib.sha256(payload).hexdigest()
    )
    manifest["source"]["embedded_artifact_byte_length"] = len(payload)
    return with_scene_revision(manifest)


@pytest.fixture
def embedded_source_package():
    @scad.model(graph_id="source-boundaries")
    def build_model():
        return scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)

    result = build_model()
    return scad.compile_scene(
        scene_id="source-boundaries",
        roots=(scad.SceneRoot(root_id="main", value=result.value),),
        source=result,
        options=scad.SceneCompileOptions(embed_source=True),
    )


def test_compile_scene_is_deterministic_and_self_validating():
    solid = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)
    roots = (scad.SceneRoot(root_id="main", value=solid),)

    first = scad.compile_scene(scene_id="box", roots=roots, source=_manual_source())
    second = scad.compile_scene(scene_id="box", roots=roots, source=_manual_source())

    assert first.manifest == second.manifest
    assert dict(first.blobs) == dict(second.blobs)
    assert validate_scene_package(first.manifest, first.blobs).valid
    assert first.manifest["revision"].startswith("sha256:")


def test_embedded_python_source_is_integrity_checked(tmp_path):
    @scad.model(graph_id="source-integrity")
    def build_model():
        return scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)

    result = build_model()
    package = scad.compile_scene(
        scene_id="source-integrity",
        roots=(scad.SceneRoot(root_id="main", value=result.value),),
        source=result,
        options=scad.SceneCompileOptions(embed_source=True),
    )
    source_record = package.manifest["source"]["source_files"][0]

    assert source_record["path"] == "test/test_scene_compiler.py"
    assert package.blobs[source_record["uri"]] == Path(__file__).read_bytes()
    assert validate_scene_package(package.manifest, package.blobs).valid

    tampered = dict(package.blobs)
    tampered[source_record["uri"]] += b"\n# tampered\n"
    report = validate_scene_package(package.manifest, tampered)
    assert not report.valid
    assert {issue.code for issue in report.issues} >= {
        "blob_hash_mismatch",
        "blob_length_mismatch",
    }

    archive_path = tmp_path / "source-integrity.scene.zip"
    export_scene(package=package, path=archive_path)
    archive = preflight_zip_bytes(archive_path.read_bytes())
    malformed_manifest = parse_canonical_json(archive.members["scene.json"])
    malformed_manifest["source"]["source_files"][0]["uri"] = "sources/wrong.py"
    malformed_manifest = with_scene_revision(malformed_manifest)
    report = validate_scene_package(malformed_manifest, package.blobs)
    assert not report.valid
    assert "source_matrix_invalid" in {issue.code for issue in report.issues}


def test_model_scene_rejects_root_from_different_graph_with_same_graph_id():
    @scad.model(graph_id="shared-provenance-id")
    def first_model():
        return scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

    @scad.model(graph_id="shared-provenance-id")
    def second_model():
        return scad.make_box_rsolid(width=4.0, height=5.0, depth=6.0)

    first = first_model()
    second = second_model()

    with pytest.raises(ValueError, match="not owned by the source model graph"):
        scad.compile_scene(
            scene_id="cross-graph-root",
            roots=(scad.SceneRoot(root_id="main", value=first.value),),
            source=second,
        )


def test_model_scene_rejects_stale_model_result_snapshot():
    @scad.model(graph_id="stale-model-snapshot")
    def build_model():
        return scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

    result = build_model()
    result.session.graph.add_node("late_mutation", node_id="late_mutation")

    with pytest.raises(ValueError, match="no longer matches its model JSON snapshot"):
        scad.compile_scene(
            scene_id="stale-model-snapshot",
            roots=(scad.SceneRoot(root_id="main", value=result.value),),
            source=result,
        )


def test_manifest_rejects_unsafe_embedded_python_path(
    embedded_source_package, tmp_path
):
    manifest, _blobs = _mutable_package(
        embedded_source_package, tmp_path, "unsafe-source-path"
    )
    source_file = manifest["source"]["source_files"][0]
    source_file["path"] = "test/../test_scene_compiler.py"
    source_file["uri"] = "sources/test/../test_scene_compiler.py"
    report = validate_scene_manifest(with_scene_revision(manifest))

    assert any(
        issue.code == "source_matrix_invalid"
        and issue.path == "/source/source_files/0/path"
        for issue in report.issues
    )


def test_package_rejects_malformed_operation_source_mapping(
    embedded_source_package, tmp_path
):
    manifest, blobs = _mutable_package(
        embedded_source_package, tmp_path, "malformed-operation-source"
    )
    model = json.loads(blobs["model/model.json"])
    node = next(node for node in model["graph"]["nodes"] if "source" in node)
    node["source"].pop("callsite_id")
    manifest = _replace_embedded_model(manifest, blobs, model)
    report = validate_scene_package(manifest, blobs)

    assert any(
        issue.code == "source_matrix_invalid"
        and issue.path.endswith("/graph/nodes/0/source")
        for issue in report.issues
    )


def test_package_rejects_invalid_utf8_python_source(
    embedded_source_package, tmp_path
):
    manifest, blobs = _mutable_package(
        embedded_source_package, tmp_path, "invalid-source-utf8"
    )
    source_file = manifest["source"]["source_files"][0]
    payload = b"\xff"
    blobs[source_file["uri"]] = payload
    source_file["byte_length"] = len(payload)
    source_file["content_hash"] = "sha256:" + hashlib.sha256(payload).hexdigest()
    report = validate_scene_package(with_scene_revision(manifest), blobs)

    assert any(
        issue.code == "invalid_utf8" and issue.path == f"/{source_file['uri']}"
        for issue in report.issues
    )


def test_sphere_entity_uses_kernel_axis_directions():
    solid = scad.make_sphere_rsolid(radius=2.5, center=(1.0, 2.0, 3.0))
    package = scad.compile_scene(
        scene_id="sphere",
        roots=(scad.SceneRoot(root_id="main", value=solid),),
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

    package = scad.compile_scene(
        scene_id="repeated",
        roots=(scad.SceneRoot(root_id="main", value=assembly),),
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
        scad.compile_scene(
            scene_id="conflict",
            roots=(scad.SceneRoot(root_id="main", value=assembly),),
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

    package = scad.compile_scene(
        scene_id="connector",
        roots=(scad.SceneRoot(root_id="main", value=part),),
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

    render = scad.build_render_mesh(
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

    default = scad.build_edge_mesh(
        solid,
        edge_entity_ids=edge_ids,
        linear_tolerance=0.35,
        angular_tolerance=0.22,
    )
    finer = scad.build_edge_mesh(
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

    mesh = scad.build_edge_mesh(
        solid,
        edge_entity_ids=edge_ids,
        linear_tolerance=0.35,
    )

    assert sorted(len(block.segments) for block in mesh.blocks) == [1, 29, 29]


def test_compiler_declares_angular_edge_render_profile():
    package = scad.compile_scene(
        scene_id="edge-profile",
        roots=(
            scad.SceneRoot(
                root_id="main",
                value=scad.make_cylinder_rsolid(radius=2.0, height=5.0),
            ),
        ),
        source=_manual_source(),
    )

    assert package.manifest["generator"]["profile"] == "scene-1.0-ocp-glb-2"
    assert package.manifest["edge_assets"][0]["tessellation"] == {
        "linear_tolerance": 0.35
    }
    assert validate_scene_package(package.manifest, package.blobs).valid


def test_validator_keeps_profile_1_scene_packages_readable(tmp_path):
    package = scad.compile_scene(
        scene_id="legacy-profile",
        roots=(
            scad.SceneRoot(
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
    package = scad.compile_scene(
        scene_id="archive",
        roots=(scad.SceneRoot(root_id="main", value=scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)),),
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

    package = scad.compile_scene(
        scene_id="forwarded",
        roots=(scad.SceneRoot(root_id="main", value=root),),
        source=_manual_source(),
    )

    forwarded = next(item for item in package.manifest["connectors"] if item["connector_id"] == "public")
    source = next(item for item in package.manifest["connectors"] if item["connector_id"] == "axis")
    assert forwarded["forwarded_from"]["source_connector_snapshot_id"] == source["connector_snapshot_id"]
    assert validate_scene_package(package.manifest, package.blobs).valid


def test_model_connector_sources_use_product_attachment_operations():
    @scad.model(graph_id="connector_provenance")
    def build_model():
        body = scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0)
        part = scad.make_part_rpart(part_id="block", body=body)
        part = scad.add_connector_rpart(
            part=part,
            connector=scad.make_placement_connector_rconnector(
                connector_id="axis",
                placement=scad.identity_placement_rplacement(),
            ),
        )
        assembly = scad.make_assembly_rassembly(assembly_id="root")
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=part,
            component_id="block",
            placement=scad.identity_placement_rplacement(),
        )
        assembly = scad.forward_connector_rassembly(
            assembly=assembly,
            connector_id="public_axis",
            source_component_id="block",
            source_connector_id="axis",
        )
        assembly = scad.place_component_rassembly(
            assembly=assembly,
            component_id="block",
            placement=scad.make_placement_rplacement(origin=(1.0, 0.0, 0.0)),
        )
        scad.capture_result(value=assembly)
        return assembly

    result = build_model()
    package = scad.compile_scene(
        scene_id="connector-provenance",
        roots=(scad.SceneRoot(root_id="main", value=result.value),),
        source=result,
    )
    graph_nodes = {
        node.node_id: node for node in result.session.graph.nodes
    }
    sources = {
        connector["connector_id"]: connector["source"]
        for connector in package.manifest["connectors"]
    }

    assert graph_nodes[sources["axis"]["node_id"]].op == "make_add_connector_rpart"
    assert (
        graph_nodes[sources["public_axis"]["node_id"]].op
        == "make_forward_connector_rassembly"
    )
    assert sources["axis"]["node_id"] != sources["public_axis"]["node_id"]
    assert validate_scene_package(package.manifest, package.blobs).valid
