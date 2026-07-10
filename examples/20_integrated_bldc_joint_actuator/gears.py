"""Herringbone ring, planet, carrier, and output parts for the 20:1 reducer."""

from __future__ import annotations

import math

import simplecadapi as scad

from common import (
    apply_tags,
    make_axis_part_rpart,
    make_axial_hole_cutters_rsolids,
    make_z_rotation_rplacement,
)
from dimensions import (
    ADDENDUM_FACTOR,
    BACKLASH,
    CLEARANCE_FACTOR,
    GEAR_HEIGHT,
    HELIX_ANGLE,
    INTERSTAGE_BEARING_CENTER_Z,
    OUTPUT_BEARING_1_CENTER_Z,
    OUTPUT_BEARING_2_CENTER_Z,
    OUTPUT_FLANGE_BOTTOM_Z,
    OUTPUT_FLANGE_RADIUS,
    OUTPUT_FLANGE_TOP_Z,
    OUTPUT_LINK_HOLE_PCD,
    OUTPUT_LINK_HOLE_RADIUS,
    OUTPUT_SHAFT_RADIUS,
    PLANET_BEARING,
    PLANET_COUNT,
    PRESSURE_ANGLE,
    RING_INSERT_OUTER_RADIUS,
    RING_RIM_THICKNESS,
    RING_SUPPORT_OVERLAP,
    STAGE1_ARM_WIDTH,
    STAGE1_CARRIER_BOTTOM_Z,
    STAGE1_CARRIER_THICKNESS,
    STAGE1_HUB_RADIUS,
    STAGE1_PAD_RADIUS,
    STAGE1_PIN_BOTTOM_Z,
    STAGE1_PIN_RADIUS,
    STAGE2_ARM_WIDTH,
    STAGE2_CARRIER_BOTTOM_Z,
    STAGE2_CARRIER_THICKNESS,
    STAGE2_HUB_RADIUS,
    STAGE2_PAD_RADIUS,
    STAGE2_PIN_BOTTOM_Z,
    STAGE2_PIN_RADIUS,
    STAGE_1,
    STAGE_2,
    INTERSTAGE_SHAFT_RADIUS,
    StageSpec,
)


def make_stage_ring_gear_rpart(
    *,
    stage: StageSpec,
    material: scad.Material,
) -> scad.Part:
    """Create one herringbone ring insert with a full housing support rim."""

    ring = scad.std.gear.make_herringbone_ring_gear_rsolid(
        n_teeth=stage.ring_teeth,
        module=stage.module,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=-HELIX_ANGLE,
        gear_height=GEAR_HEIGHT,
        rim_thickness=RING_RIM_THICKNESS,
        backlash=BACKLASH,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
    )
    support = scad.make_cylinder_rsolid(
        radius=RING_INSERT_OUTER_RADIUS,
        height=GEAR_HEIGHT,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
    )
    support_bore = scad.make_cylinder_rsolid(
        radius=stage.ring_outer_radius - RING_SUPPORT_OVERLAP,
        height=GEAR_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
    )
    support = scad.cut_rsolid(support, support_bore, skip_non_intersecting=False)
    ring = scad.union_rsolid(ring, support, glue=False)
    ring = apply_tags(
        shape=ring,
        tags=(f"role.{stage.stage_id}.fixed_ring_gear", "role.ring_gear_press_fit", "group.two_stage_reducer"),
    )
    print(
        f"{stage.stage_id}_ring: teeth={stage.ring_teeth} pitch_r={stage.ring_pitch_radius:.3f} "
        f"toothed_outer_r={stage.ring_outer_radius:.3f} insert_d={RING_INSERT_OUTER_RADIUS * 2.0:.2f}"
    )
    return make_axis_part_rpart(
        part_id=f"{stage.stage_id}_fixed_ring",
        body=ring,
        name=f"{stage.label} replaceable fixed herringbone ring insert",
        material=material,
        connectors=(("axis", (0.0, 0.0, GEAR_HEIGHT / 2.0), "Fixed ring axis"),),
    )


def make_stage_planet_gear_rpart(
    *,
    stage: StageSpec,
    material: scad.Material,
) -> scad.Part:
    """Create one reusable herringbone planet with a standard-bearing seat."""

    planet = scad.std.gear.make_herringbone_gear_rsolid(
        n_teeth=stage.planet_teeth,
        module=stage.module,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=-HELIX_ANGLE,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    bearing_seat_radius = PLANET_BEARING.outer_diameter / 2.0 + 0.05
    bearing_seat = scad.make_cylinder_rsolid(
        radius=bearing_seat_radius,
        height=GEAR_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
    )
    planet = scad.cut_rsolid(planet, bearing_seat, skip_non_intersecting=False)
    planet = apply_tags(
        shape=planet,
        tags=(f"role.{stage.stage_id}.planet_gear", "role.planet_bearing_seat", "group.two_stage_reducer"),
    )
    root_radius = stage.planet_pitch_radius - stage.module * (ADDENDUM_FACTOR + CLEARANCE_FACTOR)
    print(
        f"{stage.stage_id}_planet: teeth={stage.planet_teeth} pitch_r={stage.planet_pitch_radius:.3f} "
        f"bearing_seat_r={bearing_seat_radius:.3f} root_ligament={root_radius - bearing_seat_radius:.3f}"
    )
    return make_axis_part_rpart(
        part_id=f"{stage.stage_id}_reusable_planet",
        body=planet,
        name=f"{stage.label} reusable bearing-supported planet",
        material=material,
        connectors=(
            ("axis", (0.0, 0.0, GEAR_HEIGHT / 2.0), "Planet spin axis"),
            ("bearing_axis", (0.0, 0.0, GEAR_HEIGHT / 2.0), "Planet bearing outer-ring axis"),
        ),
    )


def make_stage1_carrier_sun_rpart(*, material: scad.Material) -> scad.Part:
    """Create the first carrier and integral second-stage sun/shaft."""

    carrier = _make_carrier_body_rsolid(
        stage=STAGE_1,
        plate_bottom_z=STAGE1_CARRIER_BOTTOM_Z,
        plate_thickness=STAGE1_CARRIER_THICKNESS,
        pin_bottom_z=STAGE1_PIN_BOTTOM_Z,
        pin_radius=STAGE1_PIN_RADIUS,
        hub_radius=STAGE1_HUB_RADIUS,
        arm_width=STAGE1_ARM_WIDTH,
        pad_radius=STAGE1_PAD_RADIUS,
    )
    shaft = scad.make_cylinder_rsolid(
        radius=INTERSTAGE_SHAFT_RADIUS,
        height=STAGE_2.top_z - STAGE1_CARRIER_BOTTOM_Z + 0.1,
        bottom_face_center=(0.0, 0.0, STAGE1_CARRIER_BOTTOM_Z - 0.05),
        axis=(0.0, 0.0, 1.0),
    )
    stage2_sun = scad.std.gear.make_herringbone_gear_rsolid(
        n_teeth=STAGE_2.sun_teeth,
        module=STAGE_2.module,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=HELIX_ANGLE,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    stage2_sun = scad.translate_shape(shape=stage2_sun, vector=(0.0, 0.0, STAGE_2.bottom_z))
    carrier = scad.union_rsolid(carrier, shaft, stage2_sun, glue=False)
    carrier = apply_tags(
        shape=carrier,
        tags=("role.stage1.planet_carrier", "role.stage2.sun_gear", "role.integral_interstage_drive", "group.two_stage_reducer"),
    )
    connectors = [
        ("carrier_axis", (0.0, 0.0, INTERSTAGE_BEARING_CENTER_Z), "Stage 1 carrier bearing axis"),
        (
            "interstage_bearing_axis",
            (0.0, 0.0, INTERSTAGE_BEARING_CENTER_Z),
            "Interstage bearing inner-ring seat",
        ),
        ("stage2_sun_axis", (0.0, 0.0, STAGE_2.mid_z), "Integral stage 2 sun axis"),
    ]
    for index in range(PLANET_COUNT):
        center = planet_center_xy(stage=STAGE_1, index=index)
        connectors.extend(
            (
                (f"planet_{index + 1}_axis", (*center, STAGE_1.mid_z), f"Stage 1 planet {index + 1} axis"),
                (f"planet_{index + 1}_bearing_axis", (*center, STAGE_1.mid_z), f"Stage 1 planet {index + 1} bearing pin"),
            )
        )
    print(
        f"stage1_carrier_sun: pins={PLANET_COUNT} shaft_d={INTERSTAGE_SHAFT_RADIUS * 2.0:.2f} "
        f"stage2_sun_teeth={STAGE_2.sun_teeth}"
    )
    return make_axis_part_rpart(
        part_id="stage1_carrier_integral_stage2_sun",
        body=carrier,
        name="Stage 1 carrier with integral stage-2 sun shaft",
        material=material,
        connectors=connectors,
    )


def make_output_carrier_flange_rpart(
    *,
    stage: StageSpec,
    material: scad.Material,
) -> scad.Part:
    """Create the second carrier, 16 mm bearing land, and output flange."""

    carrier = _make_carrier_body_rsolid(
        stage=stage,
        plate_bottom_z=STAGE2_CARRIER_BOTTOM_Z,
        plate_thickness=STAGE2_CARRIER_THICKNESS,
        pin_bottom_z=STAGE2_PIN_BOTTOM_Z,
        pin_radius=STAGE2_PIN_RADIUS,
        hub_radius=STAGE2_HUB_RADIUS,
        arm_width=STAGE2_ARM_WIDTH,
        pad_radius=STAGE2_PAD_RADIUS,
    )
    shaft = scad.make_cylinder_rsolid(
        radius=OUTPUT_SHAFT_RADIUS,
        height=OUTPUT_FLANGE_TOP_Z - STAGE2_CARRIER_BOTTOM_Z + 0.1,
        bottom_face_center=(0.0, 0.0, STAGE2_CARRIER_BOTTOM_Z - 0.05),
        axis=(0.0, 0.0, 1.0),
    )
    flange = scad.make_cylinder_rsolid(
        radius=OUTPUT_FLANGE_RADIUS,
        height=OUTPUT_FLANGE_TOP_Z - OUTPUT_FLANGE_BOTTOM_Z,
        bottom_face_center=(0.0, 0.0, OUTPUT_FLANGE_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    output = scad.union_rsolid(carrier, shaft, flange, glue=False)
    output = scad.cut_rsolid(
        output,
        make_axial_hole_cutters_rsolids(
            count=6,
            pcd=OUTPUT_LINK_HOLE_PCD,
            hole_radius=OUTPUT_LINK_HOLE_RADIUS,
            bottom_z=OUTPUT_FLANGE_BOTTOM_Z - 1.0,
            height=OUTPUT_FLANGE_TOP_Z - OUTPUT_FLANGE_BOTTOM_Z + 2.0,
            angle_offset=30.0,
        ),
        skip_non_intersecting=False,
    )
    output = apply_tags(
        shape=output,
        tags=("role.stage2.output_carrier", "role.output_bearing_land", "role.output_link_flange", "group.two_stage_reducer"),
    )
    connectors = [
        ("carrier_axis", (0.0, 0.0, STAGE2_CARRIER_BOTTOM_Z + STAGE2_CARRIER_THICKNESS / 2.0), "Stage 2 output carrier axis"),
        ("bearing_1_axis", (0.0, 0.0, OUTPUT_BEARING_1_CENTER_Z), "Rear output bearing inner-ring seat"),
        ("bearing_2_axis", (0.0, 0.0, OUTPUT_BEARING_2_CENTER_Z), "Front output bearing inner-ring seat"),
        ("output_link_axis", (0.0, 0.0, OUTPUT_FLANGE_TOP_Z), "Six-hole driven-link flange"),
    ]
    for index in range(PLANET_COUNT):
        center = planet_center_xy(stage=stage, index=index)
        connectors.extend(
            (
                (f"planet_{index + 1}_axis", (*center, stage.mid_z), f"Stage 2 planet {index + 1} axis"),
                (f"planet_{index + 1}_bearing_axis", (*center, stage.mid_z), f"Stage 2 planet {index + 1} bearing pin"),
            )
        )
    radial_ligament = OUTPUT_FLANGE_RADIUS - (OUTPUT_LINK_HOLE_PCD / 2.0 + OUTPUT_LINK_HOLE_RADIUS)
    print(
        f"output_carrier_flange: shaft_d={OUTPUT_SHAFT_RADIUS * 2.0:.2f} holes=6 "
        f"pcd={OUTPUT_LINK_HOLE_PCD:.1f} radial_ligament={radial_ligament:.2f}"
    )
    return make_axis_part_rpart(
        part_id="stage2_output_carrier_flange",
        body=output,
        name="Stage 2 carrier with paired-bearing shaft and output flange",
        material=material,
        connectors=connectors,
    )


def make_planet_rplacement(*, stage: StageSpec, index: int) -> scad.Placement:
    """Place and visually phase one planet at its pitch center."""

    center = planet_center_xy(stage=stage, index=index)
    carrier_angle = 360.0 * index / PLANET_COUNT
    spin = carrier_angle + 180.0 - 180.0 / stage.planet_teeth
    print(
        f"{stage.stage_id}_planet_{index + 1}_placement: center="
        f"({center[0]:.3f},{center[1]:.3f},{stage.bottom_z:.3f}) spin={spin:.2f}"
    )
    return make_z_rotation_rplacement(
        origin=(center[0], center[1], stage.bottom_z),
        angle_degrees=spin,
    )


def planet_center_xy(*, stage: StageSpec, index: int) -> tuple[float, float]:
    """Return one equally spaced planet pitch center."""

    angle = math.radians(360.0 * index / PLANET_COUNT)
    return (
        stage.planet_center_radius * math.cos(angle),
        stage.planet_center_radius * math.sin(angle),
    )


def _make_carrier_body_rsolid(
    *,
    stage: StageSpec,
    plate_bottom_z: float,
    plate_thickness: float,
    pin_bottom_z: float,
    pin_radius: float,
    hub_radius: float,
    arm_width: float,
    pad_radius: float,
) -> scad.Solid:
    hub = scad.make_cylinder_rsolid(
        radius=hub_radius,
        height=plate_thickness,
        bottom_face_center=(0.0, 0.0, plate_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    solids = [hub]
    pin_height = plate_bottom_z + plate_thickness - pin_bottom_z
    arm_inner_radius = hub_radius - 1.25
    arm_outer_radius = stage.planet_center_radius + pad_radius - 0.25
    arm_length = arm_outer_radius - arm_inner_radius
    arm_center_radius = (arm_inner_radius + arm_outer_radius) / 2.0
    for index in range(PLANET_COUNT):
        angle = 360.0 * index / PLANET_COUNT
        center = planet_center_xy(stage=stage, index=index)
        arm = scad.make_box_rsolid(
            width=arm_length,
            height=arm_width,
            depth=plate_thickness,
            bottom_face_center=(arm_center_radius, 0.0, plate_bottom_z),
        )
        solids.append(
            scad.rotate_shape(
                shape=arm,
                angle=angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=pad_radius,
                height=plate_thickness,
                bottom_face_center=(center[0], center[1], plate_bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=pin_radius,
                height=pin_height,
                bottom_face_center=(center[0], center[1], pin_bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )
    carrier = scad.union_rsolid(solids, glue=False)
    print(
        f"{stage.stage_id}_carrier_body: arm_length={arm_length:.3f} "
        f"hub_embed={hub_radius - arm_inner_radius:.3f} pin_height={pin_height:.3f}"
    )
    return carrier
