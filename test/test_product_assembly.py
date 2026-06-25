import inspect
import json
import math

import pytest

import simplecadapi as scad
from simplecadapi import ql


def test_material_validation_and_assignment_are_separate_from_part_creation():
    body = scad.make_box_rsolid(2.0, 3.0, 1.0)
    part_signature = inspect.signature(scad.make_part_rpart)

    assert "material" not in part_signature.parameters

    material = scad.make_material_rmaterial(
        "aluminum_6061",
        name="Aluminum 6061",
        density=2.7e-6,
        density_unit="kg/mm^3",
        color=(0.7, 0.7, 0.75),
    )
    part = scad.make_part_rpart("base_plate", body, name="Base plate")
    assigned = scad.assign_material_rpart(part, material)

    assert part.material is None
    assert assigned.material == material
    assert assigned.body is body

    with pytest.raises(Exception, match="density_unit"):
        scad.make_material_rmaterial("bad_density", density=1.0)

    with pytest.raises(Exception, match="color"):
        scad.make_material_rmaterial("bad_color", color=(1.2, 0.0, 0.0))


def test_placement_is_canonical_right_handed_frame():
    placement = scad.make_placement_rplacement(
        origin=(10.0, 20.0, 30.0),
        x_axis=(0.0, 1.0, 0.0),
        y_axis=(-1.0, 0.0, 0.0),
    )

    assert placement.origin == (10.0, 20.0, 30.0)
    assert placement.z_axis == (0.0, -0.0, 1.0)
    assert placement.transform_point((1.0, 2.0, 3.0)) == (8.0, 21.0, 33.0)

    with pytest.raises(Exception, match="orthogonal"):
        scad.make_placement_rplacement(
            origin=(0.0, 0.0, 0.0),
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(1.0, 0.0, 0.0),
        )

    with pytest.raises(Exception, match="non-zero"):
        scad.make_placement_rplacement(
            origin=(0.0, 0.0, 0.0),
            x_axis=(0.0, 0.0, 0.0),
        )


def test_assembly_components_reuse_part_and_project_to_compound():
    bolt_body = scad.make_cylinder_rsolid(1.0, 2.0)
    bolt_part = scad.make_part_rpart("bolt", bolt_body)
    assembly = scad.make_assembly_rassembly("fixture")

    assembly = scad.add_component_rassembly(
        assembly,
        bolt_part,
        component_id="bolt_left",
        placement=scad.make_placement_rplacement(origin=(-5.0, 0.0, 0.0)),
    )
    assembly = scad.add_component_rassembly(
        assembly,
        bolt_part,
        component_id="bolt_right",
        placement=scad.make_placement_rplacement(origin=(5.0, 0.0, 0.0)),
    )

    assert assembly.component_ids() == ("bolt_left", "bolt_right")
    assert assembly.get_component("bolt_left").item is bolt_part

    compound = scad.make_compound_from_assembly_rcompound(assembly)
    assert isinstance(compound, scad.Compound)
    assert len(compound.get_solids()) == 2
    assert math.isclose(compound.get_volume(), 2.0 * bolt_body.get_volume(), rel_tol=1e-7)

    face_centers_x = sorted(round(face.get_center().x, 1) for face in ql.faces().resolve(compound))
    assert face_centers_x[0] < 0.0
    assert face_centers_x[-1] > 0.0


def test_nested_assembly_projection_composes_component_placements():
    body = scad.make_box_rsolid(1.0, 1.0, 1.0)
    part = scad.make_part_rpart("cube_part", body)
    child = scad.make_assembly_rassembly("child_assembly")
    child = scad.add_component_rassembly(
        child,
        part,
        component_id="cube",
        placement=scad.make_placement_rplacement(origin=(2.0, 0.0, 0.0)),
    )
    root = scad.make_assembly_rassembly("root_assembly")
    root = scad.add_component_rassembly(
        root,
        child,
        component_id="child",
        placement=scad.make_placement_rplacement(origin=(10.0, 0.0, 0.0)),
    )

    compound = scad.make_compound_from_assembly_rcompound(root)
    face_centers_x = sorted(round(face.get_center().x, 1) for face in ql.faces().resolve(compound))

    assert len(compound.get_solids()) == 1
    assert face_centers_x[0] >= 11.5
    assert face_centers_x[-1] <= 12.5


def test_assembly_rejects_duplicate_components_raw_solids_and_cycles():
    body = scad.make_box_rsolid(1.0, 1.0, 1.0)
    part = scad.make_part_rpart("box_part", body)
    placement = scad.identity_placement_rplacement()
    assembly = scad.make_assembly_rassembly("root")
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="box", placement=placement
    )

    with pytest.raises(Exception, match="duplicate component_id"):
        scad.add_component_rassembly(
            assembly, part, component_id="box", placement=placement
        )

    with pytest.raises(Exception, match="item"):
        scad.add_component_rassembly(
            assembly, body, component_id="raw_solid", placement=placement
        )

    child = scad.make_assembly_rassembly("child")
    child = scad.add_component_rassembly(
        child, assembly, component_id="parent_instance", placement=placement
    )

    with pytest.raises(Exception, match="cycle"):
        scad.add_component_rassembly(
            assembly, child, component_id="child_instance", placement=placement
        )


def test_product_graph_model_json_and_replay_roundtrip():
    with scad.GraphSession() as session:
        body = scad.make_box_rsolid(2.0, 3.0, 1.0)
        material = scad.make_material_rmaterial(
            "steel_8_8",
            density=7.85e-6,
            density_unit="kg/mm^3",
        )
        part = scad.make_part_rpart("plate", body)
        part = scad.assign_material_rpart(part, material)
        assembly = scad.make_assembly_rassembly("fixture")
        assembly = scad.add_component_rassembly(
            assembly,
            part,
            component_id="plate_1",
            placement=scad.identity_placement_rplacement(),
        )
        compound = scad.make_compound_from_assembly_rcompound(assembly)

    payload = json.loads(scad.export_model_json(session))
    ops = [node["op"] for node in payload["graph"]["nodes"]]

    assert "make_material_rmaterial" in ops
    assert "make_part_rpart" in ops
    assert "make_assign_material_rpart" in ops
    assert "make_assembly_rassembly" in ops
    assert "make_add_component_rassembly" in ops
    assert "make_compound_from_assembly_rcompound" in ops
    assert any(
        item["entity_type"] == "Part" and item["entity_id"] == "plate"
        for item in payload["semantic_entity_registry"]
    )

    replayed = scad.replay_model_json(json.dumps(payload))
    assert len(replayed) == 1
    assert isinstance(replayed[0], scad.Compound)
    assert math.isclose(replayed[0].get_volume(), compound.get_volume(), rel_tol=1e-7)


def test_graph_session_rejects_duplicate_product_ids():
    with pytest.raises(Exception, match="duplicate part"):
        with scad.GraphSession():
            scad.make_part_rpart("same_part", scad.make_box_rsolid(1, 1, 1))
            scad.make_part_rpart("same_part", scad.make_box_rsolid(1, 1, 1))
