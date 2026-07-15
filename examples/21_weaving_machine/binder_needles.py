"""A50 opposed binder-needle beams, supply, and M2 drive envelope."""

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


def _make_binder_needle(*, materials: dict[str, scad.Material]) -> scad.Part:
    shaft = scad.make_cylinder_rsolid(
        radius=2.0,
        height=180.0,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
    )
    tip = scad.make_cone_rsolid(
        bottom_radius=2.0,
        top_radius=0.65,
        height=12.0,
        bottom_face_center=(0.0, 0.0, 180.0),
        axis=(0.0, 0.0, 1.0),
    )
    needle = scad.union_rsolid(shaft, tip, glue=False)
    eye = scad.make_cylinder_rsolid(
        radius=0.65,
        height=5.0,
        bottom_face_center=(-2.5, 0.0, 172.0),
        axis=(1.0, 0.0, 0.0),
    )
    needle = scad.cut_rsolid(needle, eye, skip_non_intersecting=False)
    needle = apply_tags(
        shape=needle,
        tags=("role.binder_needle", "role.yarn_contact", "role.replaceable_tool"),
    )
    return make_part(
        part_id="n_03_binder_needle",
        name="N-03 polished binder needle with eye",
        body=needle,
        material=materials["stainless"],
        connectors=(),
    )


def make_binder_system(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    needle = _make_binder_needle(materials=materials)
    beam = make_box_part(
        part_id="n_01_needle_beam",
        name="N-01/N-02 replaceable-slot needle beam",
        size=(70.0, 460.0, 34.0),
        material=materials["machined_aluminum"],
        tags=("role.binder_system", "role.needle_clamp_beam"),
    )
    vertical_rail = make_box_part(
        part_id="n_05_vertical_slide_rail",
        name="N-05/N-06 opposed needle Z-slide rail",
        size=(34.0, 24.0, 560.0),
        material=materials["structural_steel"],
        tags=("role.binder_system", "role.linear_guide"),
    )
    belt = make_box_part(
        part_id="m2_opposed_timing_belt",
        name="M2 opposed double-sided timing-belt envelope",
        size=(18.0, 20.0, 520.0),
        material=materials["belt"],
        tags=("role.binder_system", "role.opposed_drive"),
    )
    motor = make_cylinder_part(
        part_id="m2_servo_envelope",
        name="M2 binder servo envelope",
        radius=48.0,
        length=110.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.binder_system", "role.motor_envelope"),
    )
    support_post = make_box_part(
        part_id="n_05_needle_rail_support",
        name="N-05 needle-slide support post",
        size=(60.0, 60.0, 330.0),
        material=materials["structural_steel"],
        tags=("role.binder_system", "role.structural_support"),
    )
    motor_shelf = make_box_part(
        part_id="n_07_m2_motor_shelf",
        name="N-07 M2 needle-drive mounting shelf",
        size=(140.0, 100.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.binder_system", "role.motor_mount"),
    )
    top_tie = make_box_part(
        part_id="n_05_needle_rail_tie",
        name="N-05 needle-slide top tie beam",
        size=(60.0, 500.0, 40.0),
        material=materials["structural_steel"],
        tags=("role.binder_system", "role.reaction_frame"),
    )
    x_value = parameters.x_needle.value
    components: list[ComponentSpec] = [
        ComponentSpec(
            "upper_beam", beam, (x_value, 0.0, 245.0), "Upper opposed needle beam"
        ),
        ComponentSpec(
            "lower_beam",
            beam,
            (x_value, parameters.guide_pitch.value / 2.0, -279.0),
            "Lower opposed needle beam, half-pitch offset",
        ),
        ComponentSpec(
            "left_slide_rail",
            vertical_rail,
            (x_value - 15.0, -230.0, -280.0),
            vertical_rail.name,
        ),
        ComponentSpec(
            "right_slide_rail",
            vertical_rail,
            (x_value - 15.0, 230.0, -280.0),
            vertical_rail.name,
        ),
        ComponentSpec(
            "opposed_drive_belt", belt, (x_value - 65.0, -255.0, -260.0), belt.name
        ),
        ComponentSpec("m2_motor", motor, (x_value - 130.0, -255.0, 205.0), motor.name),
        ComponentSpec(
            "left_support_post",
            support_post,
            (x_value - 15.0, -230.0, parameters.base_datum_z.value + 40.0),
            support_post.name,
        ),
        ComponentSpec(
            "right_support_post",
            support_post,
            (x_value - 15.0, 230.0, parameters.base_datum_z.value + 40.0),
            support_post.name,
        ),
        ComponentSpec("top_tie", top_tie, (x_value - 15.0, 0.0, 280.0), top_tie.name),
        ComponentSpec(
            "m2_motor_shelf",
            motor_shelf,
            (x_value - 70.0, -255.0, 137.0),
            motor_shelf.name,
        ),
    ]
    for group, z_value, reverse in (("upper", 245.0, True), ("lower", -245.0, False)):
        for index, y_value in enumerate((-120.0, -60.0, 0.0, 60.0, 120.0)):
            components.append(
                ComponentSpec(
                    f"{group}_needle_{index}",
                    needle,
                    (
                        x_value,
                        y_value
                        + (
                            parameters.guide_pitch.value / 2.0
                            if group == "lower"
                            else 0.0
                        ),
                        z_value,
                    ),
                    f"Representative {group} binder needle {index + 1}",
                    y_axis=(0.0, -1.0, 0.0) if reverse else (0.0, 1.0, 0.0),
                )
            )
    assembly = make_static_assembly(
        assembly_id="a50_binder_system",
        name="A50 opposed binder needles, supply, Z slides, and M2 drive",
        components=components,
    )
    print("a50_binder_system: displayed_needles=10 authoritative_count=unresolved")
    return assembly
