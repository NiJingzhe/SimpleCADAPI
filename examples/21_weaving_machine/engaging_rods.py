"""A61 three-level loop-transfer rods and serial X/Z slide geometry."""

from __future__ import annotations

import simplecadapi as scad

from .common import apply_tags, make_part
from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_cylinder_part,
    make_static_assembly,
)


def _make_capture_rod(
    *,
    part_id: str,
    name: str,
    materials: dict[str, scad.Material],
    reverse: bool,
) -> scad.Part:
    beam = scad.make_box_rsolid(
        width=28.0,
        height=340.0,
        depth=90.0,
        bottom_face_center=(0.0, 0.0, -45.0),
    )
    fingers = tuple(
        scad.make_box_rsolid(
            width=62.0,
            height=340.0,
            depth=12.0,
            bottom_face_center=(
                ((-1.0 if reverse else 1.0) * 17.0),
                0.0,
                z_value - 6.0,
            ),
        )
        for z_value in (-24.0, 0.0, 24.0)
    )
    body = scad.union_rsolid(beam, fingers, glue=False)
    grooves = tuple(
        scad.make_cylinder_rsolid(
            radius=5.0,
            height=342.0,
            bottom_face_center=(
                ((-1.0 if reverse else 1.0) * 40.0),
                -171.0,
                z_value,
            ),
            axis=(0.0, 1.0, 0.0),
        )
        for z_value in (-24.0, 0.0, 24.0)
    )
    body = scad.cut_rsolid(body, grooves, skip_non_intersecting=False)
    body = apply_tags(
        shape=body,
        tags=("role.engaging_rod", "role.three_channel_capture", "role.yarn_contact"),
    )
    return make_part(
        part_id=part_id,
        name=name,
        body=body,
        material=materials["stainless"],
        connectors=(),
    )


def make_engaging_rods(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    rod_1 = _make_capture_rod(
        part_id="j1_engaging_rod",
        name="Engaging rod 1 with three retained-yarn grooves",
        materials=materials,
        reverse=False,
    )
    rod_2 = _make_capture_rod(
        part_id="j2_engaging_rod",
        name="Engaging rod 2 with three return-facing loop grooves",
        materials=materials,
        reverse=True,
    )
    x_slide = make_box_part(
        part_id="j2_x_slide",
        name="Engaging rod 2 serial X slide",
        size=(260.0, 60.0, 44.0),
        material=materials["structural_steel"],
        tags=("role.engaging_rod", "role.x_slide"),
    )
    z_slide = make_box_part(
        part_id="j_z_slide",
        name="Engaging rod Z slide",
        size=(42.0, 54.0, 210.0),
        material=materials["machined_aluminum"],
        tags=("role.engaging_rod", "role.z_slide"),
    )
    motor = make_cylinder_part(
        part_id="m4_m6_drive_envelope",
        name="M4-M6 engaging-rod servo/screw envelope",
        radius=38.0,
        length=90.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.engaging_rod", "role.motor_envelope"),
    )
    support_post = make_box_part(
        part_id="j_support_gantry_post",
        name="A61 engaging-rod support gantry post",
        size=(60.0, 60.0, 700.0),
        material=materials["structural_steel"],
        tags=("role.engaging_rod", "role.structural_support"),
    )
    support_tie = make_box_part(
        part_id="j_support_gantry_tie",
        name="A61 engaging-rod support gantry tie",
        size=(330.0, 60.0, 50.0),
        material=materials["structural_steel"],
        tags=("role.engaging_rod", "role.reaction_frame"),
    )
    rod_clamp = make_box_part(
        part_id="j_rod_slide_clamp",
        name="A61 engaging-rod to slide clamp",
        size=(70.0, 42.0, 90.0),
        material=materials["machined_aluminum"],
        tags=("role.engaging_rod", "role.rod_clamp"),
    )
    motor_shelf = make_box_part(
        part_id="j_drive_shelf",
        name="A61 engaging-rod drive mounting shelf",
        size=(120.0, 100.0, 18.0),
        material=materials["structural_steel"],
        tags=("role.engaging_rod", "role.motor_mount"),
    )
    components = [
        ComponentSpec("rod_1", rod_1, (-2.0, 0.0, -11.0), rod_1.name),
        ComponentSpec("rod_1_z_slide", z_slide, (-45.0, -200.0, -105.0), z_slide.name),
        ComponentSpec("rod_1_clamp", rod_clamp, (-15.0, -170.0, -45.0), rod_clamp.name),
        ComponentSpec("rod_1_drive", motor, (-90.0, -200.0, 115.0), "M4 rod-1 Z drive"),
        ComponentSpec("rod_2", rod_2, (-205.0, 0.0, -11.0), rod_2.name),
        ComponentSpec("rod_2_x_slide", x_slide, (-130.0, -205.0, -22.0), x_slide.name),
        ComponentSpec("rod_2_z_slide", z_slide, (-260.0, -205.0, -105.0), z_slide.name),
        ComponentSpec(
            "rod_2_clamp", rod_clamp, (-235.0, -170.0, -45.0), rod_clamp.name
        ),
        ComponentSpec(
            "rod_2_z_drive", motor, (-305.0, -205.0, 115.0), "M5 rod-2 Z drive"
        ),
        ComponentSpec(
            "rod_2_x_drive", motor, (-345.0, -205.0, -22.0), "M6 rod-2 X drive"
        ),
        ComponentSpec(
            "rear_support_post",
            support_post,
            (-45.0, -230.0, parameters.base_datum_z.value + 40.0),
            support_post.name,
        ),
        ComponentSpec(
            "front_support_post",
            support_post,
            (-260.0, -230.0, parameters.base_datum_z.value + 40.0),
            support_post.name,
        ),
        ComponentSpec(
            "support_tie", support_tie, (-150.0, -230.0, 140.0), support_tie.name
        ),
        ComponentSpec(
            "rod_1_motor_shelf", motor_shelf, (-90.0, -230.0, 75.0), motor_shelf.name
        ),
        ComponentSpec(
            "rod_2_motor_shelf", motor_shelf, (-305.0, -230.0, 75.0), motor_shelf.name
        ),
    ]
    assembly = make_static_assembly(
        assembly_id="a61_engaging_rods",
        name="A61 engaging rods 1/2 with three-channel X/Z transfer stages",
        components=components,
    )
    print("a61_engaging_rods: capture_levels=3 rod2_serial_axes=X,Z")
    return assembly
