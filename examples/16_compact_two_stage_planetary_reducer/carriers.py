"""Carrier plates, planet pins, and coaxial output shafts."""

from __future__ import annotations

import math

import simplecadapi as scad

from common import _apply_tags, add_placement_axis_connector_rpart, make_axis_part_rpart
from dimensions import (
    INTERMEDIATE_BEARING_Z,
    OUTPUT_FLANGE_TOP_Z,
    OUTPUT_BEARING_Z,
    OUTPUT_SHAFT_RADIUS,
    PLANET_COUNT,
    STAGE1_ARM_WIDTH,
    STAGE1_CARRIER_PLATE_BOTTOM_Z,
    STAGE1_CARRIER_PLATE_THICKNESS,
    STAGE1_CARRIER_SHAFT_RADIUS,
    STAGE1_HUB_RADIUS,
    STAGE1_PAD_RADIUS,
    STAGE1_PIN_BOTTOM_Z,
    STAGE1_PIN_LAND_RADIUS,
    STAGE1_PIN_RADIUS,
    STAGE2_ARM_WIDTH,
    STAGE2_CARRIER_PLATE_BOTTOM_Z,
    STAGE2_CARRIER_PLATE_THICKNESS,
    STAGE2_HUB_RADIUS,
    STAGE2_PAD_RADIUS,
    STAGE2_PIN_BOTTOM_Z,
    STAGE2_PIN_LAND_RADIUS,
    STAGE2_PIN_RADIUS,
    STAGE_2,
    StageSpec,
)


def make_stage_carrier_rpart(
    *,
    stage: StageSpec,
    material: scad.Material,
) -> scad.Part:
    """Create one carrier with three planet pins and any coaxial drive shaft."""

    if stage.stage_id == "stage1":
        solid = _make_carrier_solid_rsolid(
            stage=stage,
            plate_bottom_z=STAGE1_CARRIER_PLATE_BOTTOM_Z,
            plate_thickness=STAGE1_CARRIER_PLATE_THICKNESS,
            pin_bottom_z=STAGE1_PIN_BOTTOM_Z,
            pin_radius=STAGE1_PIN_RADIUS,
            pin_land_radius=STAGE1_PIN_LAND_RADIUS,
            hub_radius=STAGE1_HUB_RADIUS,
            arm_width=STAGE1_ARM_WIDTH,
            pad_radius=STAGE1_PAD_RADIUS,
            central_shaft_radius=STAGE1_CARRIER_SHAFT_RADIUS,
            central_shaft_top_z=STAGE_2.top_z,
        )
        connector_specs = [
            {
                "connector_id": "carrier_axis",
                "center_xy": (0.0, 0.0),
                "target_z": STAGE_2.top_z,
                "normal_z": 1.0,
            },
            {
                "connector_id": "stage2_sun_axis",
                "center_xy": (0.0, 0.0),
                "target_z": STAGE_2.top_z,
                "normal_z": 1.0,
            },
        ]
    elif stage.stage_id == "stage2":
        solid = _make_carrier_solid_rsolid(
            stage=stage,
            plate_bottom_z=STAGE2_CARRIER_PLATE_BOTTOM_Z,
            plate_thickness=STAGE2_CARRIER_PLATE_THICKNESS,
            pin_bottom_z=STAGE2_PIN_BOTTOM_Z,
            pin_radius=STAGE2_PIN_RADIUS,
            pin_land_radius=STAGE2_PIN_LAND_RADIUS,
            hub_radius=STAGE2_HUB_RADIUS,
            arm_width=STAGE2_ARM_WIDTH,
            pad_radius=STAGE2_PAD_RADIUS,
            central_shaft_radius=OUTPUT_SHAFT_RADIUS,
            central_shaft_top_z=OUTPUT_FLANGE_TOP_Z,
        )
        connector_specs = [
            {
                "connector_id": "carrier_axis",
                "center_xy": (0.0, 0.0),
                "target_z": OUTPUT_FLANGE_TOP_Z,
                "normal_z": 1.0,
            },
            {
                "connector_id": "output_axis",
                "center_xy": (0.0, 0.0),
                "target_z": OUTPUT_FLANGE_TOP_Z,
                "normal_z": 1.0,
            },
        ]
    else:
        raise ValueError(f"unsupported carrier stage: {stage.stage_id}")

    for index in range(PLANET_COUNT):
        connector_specs.append(
            {
                "connector_id": f"planet_{index + 1}_axis",
                "center_xy": _planet_center(stage=stage, planet_index=index),
                "target_z": stage.top_z,
                "normal_z": 1.0,
            }
        )

    part = make_axis_part_rpart(
        part_id=f"{stage.stage_id}_carrier",
        solid=solid,
        name=f"{stage.label} carrier with planet pins",
        material=material,
        connector_specs=connector_specs,
    )
    if stage.stage_id == "stage1":
        part = add_placement_axis_connector_rpart(
            part=part,
            connector_id="intermediate_bearing_axis",
            origin=(0.0, 0.0, INTERMEDIATE_BEARING_Z),
            name="Intermediate bearing shaft seat axis",
        )
    else:
        part = add_placement_axis_connector_rpart(
            part=part,
            connector_id="output_bearing_axis",
            origin=(0.0, 0.0, OUTPUT_BEARING_Z),
            name="Output bearing shaft seat axis",
        )
    for index in range(PLANET_COUNT):
        part = add_placement_axis_connector_rpart(
            part=part,
            connector_id=f"planet_{index + 1}_bearing_axis",
            origin=(*_planet_center(stage=stage, planet_index=index), stage.mid_z),
            name=f"{stage.label} planet {index + 1} bearing pin axis",
        )
    return part


def _make_carrier_solid_rsolid(
    *,
    stage: StageSpec,
    plate_bottom_z: float,
    plate_thickness: float,
    pin_bottom_z: float,
    pin_radius: float,
    pin_land_radius: float,
    hub_radius: float,
    arm_width: float,
    pad_radius: float,
    central_shaft_radius: float,
    central_shaft_top_z: float,
) -> scad.Solid:
    hub = scad.make_cylinder_rsolid(
        radius=hub_radius,
        height=plate_thickness,
        bottom_face_center=(0.0, 0.0, plate_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    solids = [hub]

    shaft_bottom_z = plate_bottom_z - 0.05
    solids.append(
        scad.make_cylinder_rsolid(
            radius=central_shaft_radius,
            height=central_shaft_top_z - shaft_bottom_z,
            bottom_face_center=(0.0, 0.0, shaft_bottom_z),
            axis=(0.0, 0.0, 1.0),
        )
    )

    arm_inner_radius = max(central_shaft_radius + 0.45, hub_radius - 0.35)
    arm_outer_radius = stage.planet_center_radius + pad_radius - 0.25
    arm_length = arm_outer_radius - arm_inner_radius
    arm_center_radius = (arm_inner_radius + arm_outer_radius) / 2.0
    pin_height = plate_bottom_z + plate_thickness - pin_bottom_z
    pin_land_height = stage.top_z - pin_bottom_z

    for index in range(PLANET_COUNT):
        carrier_angle = 360.0 * index / PLANET_COUNT
        center_xy = _planet_center(stage=stage, planet_index=index)

        arm = scad.make_box_rsolid(
            width=arm_length,
            height=arm_width,
            depth=plate_thickness,
            bottom_face_center=(arm_center_radius, 0.0, plate_bottom_z),
        )
        if abs(carrier_angle) > 1.0e-9:
            arm = scad.rotate_shape(
                shape=arm,
                angle=carrier_angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        solids.append(arm)
        solids.append(
            scad.make_cylinder_rsolid(
                radius=pad_radius,
                height=plate_thickness,
                bottom_face_center=(center_xy[0], center_xy[1], plate_bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=pin_radius,
                height=pin_height,
                bottom_face_center=(center_xy[0], center_xy[1], pin_bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=pin_land_radius,
                height=pin_land_height,
                bottom_face_center=(center_xy[0], center_xy[1], pin_bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )

    carrier = scad.union_rsolid(solids, glue=False)
    carrier = _apply_tags(
        carrier,
        tags=(f"role.{stage.stage_id}.planet_carrier", "group.two_stage_reducer"),
    )
    print(
        f"{stage.stage_id}_carrier_geometry: center_radius={stage.planet_center_radius:.3f} "
        f"arm_length={arm_length:.3f} pin_height={pin_height:.3f} shaft_top={central_shaft_top_z:.3f} "
        f"faces={len(carrier.get_faces())} volume={carrier.get_volume():.3f}"
    )
    return carrier


def _planet_center(*, stage: StageSpec, planet_index: int) -> tuple[float, float]:
    angle = math.radians(360.0 * planet_index / PLANET_COUNT)
    return (
        stage.planet_center_radius * math.cos(angle),
        stage.planet_center_radius * math.sin(angle),
    )
