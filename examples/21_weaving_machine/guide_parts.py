"""D0 guide-block cartridge and replaceable wear-rail geometry."""

from __future__ import annotations

import simplecadapi as scad

from .common import (
    apply_tags,
    connector_ref,
    ground_assembly,
    make_connector,
    make_part,
)
from .parameters import MachineParameters


Y_AXIS_X = (1.0, 0.0, 0.0)
Y_AXIS_Y = (0.0, 0.0, -1.0)
X_AXIS_X = (0.0, 1.0, 0.0)
X_AXIS_Y = (0.0, 0.0, 1.0)


def make_guide_block_body_part(
    *,
    parameters: MachineParameters,
    material: scad.Material,
) -> scad.Part:
    row_width = parameters.guide_block_width.value
    height = parameters.guide_block_height.value
    machine_depth = parameters.guide_block_depth.value
    eye_radius = parameters.guide_eye_diameter.value / 2.0
    eye_outer_radius = eye_radius + 1.0

    core = scad.make_box_rsolid(
        width=machine_depth,
        height=row_width,
        depth=height - 4.0,
        bottom_face_center=(0.0, 0.0, 2.0),
    )
    wear_shoes = [
        scad.make_box_rsolid(
            width=machine_depth + 4.0,
            height=row_width,
            depth=4.0,
            bottom_face_center=(0.0, 0.0, z_value),
        )
        for z_value in (0.0, height - 4.0)
    ]
    anti_rotation_shoulders = [
        scad.make_box_rsolid(
            width=4.0,
            height=row_width,
            depth=height - 8.0,
            bottom_face_center=(side * (machine_depth / 2.0 + 1.0), 0.0, 4.0),
        )
        for side in (-1.0, 1.0)
    ]
    body = scad.union_rsolid(core, wear_shoes, anti_rotation_shoulders, glue=False)
    convex_boss = scad.make_cylinder_rsolid(
        radius=3.0,
        height=1.2,
        bottom_face_center=(0.0, row_width / 2.0 - 0.4, height / 2.0),
        axis=(0.0, 1.0, 0.0),
    )
    body = scad.union_rsolid(body, convex_boss, glue=False)
    eye_bore = scad.make_cylinder_rsolid(
        radius=eye_outer_radius + 0.05,
        height=machine_depth + 6.0,
        bottom_face_center=(-machine_depth / 2.0 - 3.0, 0.0, height / 2.0),
        axis=(1.0, 0.0, 0.0),
    )
    concave_contact = scad.make_cylinder_rsolid(
        radius=3.1,
        height=1.4,
        bottom_face_center=(0.0, -row_width / 2.0 - 0.7, height / 2.0),
        axis=(0.0, 1.0, 0.0),
    )
    lock_notch = scad.make_box_rsolid(
        width=8.0,
        height=4.0,
        depth=3.0,
        bottom_face_center=(0.0, 0.0, -0.5),
    )
    body = scad.cut_rsolid(
        body,
        eye_bore,
        concave_contact,
        lock_notch,
        skip_non_intersecting=False,
    )
    body = apply_tags(
        shape=body,
        tags=(
            "role.bias_guide_block",
            "role.sliding_member",
            "role.yarn_contact_carrier",
        ),
    )
    return make_part(
        part_id="g_block_body_d0",
        name="D0 bias guide block body",
        body=body,
        material=material,
        connectors=(
            make_connector(
                connector_id="slide_axis",
                origin=(0.0, 0.0, 0.0),
                x_axis=Y_AXIS_X,
                y_axis=Y_AXIS_Y,
                name="Guide row Y axis",
            ),
            make_connector(
                connector_id="eye_axis",
                origin=(0.0, 0.0, height / 2.0),
                x_axis=X_AXIS_X,
                y_axis=X_AXIS_Y,
                name="Ceramic eye press-fit axis",
            ),
        ),
    )


def make_ceramic_eye_part(
    *,
    parameters: MachineParameters,
    material: scad.Material,
) -> scad.Part:
    machine_depth = parameters.guide_block_depth.value
    height = parameters.guide_block_height.value
    inner_radius = parameters.guide_eye_diameter.value / 2.0
    outer_radius = inner_radius + 1.0
    outer = scad.make_cylinder_rsolid(
        radius=outer_radius,
        height=machine_depth + 0.8,
        bottom_face_center=(-machine_depth / 2.0 - 0.4, 0.0, height / 2.0),
        axis=(1.0, 0.0, 0.0),
    )
    bore = scad.make_cylinder_rsolid(
        radius=inner_radius,
        height=machine_depth + 2.0,
        bottom_face_center=(-machine_depth / 2.0 - 1.0, 0.0, height / 2.0),
        axis=(1.0, 0.0, 0.0),
    )
    eye = scad.cut_rsolid(outer, bore, skip_non_intersecting=False)
    eye = apply_tags(
        shape=eye,
        tags=("role.ceramic_eye", "role.yarn_contact", "role.replaceable_insert"),
    )
    return make_part(
        part_id="g_block_ceramic_eye_d0",
        name="D0 alumina guide eye",
        body=eye,
        material=material,
        connectors=(
            make_connector(
                connector_id="eye_mount",
                origin=(0.0, 0.0, height / 2.0),
                x_axis=X_AXIS_X,
                y_axis=X_AXIS_Y,
                name="Eye press-fit axis",
            ),
        ),
    )


def make_guide_cartridge_assembly(
    *,
    parameters: MachineParameters,
    body_material: scad.Material,
    ceramic_material: scad.Material,
) -> scad.Assembly:
    body = make_guide_block_body_part(parameters=parameters, material=body_material)
    eye = make_ceramic_eye_part(parameters=parameters, material=ceramic_material)
    assembly = scad.make_assembly_rassembly(
        assembly_id="g_block_cartridge_d0",
        name="D0 bias guide cartridge",
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=body,
        component_id="block_body",
        placement=scad.identity_placement_rplacement(),
        name="Guide block body",
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=eye,
        component_id="ceramic_eye",
        placement=scad.identity_placement_rplacement(),
        name="Pressed ceramic eye",
    )
    assembly = scad.ground_component_rassembly(
        assembly=assembly, component_id="block_body"
    )
    assembly = scad.add_fixed_constraint_rassembly(
        assembly=assembly,
        constraint_id="fix_eye_in_block",
        connector_a=connector_ref(component_id="block_body", connector_id="eye_axis"),
        connector_b=connector_ref(component_id="ceramic_eye", connector_id="eye_mount"),
        name="Ceramic eye press-fit datum",
    )
    assembly = scad.forward_connector_rassembly(
        assembly=assembly,
        connector_id="slide_axis",
        source_component_id="block_body",
        source_connector_id="slide_axis",
        name="Public guide row Y axis",
    )
    assembly = scad.solve_assembly_constraints_rassembly(assembly=assembly, strict=True)
    ground_assembly(label="g_block_cartridge_d0", assembly=assembly)
    return assembly


def make_wear_rail_part(
    *,
    parameters: MachineParameters,
    material: scad.Material,
) -> scad.Part:
    length = parameters.guide_rail_length.value
    rail_width = parameters.guide_block_depth.value + 8.0
    rail_depth = 2.0
    rail = scad.make_box_rsolid(
        width=rail_width,
        height=length,
        depth=rail_depth,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    holes = [
        scad.make_cylinder_rsolid(
            radius=1.8,
            height=rail_depth + 2.0,
            bottom_face_center=(0.0, side * (length / 2.0 - 7.0), -1.0),
            axis=(0.0, 0.0, 1.0),
        )
        for side in (-1.0, 1.0)
    ]
    rail = scad.cut_rsolid(rail, holes, skip_non_intersecting=False)
    rail = apply_tags(
        shape=rail,
        tags=(
            "role.replaceable_wear_rail",
            "role.guide_row_support",
            "role.mounting_holes",
        ),
    )
    return make_part(
        part_id="g_03_wear_rail_d0",
        name="D0 replaceable guide wear rail",
        body=rail,
        material=material,
        connectors=(
            make_connector(
                connector_id="slide_axis",
                origin=(0.0, 0.0, rail_depth),
                x_axis=Y_AXIS_X,
                y_axis=Y_AXIS_Y,
                name="Guide row Y axis",
            ),
        ),
    )
