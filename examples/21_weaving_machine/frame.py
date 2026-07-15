"""A10 representative main frame, supply rack, weaving gantry, and guards."""

from __future__ import annotations

import simplecadapi as scad

from .parameters import MachineParameters
from .representative_parts import ComponentSpec, make_box_part, make_static_assembly


def make_main_frame(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    steel = materials["structural_steel"]
    rail_x = make_box_part(
        part_id="a11_longitudinal_datum_beam",
        name="A11 machined longitudinal datum beam",
        size=(parameters.overall_length.value, 80.0, 40.0),
        material=steel,
        tags=("role.structural_frame", "anchor.datum.a"),
    )
    cross_y = make_box_part(
        part_id="a11_base_crossmember",
        name="A11 base crossmember",
        size=(80.0, 2.0 * parameters.frame_half_width.value + 80.0, 40.0),
        material=steel,
        tags=("role.structural_frame", "role.load_path"),
    )
    upright = make_box_part(
        part_id="a12_a13_upright",
        name="Supply and weaving gantry upright",
        size=(60.0, 60.0, 1240.0),
        material=steel,
        tags=("role.structural_frame", "role.gantry_upright"),
    )
    gantry_cross = make_box_part(
        part_id="a13_gantry_crossbeam",
        name="A13 weaving gantry crossbeam",
        size=(60.0, 2.0 * parameters.frame_half_width.value + 60.0, 60.0),
        material=steel,
        tags=("role.structural_frame", "role.beatup_reaction_path"),
    )
    takeup_post = make_box_part(
        part_id="a14_takeup_post",
        name="A14 take-up support post",
        size=(60.0, 60.0, 620.0),
        material=steel,
        tags=("role.structural_frame", "role.takeup_support"),
    )
    guard_panel = make_box_part(
        part_id="a15_guard_panel",
        name="A15 removable drive and chain guard",
        size=(360.0, 8.0, 360.0),
        material=materials["guard"],
        tags=("role.machine_guard", "role.removable_service_panel"),
    )
    machine_crossbeam = make_box_part(
        part_id="a13_machine_crossbeam",
        name="A13 subsystem mounting crossbeam",
        size=(70.0, 620.0, 50.0),
        material=steel,
        tags=("role.structural_frame", "role.subsystem_support"),
    )
    instrument_post = make_box_part(
        part_id="a13_instrument_post",
        name="A13 guide and forming-zone support post",
        size=(60.0, 60.0, 820.0),
        material=steel,
        tags=("role.structural_frame", "role.subsystem_support"),
    )

    base_z = parameters.base_datum_z.value
    x_min = -parameters.overall_length.value / 2.0 + 100.0
    x_max = parameters.overall_length.value / 2.0 - 100.0
    components: list[ComponentSpec] = []
    for side in (-1.0, 1.0):
        components.append(
            ComponentSpec(
                f"datum_rail_{'left' if side < 0 else 'right'}",
                rail_x,
                (0.0, side * parameters.frame_half_width.value, base_z),
                "Left datum rail" if side < 0 else "Right datum rail",
            )
        )
    for index, x_value in enumerate((x_min, -900.0, -420.0, 0.0, 420.0, 900.0, x_max)):
        components.append(
            ComponentSpec(
                f"base_cross_{index}",
                cross_y,
                (x_value, 0.0, base_z),
                f"Base crossmember {index + 1}",
            )
        )
    for station, x_value in (("supply", -980.0), ("weaving", -40.0)):
        for side in (-1.0, 1.0):
            components.append(
                ComponentSpec(
                    f"{station}_upright_{'left' if side < 0 else 'right'}",
                    upright,
                    (x_value, side * parameters.frame_half_width.value, base_z + 40.0),
                    f"{station.title()} gantry upright",
                )
            )
        components.append(
            ComponentSpec(
                f"{station}_top_crossbeam",
                gantry_cross,
                (x_value, 0.0, base_z + 1280.0),
                f"{station.title()} top crossbeam",
            )
        )
    for x_value in (300.0, 1170.0):
        for side in (-1.0, 1.0):
            components.append(
                ComponentSpec(
                    f"takeup_post_{int(x_value)}_{'left' if side < 0 else 'right'}",
                    takeup_post,
                    (x_value, side * parameters.frame_half_width.value, base_z + 40.0),
                    "Take-up frame post",
                )
            )
        components.append(
            ComponentSpec(
                f"takeup_crossbeam_{int(x_value)}",
                machine_crossbeam,
                (x_value, 0.0, -170.0),
                "Take-up rail support crossbeam",
            )
        )
    for side in (-1.0, 1.0):
        components.append(
            ComponentSpec(
                f"guide_support_post_{'left' if side < 0 else 'right'}",
                instrument_post,
                (-360.0, side * 250.0, base_z + 40.0),
                "Guide-frame support post",
            )
        )
    for level, z_value in (("lower", -232.0), ("upper", 194.0)):
        components.append(
            ComponentSpec(
                f"guide_mount_crossbeam_{level}",
                machine_crossbeam,
                (-360.0, 0.0, z_value),
                f"Guide-frame {level} mounting crossbeam",
            )
        )
    components.extend(
        (
            ComponentSpec(
                "upper_bias_guard",
                guard_panel,
                (-800.0, -parameters.frame_half_width.value - 34.0, 150.0),
                "Upper bias-chain guard",
            ),
            ComponentSpec(
                "lower_bias_guard",
                guard_panel,
                (-800.0, -parameters.frame_half_width.value - 34.0, -330.0),
                "Lower bias-chain guard",
            ),
        )
    )
    return make_static_assembly(
        assembly_id="a10_main_frame",
        name="A10 frame, supply rack, weaving gantry, take-up frame, and guards",
        components=components,
    )
