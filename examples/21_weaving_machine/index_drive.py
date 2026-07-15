"""A42 supplier-neutral M1 positive phase-lock transmission geometry."""

from __future__ import annotations

import simplecadapi as scad

from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_cylinder_part,
    make_static_assembly,
)


def make_bias_index_drive(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    motor = make_cylinder_part(
        part_id="m1_servo_envelope",
        name="M1 supplier-neutral servo envelope",
        radius=55.0,
        length=135.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.index_drive", "role.motor_envelope"),
    )
    reducer = make_cylinder_part(
        part_id="m1_planetary_reducer_envelope",
        name="M1 20:1 planetary reducer envelope",
        radius=68.0,
        length=90.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["machined_aluminum"],
        tags=("role.index_drive", "role.reducer_envelope"),
    )
    clutch = make_cylinder_part(
        part_id="m1_torque_limiter",
        name="M1 torque-limiting clutch envelope",
        radius=42.0,
        length=45.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["stainless"],
        tags=("role.index_drive", "role.torque_limiter"),
    )
    shaft = make_cylinder_part(
        part_id="a42_common_index_shaft",
        name="A42 common positive index shaft",
        radius=16.0,
        length=720.0,
        axis=(0.0, 0.0, 1.0),
        material=materials["stainless"],
        tags=("role.index_drive", "role.mechanical_phase_lock"),
    )
    cam = make_cylinder_part(
        part_id="g_13_cam_blank",
        name="G-13 handed conjugate-cam blank, law not frozen",
        radius=82.0,
        length=24.0,
        axis=(0.0, 0.0, 1.0),
        material=materials["drive"],
        tags=("role.index_drive", "role.cam_blank"),
    )
    reversing_gear = make_cylinder_part(
        part_id="a42_reversing_gear_blank",
        name="A42 lower-chain reversing gear blank",
        radius=48.0,
        length=20.0,
        axis=(0.0, 1.0, 0.0),
        material=materials["drive"],
        tags=("role.index_drive", "role.reversing_output"),
    )
    bearing_block = make_box_part(
        part_id="a42_shaft_bearing_block",
        name="A42 common shaft bearing block",
        size=(60.0, 70.0, 70.0),
        material=materials["structural_steel"],
        tags=("role.index_drive", "role.shaft_support"),
    )
    side_plate = make_box_part(
        part_id="a42_drive_side_plate",
        name="A42 shaft and cam mounting side plate",
        size=(80.0, 30.0, 930.0),
        material=materials["structural_steel"],
        tags=("role.index_drive", "role.structural_support"),
    )
    motor_shelf = make_box_part(
        part_id="a42_motor_shelf",
        name="A42 M1 drivetrain mounting shelf",
        size=(500.0, 150.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.index_drive", "role.motor_mount"),
    )
    right_angle_housing = make_box_part(
        part_id="a42_right_angle_housing",
        name="A42 right-angle shaft-input housing",
        size=(90.0, 90.0, 90.0),
        material=materials["machined_aluminum"],
        tags=("role.index_drive", "role.right_angle_drive"),
    )
    reversing_bracket = make_box_part(
        part_id="a42_reversing_gear_bracket",
        name="A42 lower-chain reversing-gear bracket",
        size=(70.0, 160.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.index_drive", "role.gear_support"),
    )
    x_value = parameters.x_guide.value - 120.0
    components = [
        ComponentSpec(
            "drive_side_plate",
            side_plate,
            (x_value + 45.0, -390.0, parameters.base_datum_z.value + 40.0),
            side_plate.name,
        ),
        ComponentSpec(
            "motor_shelf",
            motor_shelf,
            (x_value - 90.0, -360.0, -155.0),
            motor_shelf.name,
        ),
        ComponentSpec("m1_motor", motor, (x_value - 220.0, -360.0, -80.0), motor.name),
        ComponentSpec(
            "m1_reducer", reducer, (x_value - 85.0, -360.0, -80.0), reducer.name
        ),
        ComponentSpec("m1_clutch", clutch, (x_value + 5.0, -360.0, -80.0), clutch.name),
        ComponentSpec(
            "right_angle_housing",
            right_angle_housing,
            (x_value + 45.0, -360.0, -125.0),
            right_angle_housing.name,
        ),
        ComponentSpec(
            "common_index_shaft", shaft, (x_value + 45.0, -360.0, -360.0), shaft.name
        ),
        ComponentSpec(
            "upper_cam_blank",
            cam,
            (x_value + 25.0, -360.0, parameters.guide_frame_half_height.value),
            "Upper handed cam blank",
        ),
        ComponentSpec(
            "lower_cam_blank",
            cam,
            (x_value + 25.0, -360.0, -parameters.guide_frame_half_height.value),
            "Lower handed cam blank",
        ),
        ComponentSpec(
            "upper_bearing",
            bearing_block,
            (x_value + 45.0, -360.0, 250.0),
            bearing_block.name,
        ),
        ComponentSpec(
            "lower_bearing",
            bearing_block,
            (x_value + 45.0, -360.0, -320.0),
            bearing_block.name,
        ),
        ComponentSpec(
            "reversing_gear_bracket",
            reversing_bracket,
            (x_value + 45.0, -280.0, -280.0),
            reversing_bracket.name,
        ),
        ComponentSpec(
            "reversing_gear_a",
            reversing_gear,
            (x_value + 45.0, -310.0, -250.0),
            "Lower chain reversing gear A",
        ),
        ComponentSpec(
            "reversing_gear_b",
            reversing_gear,
            (x_value + 45.0, -250.0, -250.0),
            "Lower chain reversing gear B",
        ),
    ]
    assembly = make_static_assembly(
        assembly_id="a42_bias_index_drive",
        name="A42 M1 reducer, clutch, shaft, cam blanks, and reversing output",
        components=components,
    )
    print("a42_index_drive: positive_outputs=4 continuous_cam_law=false")
    return assembly
