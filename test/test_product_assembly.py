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


def test_product_and_constraint_public_apis_do_not_use_bare_star_parameters():
    public_apis = [
        scad.make_material_rmaterial,
        scad.make_placement_rplacement,
        scad.make_part_rpart,
        scad.make_assembly_rassembly,
        scad.add_component_rassembly,
        scad.make_face_connector_rconnector,
        scad.make_edge_connector_rconnector,
        scad.make_vertex_connector_rconnector,
        scad.make_placement_connector_rconnector,
        scad.add_connector_rpart,
        scad.add_connector_rassembly,
        scad.forward_connector_rassembly,
        scad.make_connector_ref_rconnectorref,
        scad.make_scalar_limit_rscalarlimit,
        scad.ground_component_rassembly,
        scad.unground_component_rassembly,
        scad.add_fixed_constraint_rassembly,
        scad.add_revolute_constraint_rassembly,
        scad.add_prismatic_constraint_rassembly,
        scad.add_gear_constraint_rassembly,
        scad.add_belt_constraint_rassembly,
        scad.add_rack_pinion_constraint_rassembly,
        scad.solve_assembly_constraints_rassembly,
    ]

    for api in public_apis:
        signature = inspect.signature(api)
        assert all(
            parameter.kind is not inspect.Parameter.KEYWORD_ONLY
            for parameter in signature.parameters.values()
        )


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


def _part_with_face_connector(part_id):
    body = scad.make_box_rsolid(1.0, 1.0, 1.0)
    part = scad.make_part_rpart(part_id, body)
    top_face = ql.faces().resolve(body)[-1]
    connector = scad.make_face_connector_rconnector("axis", top_face)
    return scad.add_connector_rpart(part, connector)


def _part_with_placement_connector(part_id, connector_origin=(0.0, 0.0, 0.0)):
    body = scad.make_box_rsolid(1.0, 1.0, 1.0)
    part = scad.make_part_rpart(part_id, body)
    placement = scad.make_placement_rplacement(origin=connector_origin)
    connector = scad.make_placement_connector_rconnector("axis", placement)
    return scad.add_connector_rpart(part, connector)


def test_placement_connector_can_drive_fixed_constraints():
    part = _part_with_placement_connector("placement_constraint_part")
    assembly = scad.make_assembly_rassembly("placement_constraint_asm")
    assembly = scad.add_component_rassembly(
        assembly,
        part,
        component_id="base",
        placement=scad.make_placement_rplacement(origin=(1.0, 2.0, 3.0)),
    )
    assembly = scad.add_component_rassembly(
        assembly,
        part,
        component_id="follower",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(assembly, "base")
    assembly = scad.add_fixed_constraint_rassembly(
        assembly,
        "fixed",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("follower", "axis"),
    )

    solved = scad.solve_assembly_constraints_rassembly(assembly)

    assert solved.get_component("follower").placement.origin == (1.0, 2.0, 3.0)
    assert scad.measure_constraint_residual_rconstraintresidual(solved, "fixed").within_tolerance


def test_forwarded_connector_resolves_and_solves_at_parent_level():
    inner_part = _part_with_placement_connector("forwarded_inner_part", (2.0, 0.0, 0.0))
    base_part = _part_with_placement_connector("forwarded_base_part")
    child = scad.make_assembly_rassembly("forwarded_child")
    child = scad.add_component_rassembly(
        child,
        inner_part,
        component_id="inner",
        placement=scad.make_placement_rplacement(origin=(5.0, 0.0, 0.0)),
    )
    child = scad.forward_connector_rassembly(
        child,
        connector_id="public_axis",
        source_component_id="inner",
        source_connector_id="axis",
    )

    assert child.connector_ids() == ("public_axis",)
    assert child.get_connector("public_axis").placement.origin == (7.0, 0.0, 0.0)

    root = scad.make_assembly_rassembly("forwarded_root")
    root = scad.add_component_rassembly(
        root,
        base_part,
        component_id="base",
        placement=scad.make_placement_rplacement(origin=(10.0, 0.0, 0.0)),
    )
    root = scad.add_component_rassembly(
        root,
        child,
        component_id="child",
        placement=scad.identity_placement_rplacement(),
    )
    root = scad.ground_component_rassembly(root, "base")
    root = scad.add_fixed_constraint_rassembly(
        root,
        "bind_forwarded_axis",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("child", "public_axis"),
    )
    solved = scad.solve_assembly_constraints_rassembly(root)

    assert solved.get_component("child").placement.origin == (3.0, 0.0, 0.0)
    assert scad.measure_constraint_residual_rconstraintresidual(
        solved,
        "bind_forwarded_axis",
    ).within_tolerance


def test_forwarded_connector_validation_reports_missing_sources():
    assembly = scad.make_assembly_rassembly("bad_forwarded_connector_asm")

    with pytest.raises(Exception, match="missing component"):
        scad.forward_connector_rassembly(
            assembly,
            connector_id="public_axis",
            source_component_id="inner",
            source_connector_id="axis",
        )


def test_fixed_revolute_and_prismatic_constraints_solve_component_placements():
    part = _part_with_face_connector("constraint_part")

    fixed_assembly = scad.make_assembly_rassembly("fixed_asm")
    fixed_assembly = scad.add_component_rassembly(
        fixed_assembly,
        part,
        component_id="base",
        placement=scad.make_placement_rplacement((1.0, 2.0, 3.0)),
    )
    fixed_assembly = scad.add_component_rassembly(
        fixed_assembly,
        part,
        component_id="follower",
        placement=scad.identity_placement_rplacement(),
    )
    fixed_assembly = scad.ground_component_rassembly(fixed_assembly, "base")
    fixed_assembly = scad.add_fixed_constraint_rassembly(
        fixed_assembly,
        "fixed",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("follower", "axis"),
    )
    fixed_solved = scad.solve_assembly_constraints_rassembly(fixed_assembly)
    assert fixed_solved.get_component("follower").placement.origin == (1.0, 2.0, 3.0)
    assert scad.measure_constraint_residual_rconstraintresidual(
        fixed_solved, "fixed"
    ).within_tolerance

    revolute_assembly = scad.make_assembly_rassembly("revolute_asm")
    revolute_assembly = scad.add_component_rassembly(
        revolute_assembly,
        part,
        component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    revolute_assembly = scad.add_component_rassembly(
        revolute_assembly,
        part,
        component_id="arm",
        placement=scad.identity_placement_rplacement(),
    )
    revolute_assembly = scad.ground_component_rassembly(revolute_assembly, "base")
    revolute_assembly = scad.add_revolute_constraint_rassembly(
        revolute_assembly,
        "hinge",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("arm", "axis"),
        drive_angle_degrees=90.0,
    )
    revolute_solved = scad.solve_assembly_constraints_rassembly(revolute_assembly)
    arm_placement = revolute_solved.get_component("arm").placement
    assert math.isclose(arm_placement.origin[0], 0.0, abs_tol=1e-12)
    assert math.isclose(arm_placement.origin[1], 0.0, abs_tol=1e-12)
    assert math.isclose(arm_placement.origin[2], 0.0, abs_tol=1e-12)
    assert math.isclose(revolute_solved.get_component("arm").placement.x_axis[0], 0.0, abs_tol=1e-10)
    assert math.isclose(revolute_solved.get_component("arm").placement.x_axis[1], 1.0, abs_tol=1e-10)

    prismatic_assembly = scad.make_assembly_rassembly("prismatic_asm")
    prismatic_assembly = scad.add_component_rassembly(
        prismatic_assembly,
        part,
        component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    prismatic_assembly = scad.add_component_rassembly(
        prismatic_assembly,
        part,
        component_id="slider",
        placement=scad.identity_placement_rplacement(),
    )
    prismatic_assembly = scad.ground_component_rassembly(prismatic_assembly, "base")
    prismatic_assembly = scad.add_prismatic_constraint_rassembly(
        prismatic_assembly,
        "slide",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("slider", "axis"),
        drive_distance=5.0,
    )
    prismatic_solved = scad.solve_assembly_constraints_rassembly(prismatic_assembly)
    assert prismatic_solved.get_component("slider").placement.origin == (0.0, 0.0, 5.0)
    report = scad.inspect_assembly_constraints_rconstraintreport(prismatic_solved)
    assert report.solved


def test_constraint_validation_rejects_missing_refs_and_limit_violations():
    part = _part_with_face_connector("limited_part")
    assembly = scad.make_assembly_rassembly("limited_asm")
    assembly = scad.add_component_rassembly(
        assembly,
        part,
        component_id="base",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly,
        part,
        component_id="slider",
        placement=scad.identity_placement_rplacement(),
    )
    connector_a = scad.make_connector_ref_rconnectorref("base", "axis")
    connector_b = scad.make_connector_ref_rconnectorref("slider", "axis")

    assembly_with_limit = scad.ground_component_rassembly(assembly, "base")
    assembly_with_limit = scad.add_prismatic_constraint_rassembly(
        assembly_with_limit, "slide",
        connector_a,
        connector_b,
        drive_distance=10.0,
        distance_limit=scad.make_scalar_limit_rscalarlimit(0.0, 5.0),
    )
    solved = scad.solve_assembly_constraints_rassembly(assembly_with_limit)
    assert solved.get_component("slider").placement.origin == (0.0, 0.0, 5.0)

    with pytest.raises(Exception, match="connector"):
        scad.add_fixed_constraint_rassembly(
            assembly,
            "missing",
            connector_a,
            scad.make_connector_ref_rconnectorref("slider", "missing_axis"),
        )

    with pytest.raises(Exception, match="grounded"):
        ungrounded = scad.make_assembly_rassembly("ungrounded_asm")
        ungrounded = scad.add_component_rassembly(
            ungrounded, part, component_id="base", placement=scad.identity_placement_rplacement(),
        )
        ungrounded = scad.add_component_rassembly(
            ungrounded, part, component_id="slider", placement=scad.identity_placement_rplacement(),
        )
        ungrounded = scad.add_prismatic_constraint_rassembly(
            ungrounded, "slide_ungrounded",
            scad.make_connector_ref_rconnectorref("base", "axis"),
            scad.make_connector_ref_rconnectorref("slider", "axis"),
            drive_distance=1.0,
        )
        scad.solve_assembly_constraints_rassembly(ungrounded)


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


def test_constraint_graph_model_json_and_replay_roundtrip():
    with scad.GraphSession() as session:
        part = _part_with_face_connector("replay_constraint_part")
        assembly = scad.make_assembly_rassembly("replay_constraint_asm")
        assembly = scad.add_component_rassembly(
            assembly,
            part,
            component_id="base",
            placement=scad.identity_placement_rplacement(),
        )
        assembly = scad.add_component_rassembly(
            assembly,
            part,
            component_id="slider",
            placement=scad.identity_placement_rplacement(),
        )
        assembly = scad.ground_component_rassembly(assembly, "base")
        connector_a = scad.make_connector_ref_rconnectorref("base", "axis")
        connector_b = scad.make_connector_ref_rconnectorref("slider", "axis")
        limit = scad.make_scalar_limit_rscalarlimit(0.0, 10.0)
        assembly = scad.add_prismatic_constraint_rassembly(
            assembly,
            "slide",
            connector_a,
            connector_b,
            drive_distance=4.0,
            distance_limit=limit,
        )
        solved = scad.solve_assembly_constraints_rassembly(assembly)

    payload = json.loads(scad.export_model_json(session))
    ops = [node["op"] for node in payload["graph"]["nodes"]]
    assert "make_face_connector_rconnector" in ops
    assert "make_add_connector_rpart" in ops
    assert "make_connector_ref_rconnectorref" in ops
    assert "make_scalar_limit_rscalarlimit" in ops
    assert "make_ground_component_rassembly" in ops
    assert "make_prismatic_constraint_rassembly" in ops
    assert "make_solve_assembly_constraints_rassembly" in ops

    replayed = scad.replay_model_json(json.dumps(payload))
    assert len(replayed) == 1
    assert isinstance(replayed[0], scad.Assembly)
    assert replayed[0].get_component("slider").placement.origin == (0.0, 0.0, 4.0)
    assert replayed[0].constraints[0].distance_limit.lower_value == 0.0
    assert solved.get_component("slider").placement.origin == (0.0, 0.0, 4.0)


def test_boolean_named_face_connector_resolves_after_replay():
    with scad.GraphSession() as session:
        flange = scad.extrude_rsolid(
            scad.make_circle_rface(
                center=(0.0, 0.0, 0.0),
                radius=2.0,
                normal=(1.0, 0.0, 0.0),
            ),
            direction=(1.0, 0.0, 0.0),
            distance=2.0,
            end_face_tag="cap.face.end",
        )
        body = scad.make_cylinder_rsolid(
            radius=1.5,
            height=4.0,
            bottom_face_center=(-1.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        bridge = scad.make_box_rsolid(
            width=1.0,
            height=1.0,
            depth=1.0,
            bottom_face_center=(-0.5, -0.5, -0.5),
        )
        fused = scad.union_rsolid(body, flange, bridge, glue=False)
        result = scad.cut_rsolid(
            fused,
            scad.make_cylinder_rsolid(
                radius=0.25,
                height=4.0,
                bottom_face_center=(-1.0, 1.0, 0.0),
                axis=(1.0, 0.0, 0.0),
            ),
        )
        named_face = (
            ql.faces()
            .where(ql.tag("cap.face.end"))
            .exactly(1)
            .resolve(result)[0]
        )
        connector = scad.make_face_connector_rconnector("mount", named_face)
        part = scad.add_connector_rpart(
            scad.make_part_rpart("boolean_named_part", result),
            connector,
        )
        session.capture_result(value=part)

    replayed = scad.replay_model_json(scad.export_model_json(session))[0]
    assert isinstance(replayed, scad.Part)
    replayed_face = (
        ql.faces()
        .where(ql.tag("cap.face.end"))
        .exactly(1)
        .resolve(replayed.body)[0]
    )
    assert replayed.get_connector("mount").placement.origin == pytest.approx(
        tuple(replayed_face.get_center())
    )

    package = scad.compile_scene(
        scene_id="boolean-named-connector",
        roots=(scad.SceneRoot(root_id="main", value=replayed),),
    )
    snapshot = package.manifest["connectors"][0]
    asset = next(
        item
        for item in package.manifest["entity_assets"]
        if item["entity_asset_id"] == snapshot["target"]["entity_asset_id"]
    )
    entity_document = json.loads(package.blobs[asset["uri"]])
    target = next(
        item
        for item in entity_document["entities"]
        if item["entity_id"] == snapshot["target"]["entity_id"]
    )
    assert "cap.face.end" in target["evaluated_tags"]


def test_nested_constraint_graph_replay_preserves_child_assembly_constraints():
    with scad.GraphSession() as session:
        part = _part_with_placement_connector("nested_replay_part")
        child = scad.make_assembly_rassembly(assembly_id="nested_replay_child")
        child = scad.add_component_rassembly(
            assembly=child,
            item=part,
            component_id="base",
            placement=scad.identity_placement_rplacement(),
        )
        child = scad.add_component_rassembly(
            assembly=child,
            item=part,
            component_id="arm",
            placement=scad.identity_placement_rplacement(),
        )
        child = scad.ground_component_rassembly(
            assembly=child,
            component_id="base",
        )
        child = scad.add_revolute_constraint_rassembly(
            assembly=child,
            constraint_id="pivot",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="base",
                connector_id="axis",
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="arm",
                connector_id="axis",
            ),
            drive_angle_degrees=30.0,
        )
        child = scad.solve_assembly_constraints_rassembly(assembly=child)

        root = scad.make_assembly_rassembly(assembly_id="nested_replay_root")
        root = scad.add_component_rassembly(
            assembly=root,
            item=child,
            component_id="child",
            placement=scad.make_placement_rplacement(origin=(10.0, 20.0, 30.0)),
        )

    payload = json.loads(scad.export_model_json(session))
    ops = [node["op"] for node in payload["graph"]["nodes"]]
    assert ops.count("make_revolute_constraint_rassembly") == 1
    assert ops.count("make_solve_assembly_constraints_rassembly") == 1
    assert ops.count("make_add_component_rassembly") == 3

    replayed = scad.replay_model_json(json.dumps(payload))
    assert len(replayed) == 1
    replayed_root = replayed[0]
    assert isinstance(replayed_root, scad.Assembly)
    replayed_child = replayed_root.get_component("child").item
    assert isinstance(replayed_child, scad.Assembly)
    assert replayed_child.assembly_id == "nested_replay_child"
    assert replayed_child.component_ids() == ("base", "arm")
    assert replayed_child.constraint_ids() == ("pivot",)
    assert replayed_child.grounded_component_ids == ("base",)
    assert replayed_child.get_constraint("pivot").drive_angle_degrees == 30.0
    assert replayed_child.get_component("arm").placement.x_axis == (
        math.cos(math.radians(30.0)),
        math.sin(math.radians(30.0)),
        0.0,
    )
    assert replayed_root.get_component("child").placement.origin == (10.0, 20.0, 30.0)


def test_graph_session_rejects_duplicate_product_ids():
    with pytest.raises(Exception, match="duplicate part"):
        with scad.GraphSession():
            scad.make_part_rpart("same_part", scad.make_box_rsolid(1, 1, 1))
            scad.make_part_rpart("same_part", scad.make_box_rsolid(1, 1, 1))


def test_limit_aware_prismatic_tree_clamps_scalar_to_bounds():
    part = _part_with_face_connector("clamp_part")
    assembly = scad.make_assembly_rassembly("clamp_asm")
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="base", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="slider", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(assembly, "base")
    assembly = scad.add_prismatic_constraint_rassembly(
        assembly, "slide",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("slider", "axis"),
        drive_distance=100.0,
        distance_limit=scad.make_scalar_limit_rscalarlimit(0.0, 5.0),
    )
    solved = scad.solve_assembly_constraints_rassembly(assembly)
    assert solved.get_component("slider").placement.origin == (0.0, 0.0, 5.0)
    residual = scad.measure_constraint_residual_rconstraintresidual(solved, "slide")
    assert residual.within_tolerance


def test_limit_aware_prismatic_tree_uses_drive_when_within_bounds():
    part = _part_with_face_connector("inrange_part")
    assembly = scad.make_assembly_rassembly("inrange_asm")
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="base", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="slider", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(assembly, "base")
    assembly = scad.add_prismatic_constraint_rassembly(
        assembly, "slide",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("slider", "axis"),
        drive_distance=3.0,
        distance_limit=scad.make_scalar_limit_rscalarlimit(0.0, 10.0),
    )
    solved = scad.solve_assembly_constraints_rassembly(assembly)
    assert solved.get_component("slider").placement.origin == (0.0, 0.0, 3.0)


def test_limit_aware_revolute_tree_clamps_angle_to_bounds():
    part = _part_with_face_connector("rev_clamp_part")
    assembly = scad.make_assembly_rassembly("rev_clamp_asm")
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="base", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="arm", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(assembly, "base")
    assembly = scad.add_revolute_constraint_rassembly(
        assembly, "hinge",
        scad.make_connector_ref_rconnectorref("base", "axis"),
        scad.make_connector_ref_rconnectorref("arm", "axis"),
        drive_angle_degrees=999.0,
        angle_limit=scad.make_scalar_limit_rscalarlimit(0.0, 45.0),
    )
    solved = scad.solve_assembly_constraints_rassembly(assembly)
    arm_x = solved.get_component("arm").placement.x_axis
    expected_cos = math.cos(math.radians(45.0))
    expected_sin = math.sin(math.radians(45.0))
    assert math.isclose(arm_x[0], expected_cos, abs_tol=1e-10)
    assert math.isclose(arm_x[1], expected_sin, abs_tol=1e-10)


def test_limit_aware_revolute_loop_finds_optimal_angle():
    part_a = _part_with_face_connector("loop_a")
    part_b = _part_with_face_connector("loop_b")
    assembly = scad.make_assembly_rassembly("rev_loop")
    assembly = scad.add_component_rassembly(
        assembly, part_a, component_id="link1",
        placement=scad.make_placement_rplacement(origin=(5.0, 0.0, 0.0)),
    )
    assembly = scad.add_component_rassembly(
        assembly, part_b, component_id="link2",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(assembly, "link1")
    connector_a = scad.make_connector_ref_rconnectorref("link1", "axis")
    connector_b = scad.make_connector_ref_rconnectorref("link2", "axis")
    assembly = scad.add_revolute_constraint_rassembly(
        assembly, "hinge",
        connector_a, connector_b,
        angle_limit=scad.make_scalar_limit_rscalarlimit(0.0, 90.0),
    )
    solved = scad.solve_assembly_constraints_rassembly(assembly, strict=False)
    residual = scad.measure_constraint_residual_rconstraintresidual(solved, "hinge")
    assert residual.within_tolerance


def _signed_z_angle_degrees(placement):
    return math.degrees(math.atan2(placement.x_axis[1], placement.x_axis[0]))


def test_gear_and_belt_constraints_couple_revolute_support_joints():
    part = _part_with_face_connector("coupled_rotor_part")
    base_ref = scad.make_connector_ref_rconnectorref("base", "axis")
    gear_a_ref = scad.make_connector_ref_rconnectorref("gear_a", "axis")
    gear_b_ref = scad.make_connector_ref_rconnectorref("gear_b", "axis")

    gear_assembly = scad.make_assembly_rassembly("gear_coupler_asm")
    for component_id in ("base", "gear_a", "gear_b"):
        gear_assembly = scad.add_component_rassembly(
            gear_assembly,
            part,
            component_id=component_id,
            placement=scad.identity_placement_rplacement(),
        )
    gear_assembly = scad.ground_component_rassembly(gear_assembly, "base")
    gear_assembly = scad.add_revolute_constraint_rassembly(
        gear_assembly, "drive_a", base_ref, gear_a_ref, drive_angle_degrees=90.0,
    )
    gear_assembly = scad.add_revolute_constraint_rassembly(
        gear_assembly, "free_b", base_ref, gear_b_ref,
    )
    gear_assembly = scad.add_gear_constraint_rassembly(
        gear_assembly,
        "mesh",
        gear_a_ref,
        gear_b_ref,
        pitch_radius_a=1.0,
        pitch_radius_b=2.0,
    )
    gear_solved = scad.solve_assembly_constraints_rassembly(gear_assembly)
    assert math.isclose(
        _signed_z_angle_degrees(gear_solved.get_component("gear_b").placement),
        -45.0,
        abs_tol=1e-9,
    )
    assert scad.measure_constraint_residual_rconstraintresidual(
        gear_solved, "mesh"
    ).within_tolerance

    belt_assembly = scad.make_assembly_rassembly("belt_coupler_asm")
    for component_id in ("base", "gear_a", "gear_b"):
        belt_assembly = scad.add_component_rassembly(
            belt_assembly,
            part,
            component_id=component_id,
            placement=scad.identity_placement_rplacement(),
        )
    belt_assembly = scad.ground_component_rassembly(belt_assembly, "base")
    belt_assembly = scad.add_revolute_constraint_rassembly(
        belt_assembly, "drive_a", base_ref, gear_a_ref, drive_angle_degrees=90.0,
    )
    belt_assembly = scad.add_revolute_constraint_rassembly(
        belt_assembly, "free_b", base_ref, gear_b_ref,
    )
    belt_assembly = scad.add_belt_constraint_rassembly(
        belt_assembly,
        "belt",
        gear_a_ref,
        gear_b_ref,
        pulley_radius_a=1.0,
        pulley_radius_b=2.0,
    )
    belt_solved = scad.solve_assembly_constraints_rassembly(belt_assembly)
    assert math.isclose(
        _signed_z_angle_degrees(belt_solved.get_component("gear_b").placement),
        45.0,
        abs_tol=1e-9,
    )
    assert scad.measure_constraint_residual_rconstraintresidual(
        belt_solved, "belt"
    ).within_tolerance


def test_rack_pinion_constraint_couples_prismatic_and_revolute_support_joints():
    part = _part_with_face_connector("rack_pinion_part")
    base_ref = scad.make_connector_ref_rconnectorref("base", "axis")
    rack_ref = scad.make_connector_ref_rconnectorref("rack", "axis")
    pinion_ref = scad.make_connector_ref_rconnectorref("pinion", "axis")
    assembly = scad.make_assembly_rassembly("rack_pinion_asm")
    for component_id in ("base", "rack", "pinion"):
        assembly = scad.add_component_rassembly(
            assembly,
            part,
            component_id=component_id,
            placement=scad.identity_placement_rplacement(),
        )
    assembly = scad.ground_component_rassembly(assembly, "base")
    assembly = scad.add_prismatic_constraint_rassembly(
        assembly, "rack_slide", base_ref, rack_ref,
    )
    assembly = scad.add_revolute_constraint_rassembly(
        assembly, "pinion_axis", base_ref, pinion_ref, drive_angle_degrees=90.0,
    )
    assembly = scad.add_rack_pinion_constraint_rassembly(
        assembly,
        "rack_mesh",
        rack_ref,
        pinion_ref,
        pitch_radius=2.0,
    )

    solved = scad.solve_assembly_constraints_rassembly(assembly)

    assert math.isclose(
        solved.get_component("rack").placement.origin[2],
        -math.pi,
        abs_tol=1e-9,
    )
    assert scad.measure_constraint_residual_rconstraintresidual(
        solved, "rack_mesh"
    ).within_tolerance


def test_coupling_constraints_validate_positive_radii():
    part = _part_with_face_connector("invalid_coupler_part")
    assembly = scad.make_assembly_rassembly("invalid_coupler_asm")
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="a", placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="b", placement=scad.identity_placement_rplacement(),
    )
    ref_a = scad.make_connector_ref_rconnectorref("a", "axis")
    ref_b = scad.make_connector_ref_rconnectorref("b", "axis")

    with pytest.raises(Exception, match="pitch_radius_a"):
        scad.add_gear_constraint_rassembly(
            assembly, "bad_gear", ref_a, ref_b, pitch_radius_a=0.0, pitch_radius_b=1.0,
        )
    with pytest.raises(Exception, match="pulley_radius_b"):
        scad.add_belt_constraint_rassembly(
            assembly, "bad_belt", ref_a, ref_b, pulley_radius_a=1.0, pulley_radius_b=-1.0,
        )
    with pytest.raises(Exception, match="pitch_radius"):
        scad.add_rack_pinion_constraint_rassembly(
            assembly, "bad_rack", ref_a, ref_b, pitch_radius=0.0,
        )


def test_limit_aware_prismatic_loop_finds_optimal_distance():
    part = _part_with_face_connector("ploop_part")
    assembly = scad.make_assembly_rassembly("prism_loop")
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="fixed_part",
        placement=scad.make_placement_rplacement(origin=(0.0, 0.0, 2.0)),
    )
    assembly = scad.add_component_rassembly(
        assembly, part, component_id="movable",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.ground_component_rassembly(assembly, "fixed_part")
    connector_a = scad.make_connector_ref_rconnectorref("fixed_part", "axis")
    connector_b = scad.make_connector_ref_rconnectorref("movable", "axis")
    assembly = scad.add_prismatic_constraint_rassembly(
        assembly, "slide",
        connector_a, connector_b,
        distance_limit=scad.make_scalar_limit_rscalarlimit(-5.0, 5.0),
    )
    solved = scad.solve_assembly_constraints_rassembly(assembly, strict=False)
    residual = scad.measure_constraint_residual_rconstraintresidual(solved, "slide")
    assert residual.within_tolerance
