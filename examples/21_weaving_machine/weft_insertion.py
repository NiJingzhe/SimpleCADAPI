"""A60 three-channel rapier insertion and filling-supply geometry."""

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


def _make_rapier_hook(*, materials: dict[str, scad.Material]) -> scad.Part:
    base = scad.make_box_rsolid(
        width=32.0,
        height=7.0,
        depth=6.0,
        bottom_face_center=(0.0, -12.5, 0.0),
    )
    sides = tuple(
        scad.make_box_rsolid(
            width=7.0,
            height=32.0,
            depth=6.0,
            bottom_face_center=(side * 12.5, 0.0, 0.0),
        )
        for side in (-1.0, 1.0)
    )
    body = scad.union_rsolid(base, sides, glue=False)
    release = scad.make_box_rsolid(
        width=12.0,
        height=16.0,
        depth=8.0,
        bottom_face_center=(5.0, 5.0, -1.0),
    )
    body = scad.cut_rsolid(body, release, skip_non_intersecting=False)
    body = apply_tags(
        shape=body,
        tags=("role.filling_hook", "role.yarn_contact", "role.replaceable_tool"),
    )
    return make_part(
        part_id="r_07_rapier_hook",
        name="R-07 polished replaceable rapier hook head",
        body=body,
        material=materials["stainless"],
        connectors=(),
    )


def make_filling_system(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    rapier = make_box_part(
        part_id="r_01_rapier_beam",
        name="R-01/R-03 anti-rotation rapier beam",
        size=(
            18.0,
            parameters.minimum_rapier_travel,
            parameters.rapier_thickness.value,
        ),
        material=materials["machined_aluminum"],
        tags=("role.filling_rapier", "role.transverse_insertion"),
    )
    hook = _make_rapier_hook(materials=materials)
    carrier = make_box_part(
        part_id="r_04_common_rapier_carrier",
        name="R-04 rigid common three-rapier carrier",
        size=(54.0, 70.0, 170.0),
        material=materials["structural_steel"],
        tags=("role.filling_system", "role.common_rapier_carrier"),
    )
    rail = make_box_part(
        part_id="r_05_rapier_linear_rail",
        name="R-05 widely spaced rapier carrier rail",
        size=(34.0, 760.0, 22.0),
        material=materials["structural_steel"],
        tags=("role.filling_system", "role.linear_guide"),
    )
    drive_belt = make_box_part(
        part_id="r_06_htd_belt",
        name="R-06 closed HTD rapier drive-belt envelope",
        size=(12.0, 760.0, 18.0),
        material=materials["belt"],
        tags=("role.filling_system", "role.belt_drive"),
    )
    motor = make_cylinder_part(
        part_id="m3_servo_envelope",
        name="M3 rapier servo envelope",
        radius=55.0,
        length=125.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.filling_system", "role.motor_envelope"),
    )
    carriage_bridge = make_box_part(
        part_id="r_04_rapier_carriage_bridge",
        name="R-04 double-rail rapier carriage bridge",
        size=(150.0, 100.0, 20.0),
        material=materials["machined_aluminum"],
        tags=("role.filling_system", "role.rail_carriage"),
    )
    support_post = make_box_part(
        part_id="r_05_rapier_rail_support",
        name="R-05 rapier-rail support post",
        size=(50.0, 50.0, 442.0),
        material=materials["structural_steel"],
        tags=("role.filling_system", "role.structural_support"),
    )
    base_sill = make_box_part(
        part_id="r_05_rapier_base_sill",
        name="R-05 rapier-rail foundation sill",
        size=(160.0, 960.0, 40.0),
        material=materials["structural_steel"],
        tags=("role.filling_system", "role.frame_interface"),
    )
    motor_shelf = make_box_part(
        part_id="r_06_m3_motor_shelf",
        name="R-06 M3 rapier-drive mounting shelf",
        size=(150.0, 150.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.filling_system", "role.motor_mount"),
    )
    pulley = make_cylinder_part(
        part_id="r_06_htd_pulley",
        name="R-06 supported HTD drive pulley",
        radius=30.0,
        length=16.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.filling_system", "role.belt_pulley"),
    )
    x_value = parameters.x_rapier.value
    home_y = (
        -parameters.effective_width.value / 2.0 - parameters.rapier_left_clearance.value
    )
    components: list[ComponentSpec] = [
        ComponentSpec(
            "rail_base_sill",
            base_sill,
            (x_value, 0.0, parameters.base_datum_z.value),
            base_sill.name,
        ),
        ComponentSpec(
            "common_carrier", carrier, (x_value, home_y - 35.0, -85.0), carrier.name
        ),
        ComponentSpec(
            "carriage_bridge",
            carriage_bridge,
            (x_value, home_y - 35.0, -88.0),
            carriage_bridge.name,
        ),
        ComponentSpec(
            "left_linear_rail", rail, (x_value - 52.0, 0.0, -88.0), rail.name
        ),
        ComponentSpec(
            "right_linear_rail", rail, (x_value + 52.0, 0.0, -88.0), rail.name
        ),
        ComponentSpec(
            "drive_belt", drive_belt, (x_value - 90.0, 0.0, -20.0), drive_belt.name
        ),
        ComponentSpec("m3_motor", motor, (x_value - 145.0, -385.0, -20.0), motor.name),
        ComponentSpec(
            "m3_motor_shelf",
            motor_shelf,
            (x_value - 70.0, -350.0, -95.0),
            motor_shelf.name,
        ),
        ComponentSpec(
            "drive_pulley_left",
            pulley,
            (x_value - 98.0, -380.0, -11.0),
            pulley.name,
        ),
        ComponentSpec(
            "drive_pulley_right",
            pulley,
            (x_value - 98.0, 364.0, -11.0),
            pulley.name,
        ),
    ]
    for x_label, support_x in (("left", x_value - 52.0), ("right", x_value + 52.0)):
        for y_label, support_y in (("rear", -330.0), ("front", 330.0)):
            components.append(
                ComponentSpec(
                    f"{x_label}_{y_label}_rail_support",
                    support_post,
                    (
                        support_x,
                        support_y,
                        parameters.base_datum_z.value + 40.0,
                    ),
                    support_post.name,
                )
            )
    for index, z_value in enumerate(parameters.filling_planes_z):
        components.extend(
            (
                ComponentSpec(
                    f"rapier_{index}",
                    rapier,
                    (
                        x_value,
                        home_y + parameters.minimum_rapier_travel / 2.0,
                        z_value - parameters.rapier_thickness.value / 2.0,
                    ),
                    f"Rapier at filling plane Z={z_value:g}",
                ),
                ComponentSpec(
                    f"hook_head_{index}",
                    hook,
                    (
                        x_value,
                        parameters.effective_width.value / 2.0
                        + parameters.rapier_right_clearance.value
                        - 16.0,
                        z_value - 3.0,
                    ),
                    f"R-07 hook head {index + 1}",
                ),
            )
        )
    assembly = make_static_assembly(
        assembly_id="a60_filling_system",
        name="A60 three-channel filling supply and common-carrier rapiers",
        components=components,
    )
    print(
        f"a60_filling_system: rapiers=3 travel={parameters.minimum_rapier_travel:g} "
        f"planes={parameters.filling_planes_z}"
    )
    return assembly
