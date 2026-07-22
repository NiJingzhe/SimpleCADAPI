"""Reusable herringbone gear parts for the two-stage reducer."""

from __future__ import annotations

import math

import simplecadapi as scad
from simplecadapi import ql

from common import (
    _apply_tags,
    add_placement_axis_connector_rpart,
    make_axis_part_rpart,
    make_z_rotation_rplacement,
)
from dimensions import (
    ADDENDUM_FACTOR,
    BACKLASH,
    CLEARANCE_FACTOR,
    FIXED_RING_HOUSING_SUPPORT_OVERLAP,
    GEAR_HEIGHT,
    HOUSING_INNER_RADIUS,
    MODULE,
    PRESSURE_ANGLE,
    RING_RIM_THICKNESS,
    BearingSpec,
    StageSpec,
)


@scad.requires_session
def make_stage_ring_gear_rpart(
    *,
    stage: StageSpec,
    material: scad.Material,
) -> scad.Part:
    """Create one fixed internal herringbone ring gear part for a stage."""

    ring = scad.std.gear.make_herringbone_ring_gear_rsolid(
        n_teeth=stage.ring_teeth,
        module=MODULE,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=stage.ring_helix_angle,
        gear_height=GEAR_HEIGHT,
        rim_thickness=RING_RIM_THICKNESS,
        backlash=BACKLASH,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
    )
    ring = scad.apply_tag(shape=ring, tag=f"solid.reducer.{stage.stage_id}.ring.gear")
    support = scad.make_cylinder_rsolid(
        radius=HOUSING_INNER_RADIUS,
        height=stage.gear_height,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"reducer.{stage.stage_id}.ring.support.outer",
        result_tag=f"solid.reducer.{stage.stage_id}.ring.support.outer",
    )
    support_bore = scad.make_cylinder_rsolid(
        radius=stage.ring_outer_radius - FIXED_RING_HOUSING_SUPPORT_OVERLAP,
        height=stage.gear_height + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"reducer.{stage.stage_id}.ring.support.bore",
        result_tag=f"solid.reducer.{stage.stage_id}.ring.support.bore.cutter",
    )
    support = scad.cut_rsolid(
        support,
        support_bore,
        skip_non_intersecting=False,
        tracking_policy=scad.TrackingPolicy.GRAPH,
    )
    support = scad.apply_tag(shape=support, tag=f"role.{stage.stage_id}.fixed_ring_housing_support")
    ring = scad.union_rsolid(
        [ring, support],
        glue=False,
        tracking_policy=scad.TrackingPolicy.GRAPH,
    )
    ring = _apply_tags(
        ring,
        tags=(f"role.{stage.stage_id}.fixed_ring_gear", "group.two_stage_reducer"),
    )
    _ground_gear(label=f"{stage.stage_id}_ring", solid=ring)
    print(
        f"{stage.stage_id}_ring_pitch: teeth={stage.ring_teeth} "
        f"pitch_radius={stage.ring_pitch_radius:.3f} outer_radius={stage.ring_outer_radius:.3f} "
        f"support_outer_radius={HOUSING_INNER_RADIUS:.3f}"
    )
    return make_axis_part_rpart(
        part_id=f"{stage.stage_id}_ring_gear",
        solid=ring,
        name=f"{stage.label} fixed herringbone ring gear",
        material=material,
        connector_specs=(
            {
                "connector_id": "axis",
                "center_xy": (0.0, 0.0),
                "target_z": GEAR_HEIGHT,
                "normal_z": 1.0,
            },
        ),
    )


@scad.requires_session
def make_stage_sun_gear_rpart(
    *,
    stage: StageSpec,
    bore_radius: float,
    material: scad.Material,
) -> scad.Part:
    """Create one bored external herringbone sun gear part for a stage."""

    sun = scad.std.gear.make_herringbone_gear_rsolid(
        n_teeth=stage.sun_teeth,
        module=MODULE,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=stage.sun_helix_angle,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    sun = scad.apply_tag(shape=sun, tag=f"solid.reducer.{stage.stage_id}.sun.gear")
    sun = _cut_bore_rsolid(
        label=f"{stage.stage_id}_sun_bore",
        solid=sun,
        bore_radius=bore_radius,
        tag_prefix=f"reducer.{stage.stage_id}.sun.bore",
    )
    sun = _apply_tags(
        sun,
        tags=(f"role.{stage.stage_id}.sun_gear", "group.two_stage_reducer"),
    )
    _ground_gear(label=f"{stage.stage_id}_sun", solid=sun)
    print(
        f"{stage.stage_id}_sun_pitch: teeth={stage.sun_teeth} "
        f"pitch_radius={stage.sun_pitch_radius:.3f} bore_radius={bore_radius:.3f}"
    )
    return make_axis_part_rpart(
        part_id=f"{stage.stage_id}_sun_gear",
        solid=sun,
        name=f"{stage.label} herringbone sun gear",
        material=material,
        connector_specs=(
            {
                "connector_id": "axis",
                "center_xy": (0.0, 0.0),
                "target_z": GEAR_HEIGHT,
                "normal_z": 1.0,
            },
        ),
    )


@scad.requires_session
def make_stage_planet_gear_rpart(
    *,
    stage: StageSpec,
    bearing: BearingSpec,
    material: scad.Material,
) -> scad.Part:
    """Create a reusable bored herringbone planet gear part for a stage."""

    planet = scad.std.gear.make_herringbone_gear_rsolid(
        n_teeth=stage.planet_teeth,
        module=MODULE,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=stage.planet_helix_angle,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    planet = scad.apply_tag(shape=planet, tag=f"solid.reducer.{stage.stage_id}.planet.gear")
    bore_radius = bearing.outer_diameter / 2.0 + 0.06
    planet = _cut_bore_rsolid(
        label=f"{stage.stage_id}_planet_bearing_seat",
        solid=planet,
        bore_radius=bore_radius,
        tag_prefix=f"reducer.{stage.stage_id}.planet.bearing.seat",
    )
    planet = _apply_tags(
        planet,
        tags=(f"role.{stage.stage_id}.planet_gear", "group.two_stage_reducer"),
    )
    _ground_gear(label=f"{stage.stage_id}_planet", solid=planet)
    print(
        f"{stage.stage_id}_planet_pitch: teeth={stage.planet_teeth} "
        f"pitch_radius={stage.planet_pitch_radius:.3f} bearing_seat_radius={bore_radius:.3f}"
    )
    part = make_axis_part_rpart(
        part_id=f"{stage.stage_id}_planet_gear",
        solid=planet,
        name=f"{stage.label} reusable herringbone planet gear",
        material=material,
        connector_specs=(
            {
                "connector_id": "axis",
                "center_xy": (0.0, 0.0),
                "target_z": GEAR_HEIGHT,
                "normal_z": 1.0,
            },
        ),
    )
    return add_placement_axis_connector_rpart(
        part=part,
        connector_id="bearing_axis",
        origin=(0.0, 0.0, stage.gear_height / 2.0),
        name=f"{stage.label} planet bearing bore axis",
    )


@scad.requires_session
def make_planet_component_rplacement(
    *,
    stage: StageSpec,
    planet_index: int,
) -> scad.Placement:
    """Return the placed and phased component placement for one planet gear."""

    carrier_angle = 360.0 * planet_index / 3.0
    angle_radians = math.radians(carrier_angle)
    center = (
        stage.planet_center_radius * math.cos(angle_radians),
        stage.planet_center_radius * math.sin(angle_radians),
        stage.bottom_z,
    )
    planet_spin = carrier_angle + 180.0 - (180.0 / stage.planet_teeth)
    print(
        f"{stage.stage_id}_planet_{planet_index + 1}: center=({center[0]:.3f},{center[1]:.3f},{center[2]:.3f}) "
        f"carrier_angle={carrier_angle:.1f} spin={planet_spin:.1f}"
    )
    return make_z_rotation_rplacement(origin=center, angle_degrees=planet_spin)


@scad.requires_session
def _cut_bore_rsolid(
    *,
    label: str,
    solid: scad.Solid,
    bore_radius: float,
    tag_prefix: str,
) -> scad.Solid:
    cutter = scad.make_cylinder_rsolid(
        radius=bore_radius,
        height=GEAR_HEIGHT + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=tag_prefix,
        result_tag=f"solid.{tag_prefix}.cutter",
    )
    bored = scad.cut_rsolid(
        solid,
        cutter,
        skip_non_intersecting=False,
        tracking_policy=scad.TrackingPolicy.GRAPH,
    )
    bored = scad.apply_tag(shape=bored, tag=f"solid.cut.{label}")
    print(f"{label}: bore_radius={bore_radius:.3f} volume={bored.get_volume():.3f}")
    return bored


def _ground_gear(*, label: str, solid: scad.Solid) -> None:
    faces = ql.select(items=solid.get_faces()).all()
    edges = ql.select(items=solid.get_edges()).all()
    print(
        f"gear_{label}: faces={len(faces)} edges={len(edges)} "
        f"volume={solid.get_volume():.3f} tags={','.join(scad.list_tags(shape=solid))}"
    )
