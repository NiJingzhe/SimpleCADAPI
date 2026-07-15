"""A90 finite-travel dual-screw synchronized linear take-up geometry."""

from __future__ import annotations

import simplecadapi as scad

from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_cylinder_part,
    make_static_assembly,
)


def make_linear_takeup(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    rail = make_box_part(
        part_id="t_01_linear_rail",
        name="T-01/T-02 finite-travel take-up linear rail",
        size=(parameters.takeup_travel.value, 36.0, 28.0),
        material=materials["structural_steel"],
        tags=("role.linear_takeup", "role.linear_guide"),
    )
    screw = make_cylinder_part(
        part_id="t_03_ball_screw_envelope",
        name="T-03/T-04 ball-screw envelope",
        radius=14.0,
        length=parameters.takeup_travel.value,
        axis=(1.0, 0.0, 0.0),
        material=materials["stainless"],
        tags=("role.linear_takeup", "role.ball_screw_envelope"),
    )
    jaw = make_box_part(
        part_id="t_07_full_width_jaw",
        name="T-07/T-08 full-width box-section take-up jaw",
        size=(70.0, parameters.effective_width.value + 80.0, 38.0),
        material=materials["machined_aluminum"],
        tags=("role.linear_takeup", "role.full_width_clamp"),
    )
    pad = make_box_part(
        part_id="t_09_segmented_clamp_pad",
        name="T-09 segmented compliant clamp pad",
        size=(40.0, 64.0, 8.0),
        material=materials["clamp_pad"],
        tags=("role.linear_takeup", "role.replaceable_clamp_pad"),
    )
    sync_shaft = make_cylinder_part(
        part_id="t_05_sync_shaft",
        name="T-05 mechanically synchronized screw cross-shaft",
        radius=14.0,
        length=720.0,
        axis=(0.0, 1.0, 0.0),
        material=materials["stainless"],
        tags=("role.linear_takeup", "role.mechanical_phase_lock"),
    )
    bevel = make_cylinder_part(
        part_id="t_05_bevel_gear_blank",
        name="T-05 take-up bevel-gear blank",
        radius=42.0,
        length=22.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.linear_takeup", "role.bevel_gear_blank"),
    )
    motor = make_cylinder_part(
        part_id="m10_brake_servo",
        name="M10 take-up brake-servo envelope",
        radius=55.0,
        length=125.0,
        axis=(1.0, 0.0, 0.0),
        material=materials["drive"],
        tags=("role.linear_takeup", "role.brake_motor_envelope"),
    )
    screw_bearing = make_box_part(
        part_id="t_03_screw_bearing_block",
        name="T-03/T-04 ball-screw end bearing block",
        size=(50.0, 70.0, 70.0),
        material=materials["machined_aluminum"],
        tags=("role.linear_takeup", "role.screw_support"),
    )
    carriage_bridge = make_box_part(
        part_id="t_06_takeup_carriage_bridge",
        name="T-06 full-width double-rail take-up carriage",
        size=(70.0, 520.0, 60.0),
        material=materials["structural_steel"],
        tags=("role.linear_takeup", "role.rail_carriage"),
    )
    gearbox_housing = make_box_part(
        part_id="t_05_sync_gearbox_housing",
        name="T-05 synchronized bevel-gear housing",
        size=(80.0, 80.0, 80.0),
        material=materials["machined_aluminum"],
        tags=("role.linear_takeup", "role.right_angle_drive"),
    )
    motor_shelf = make_box_part(
        part_id="t_05_m10_motor_shelf",
        name="T-05/M10 take-up drive mounting shelf",
        size=(180.0, 120.0, 20.0),
        material=materials["structural_steel"],
        tags=("role.linear_takeup", "role.motor_mount"),
    )
    clamp_column = make_box_part(
        part_id="t_08_clamp_column",
        name="T-08 guided upper-jaw clamp column",
        size=(32.0, 32.0, 94.0),
        material=materials["stainless"],
        tags=("role.linear_takeup", "role.clamp_guide"),
    )
    start_x = parameters.x_takeup.value
    half_support = parameters.effective_width.value / 2.0 + 90.0
    components: list[ComponentSpec] = []
    for side, y_value in (("left", -half_support), ("right", half_support)):
        components.extend(
            (
                ComponentSpec(
                    f"{side}_rail",
                    rail,
                    (start_x + parameters.takeup_travel.value / 2.0, y_value, -120.0),
                    f"{side.title()} take-up rail",
                ),
                ComponentSpec(
                    f"{side}_screw",
                    screw,
                    (start_x, y_value, -65.0),
                    f"{side.title()} take-up ball screw",
                ),
                ComponentSpec(
                    f"{side}_bevel_gear",
                    bevel,
                    (start_x - 30.0, y_value, -65.0),
                    f"{side.title()} synchronized bevel gear",
                ),
                ComponentSpec(
                    f"{side}_drive_bearing",
                    screw_bearing,
                    (start_x, y_value, -100.0),
                    f"{side.title()} screw drive bearing",
                ),
                ComponentSpec(
                    f"{side}_floating_bearing",
                    screw_bearing,
                    (start_x + parameters.takeup_travel.value, y_value, -100.0),
                    f"{side.title()} screw floating bearing",
                ),
            )
        )
    clamp_x = start_x + parameters.takeup_step
    components.extend(
        (
            ComponentSpec(
                "takeup_carriage",
                carriage_bridge,
                (clamp_x, 0.0, -100.0),
                carriage_bridge.name,
            ),
            ComponentSpec(
                "lower_jaw", jaw, (clamp_x, 0.0, -44.0), "Lower full-width take-up jaw"
            ),
            ComponentSpec(
                "upper_jaw", jaw, (clamp_x, 0.0, 12.0), "Upper full-width take-up jaw"
            ),
            ComponentSpec(
                "left_clamp_column",
                clamp_column,
                (clamp_x, -170.0, -44.0),
                clamp_column.name,
            ),
            ComponentSpec(
                "right_clamp_column",
                clamp_column,
                (clamp_x, 170.0, -44.0),
                clamp_column.name,
            ),
            ComponentSpec(
                "sync_shaft",
                sync_shaft,
                (start_x - 20.0, -360.0, -65.0),
                sync_shaft.name,
            ),
            ComponentSpec(
                "m10_drive", motor, (start_x - 150.0, -360.0, -65.0), motor.name
            ),
            ComponentSpec(
                "sync_gearbox",
                gearbox_housing,
                (start_x - 20.0, -330.0, -105.0),
                gearbox_housing.name,
            ),
            ComponentSpec(
                "m10_motor_shelf",
                motor_shelf,
                (start_x - 80.0, -360.0, -140.0),
                motor_shelf.name,
            ),
        )
    )
    for jaw_level, z_value in (("lower", -6.0), ("upper", 4.0)):
        for index, y_value in enumerate((-128.0, -64.0, 0.0, 64.0, 128.0)):
            components.append(
                ComponentSpec(
                    f"{jaw_level}_pad_{index}",
                    pad,
                    (clamp_x, y_value, z_value),
                    f"{jaw_level.title()} segmented clamp pad {index + 1}",
                )
            )
    assembly = make_static_assembly(
        assembly_id="a90_linear_takeup",
        name="A90 dual-rail dual-screw full-width finite-travel take-up",
        components=components,
    )
    print(
        f"a90_linear_takeup: travel={parameters.takeup_travel.value:g} "
        f"step={parameters.takeup_step:g} synchronized_screws=2"
    )
    return assembly
