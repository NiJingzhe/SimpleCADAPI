from pathlib import Path

import pytest

import simplecadapi as scad
from simplecadapi.product_packages import ProductPackageError
from simplecadapi.scene import parse_canonical_json, preflight_zip_bytes


def _box_part(part_id: str = "box") -> scad.Part:
    return scad.make_part_rpart(
        part_id=part_id,
        body=scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0),
    )


def test_part_package_round_trip_is_self_contained(tmp_path: Path) -> None:
    part = _box_part()
    package = scad.build_part_package(part)
    path = scad.export_product_package(package, tmp_path / "box.prt.zip")

    loaded_package = scad.read_product_package(path, kind="part")
    loaded_part = scad.load_part_package(path)

    assert loaded_package.manifest["artifact_kind"] == "part"
    assert loaded_part.part_id == part.part_id
    assert loaded_part.body.get_volume() == pytest.approx(part.body.get_volume())
    assert set(loaded_package.blobs) == {
        loaded_package.manifest[field]["uri"]
        for field in ("body_ref", "topology_ref", "connector_ref")
    }


def test_nested_assembly_round_trip_reuses_one_part_definition(tmp_path: Path) -> None:
    part = _box_part()
    child = scad.make_assembly_rassembly(assembly_id="child")
    child = scad.add_component_rassembly(
        assembly=child,
        item=part,
        component_id="inner",
        placement=scad.make_placement_rplacement(origin=(1.0, 2.0, 3.0)),
    )
    root = scad.make_assembly_rassembly(assembly_id="root")
    root = scad.add_component_rassembly(
        assembly=root,
        item=child,
        component_id="nested",
        placement=scad.make_placement_rplacement(origin=(10.0, 0.0, 0.0)),
    )
    root = scad.add_component_rassembly(
        assembly=root,
        item=part,
        component_id="direct",
        placement=scad.make_placement_rplacement(origin=(0.0, 5.0, 0.0)),
    )

    package = scad.build_assembly_package(root)
    path = scad.export_product_package(package, tmp_path / "root.asm.zip")
    loaded = scad.load_assembly_package(path)
    nested = loaded.get_component("nested").item

    assert loaded.component_ids() == ("nested", "direct")
    assert isinstance(nested, scad.Assembly)
    assert nested.component_ids() == ("inner",)
    assert nested.get_component("inner").placement.origin == (1.0, 2.0, 3.0)
    assert nested.get_component("inner").item is loaded.get_component("direct").item
    assert len([name for name in package.blobs if name.endswith(".part.json")]) == 1


def test_product_package_rejects_hash_mutation_and_unreferenced_member() -> None:
    part = _box_part()
    package = scad.build_part_package(part)
    body_uri = package.manifest["body_ref"]["uri"]
    mutated = dict(package.blobs)
    mutated[body_uri] = mutated[body_uri] + b"x"
    with pytest.raises(ProductPackageError, match="byte_length|content_hash"):
        scad.validate_product_package(package.manifest, mutated, kind="part")

    extra = dict(package.blobs)
    extra["unexpected.bin"] = b"unexpected"
    with pytest.raises(ProductPackageError, match="member set"):
        scad.validate_product_package(package.manifest, extra, kind="part")


def test_assembly_package_preserves_connectors_constraints_and_grounding(
    tmp_path: Path,
) -> None:
    body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
    part = scad.make_part_rpart(part_id="linked", body=body)
    part = scad.add_connector_rpart(
        part=part,
        connector=scad.make_placement_connector_rconnector(
            connector_id="axis",
            placement=scad.identity_placement_rplacement(),
        ),
    )
    assembly = scad.make_assembly_rassembly(assembly_id="fixture")
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="follower",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.forward_connector_rassembly(
        assembly=assembly,
        connector_id="public_axis",
        source_component_id="base",
        source_connector_id="axis",
    )
    assembly = scad.ground_component_rassembly(
        assembly=assembly,
        component_id="base",
    )
    assembly = scad.add_fixed_constraint_rassembly(
        assembly=assembly,
        constraint_id="fixed",
        connector_a=scad.make_connector_ref_rconnectorref(
            component_id="base", connector_id="axis"
        ),
        connector_b=scad.make_connector_ref_rconnectorref(
            component_id="follower", connector_id="axis"
        ),
    )

    path = scad.export_product_package(
        scad.build_assembly_package(assembly),
        tmp_path / "fixture.asm.zip",
    )
    loaded = scad.load_assembly_package(path)

    assert loaded.grounded_component_ids == ("base",)
    assert loaded.connectors[0].to_dict() == assembly.connectors[0].to_dict()
    assert loaded.constraints[0].to_dict() == assembly.constraints[0].to_dict()
    assert loaded.get_component("base").item.connectors[0].connector_id == "axis"


def test_product_package_reexport_is_byte_identical(tmp_path: Path) -> None:
    first = scad.export_product_package(
        scad.build_part_package(_box_part()),
        tmp_path / "first.prt.zip",
    )
    loaded = scad.read_product_package(first)
    second = scad.export_product_package(loaded, tmp_path / "second.prt.zip")

    assert first.read_bytes() == second.read_bytes()


def test_model_result_explicit_product_and_scene_exports(tmp_path: Path) -> None:
    @scad.model(graph_id="explicit_products")
    def build_model() -> scad.Part:
        part = _box_part("captured")
        scad.capture_result(value=part)
        return part

    result = build_model()
    exported = result.export_artifacts(
        output_dir=tmp_path,
        formats=("prt", "scene"),
    )

    assert set(exported.artifact_paths) == {"part", "scene"}
    assert exported.artifact_paths["part"].name.endswith(".prt.zip")
    assert exported.artifact_paths["scene"].name.endswith(".scene.zip")
    assert scad.load_part_package(exported.artifact_paths["part"]).part_id == "captured"
    scene_archive = preflight_zip_bytes(exported.artifact_paths["scene"].read_bytes())
    scene_manifest = parse_canonical_json(scene_archive.members["scene.json"])
    part_package = scad.read_product_package(exported.artifact_paths["part"])

    assert scene_archive.manifest_name == "scene.json"
    assert scene_manifest["source"] == {
        "kind": "part_package",
        "definition_id": "captured",
        "revision": part_package.content_hash,
        "artifact_hash": part_package.content_hash,
    }
    assert scene_manifest["compile_options"]["embed_source"] is False
    assert not any(name.endswith(".prt.zip") for name in scene_archive.members)
    assert all(
        definition["source"]["kind"] == "product_package"
        for definition in scene_manifest["definitions"]
    )


def test_model_result_rejects_duplicate_export_formats(tmp_path: Path) -> None:
    @scad.model(graph_id="duplicate_formats")
    def build_model() -> scad.Part:
        return _box_part("captured")

    result = build_model()
    with pytest.raises(ValueError, match="duplicates"):
        result.export_artifacts(output_dir=tmp_path, formats=("part", "prt"))
