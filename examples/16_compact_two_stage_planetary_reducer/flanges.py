"""Input and output flange parts."""

from __future__ import annotations

import math

import simplecadapi as scad

from common import _apply_tags, make_axis_part_rpart
from dimensions import (
    INPUT_FLANGE_BOSS_HEIGHT,
    INPUT_FLANGE_BOSS_OUTER_DIAMETER,
    INPUT_FLANGE_BOTTOM_Z,
    INPUT_FLANGE_HOLE_CIRCLE_DIAMETER,
    INPUT_FLANGE_HOLE_COUNT,
    INPUT_FLANGE_HOLE_COUNTERBORE_DEPTH,
    INPUT_FLANGE_HOLE_COUNTERBORE_DIAMETER,
    INPUT_FLANGE_HOLE_DIAMETER,
    INPUT_FLANGE_INNER_DIAMETER,
    INPUT_FLANGE_OUTER_DIAMETER,
    INPUT_FLANGE_THICKNESS,
    INPUT_FLANGE_TOP_Z,
    OUTPUT_FLANGE_BOSS_HEIGHT,
    OUTPUT_FLANGE_BOSS_OUTER_DIAMETER,
    OUTPUT_FLANGE_BOTTOM_Z,
    OUTPUT_FLANGE_CENTER_COUNTERBORE_DEPTH,
    OUTPUT_FLANGE_CENTER_COUNTERBORE_DIAMETER,
    OUTPUT_FLANGE_CENTER_FASTENER_CIRCLE_DIAMETER,
    OUTPUT_FLANGE_CENTER_FASTENER_COUNT,
    OUTPUT_FLANGE_CENTER_FASTENER_DIAMETER,
    OUTPUT_FLANGE_HOLE_CIRCLE_DIAMETER,
    OUTPUT_FLANGE_HOLE_COUNT,
    OUTPUT_FLANGE_HOLE_COUNTERBORE_DEPTH,
    OUTPUT_FLANGE_HOLE_COUNTERBORE_DIAMETER,
    OUTPUT_FLANGE_HOLE_DIAMETER,
    OUTPUT_FLANGE_HOLE_OFFSET_DEGREES,
    OUTPUT_FLANGE_HOLES_PER_PAD,
    OUTPUT_FLANGE_INNER_DIAMETER,
    OUTPUT_FLANGE_OUTER_DIAMETER,
    OUTPUT_FLANGE_REGISTER_GAP_WIDTH,
    OUTPUT_FLANGE_REGISTER_HEIGHT,
    OUTPUT_FLANGE_REGISTER_INNER_DIAMETER,
    OUTPUT_FLANGE_REGISTER_OUTER_DIAMETER,
    OUTPUT_FLANGE_REGISTER_PAD_COUNT,
    OUTPUT_FLANGE_THICKNESS,
    OUTPUT_FLANGE_TOP_Z,
)


@scad.requires_session
def make_input_flange_rpart(*, material: scad.Material) -> scad.Part:
    """Create the reducer input flange part with six bolt holes."""

    flange = _make_n_hole_flange_solid_rsolid(
        flange_outer_diameter=INPUT_FLANGE_OUTER_DIAMETER,
        flange_inner_diameter=INPUT_FLANGE_INNER_DIAMETER,
        flange_thickness=INPUT_FLANGE_THICKNESS,
        boss_outer_diameter=INPUT_FLANGE_BOSS_OUTER_DIAMETER,
        boss_height=INPUT_FLANGE_BOSS_HEIGHT,
        hole_diameter=INPUT_FLANGE_HOLE_DIAMETER,
        hole_circle_diameter=INPUT_FLANGE_HOLE_CIRCLE_DIAMETER,
        hole_count=INPUT_FLANGE_HOLE_COUNT,
        counterbore_diameter=INPUT_FLANGE_HOLE_COUNTERBORE_DIAMETER,
        counterbore_depth=INPUT_FLANGE_HOLE_COUNTERBORE_DEPTH,
        tag_prefix="reducer.input.flange",
    )
    flange = scad.translate_shape(
        shape=flange,
        vector=(0.0, 0.0, INPUT_FLANGE_BOTTOM_Z),
    )
    flange = _apply_tags(
        flange,
        tags=("role.input_flange", "group.two_stage_reducer"),
    )
    print(
        f"input_flange: outer_diameter={INPUT_FLANGE_OUTER_DIAMETER:.1f} "
        f"top_z={INPUT_FLANGE_TOP_Z:.3f} faces={len(flange.get_faces())}"
    )
    return make_axis_part_rpart(
        part_id="input_flange",
        solid=flange,
        name="Six-hole input flange",
        material=material,
        connector_specs=(
            {
                "connector_id": "axis",
                "center_xy": (0.0, 0.0),
                "target_z": INPUT_FLANGE_TOP_Z,
                "normal_z": 1.0,
            },
        ),
    )


@scad.requires_session
def make_output_flange_rpart(*, material: scad.Material) -> scad.Part:
    """Create the reducer output flange part with realistic mounting detail."""

    flange = _make_output_flange_solid_rsolid(tag_prefix="reducer.output.flange")
    flange = scad.translate_shape(
        shape=flange,
        vector=(0.0, 0.0, OUTPUT_FLANGE_BOTTOM_Z),
    )
    flange = _apply_tags(
        flange,
        tags=("role.output_flange", "group.two_stage_reducer"),
    )
    print(
        f"output_flange: outer_diameter={OUTPUT_FLANGE_OUTER_DIAMETER:.1f} "
        f"holes={OUTPUT_FLANGE_HOLE_COUNT} top_z={OUTPUT_FLANGE_TOP_Z:.3f} "
        f"faces={len(flange.get_faces())}"
    )
    return make_axis_part_rpart(
        part_id="output_flange",
        solid=flange,
        name="Six-hole output flange",
        material=material,
        connector_specs=(
            {
                "connector_id": "axis",
                "center_xy": (0.0, 0.0),
                "target_z": OUTPUT_FLANGE_TOP_Z,
                "normal_z": 1.0,
            },
        ),
    )


@scad.requires_session
def _make_output_flange_solid_rsolid(*, tag_prefix: str) -> scad.Solid:
    """Build the sealed actuator-style output flange.

    The earlier example used a small six-hole disk.  That was enough to prove
    the gear train, but it did not describe how a robot link would actually find
    and fasten to the actuator.  This output part keeps the simple reducer core
    while adding three production-oriented details: a broad rotating face close
    to the housing bore, segmented raised register pads for quick angular
    location, and separate center fasteners for retaining the output cap.
    """

    base = scad.make_cylinder_rsolid(
        radius=OUTPUT_FLANGE_OUTER_DIAMETER / 2.0,
        height=OUTPUT_FLANGE_THICKNESS,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.base",
        result_tag=f"solid.{tag_prefix}.base",
    )
    boss = scad.make_cylinder_rsolid(
        radius=OUTPUT_FLANGE_BOSS_OUTER_DIAMETER / 2.0,
        height=OUTPUT_FLANGE_BOSS_HEIGHT + 0.05,
        bottom_face_center=(0.0, 0.0, OUTPUT_FLANGE_THICKNESS - 0.05),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.boss",
        result_tag=f"solid.{tag_prefix}.boss",
    )

    register_outer = scad.make_cylinder_rsolid(
        radius=OUTPUT_FLANGE_REGISTER_OUTER_DIAMETER / 2.0,
        height=OUTPUT_FLANGE_REGISTER_HEIGHT + 0.05,
        bottom_face_center=(0.0, 0.0, OUTPUT_FLANGE_THICKNESS - 0.05),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.register.outer",
        result_tag=f"solid.{tag_prefix}.register.outer",
    )
    register_inner = scad.make_cylinder_rsolid(
        radius=OUTPUT_FLANGE_REGISTER_INNER_DIAMETER / 2.0,
        height=OUTPUT_FLANGE_REGISTER_HEIGHT + 0.55,
        bottom_face_center=(0.0, 0.0, OUTPUT_FLANGE_THICKNESS - 0.30),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.register.inner",
        result_tag=f"solid.{tag_prefix}.register.inner.cutter",
    )
    register = scad.cut_rsolid(register_outer, register_inner, skip_non_intersecting=False)

    # The register ring is intentionally shallow and segmented.  In real joint
    # modules this gives the mating link a positive anti-slip locating feature:
    # the link can have matching recesses, so torque is not carried only by screw
    # friction while the assembler is trying to align the output face.
    flange = scad.union_rsolid([base, boss, register], glue=False)

    cutters = [
        scad.make_cylinder_rsolid(
            radius=OUTPUT_FLANGE_INNER_DIAMETER / 2.0,
            height=OUTPUT_FLANGE_THICKNESS + OUTPUT_FLANGE_BOSS_HEIGHT + 2.0,
            bottom_face_center=(0.0, 0.0, -1.0),
            axis=(0.0, 0.0, 1.0),
            tag_prefix=f"{tag_prefix}.center.bore",
            result_tag=f"solid.{tag_prefix}.center.bore.cutter",
        )
    ]

    register_mid_radius = (
        OUTPUT_FLANGE_REGISTER_INNER_DIAMETER + OUTPUT_FLANGE_REGISTER_OUTER_DIAMETER
    ) / 4.0
    register_radial_width = (
        OUTPUT_FLANGE_REGISTER_OUTER_DIAMETER - OUTPUT_FLANGE_REGISTER_INNER_DIAMETER
    ) / 2.0
    for index in range(OUTPUT_FLANGE_REGISTER_PAD_COUNT):
        gap_angle = 60.0 + 360.0 * index / OUTPUT_FLANGE_REGISTER_PAD_COUNT
        gap = scad.make_box_rsolid(
            width=register_radial_width + 2.2,
            height=OUTPUT_FLANGE_REGISTER_GAP_WIDTH,
            depth=OUTPUT_FLANGE_REGISTER_HEIGHT + 0.6,
            bottom_face_center=(
                register_mid_radius,
                0.0,
                OUTPUT_FLANGE_THICKNESS - 0.25,
            ),
            tag_prefix=f"{tag_prefix}.register.gap.i{index + 1}",
            result_tag=f"solid.{tag_prefix}.register.gap.i{index + 1}.cutter",
        )
        cutters.append(
            scad.rotate_shape(
                shape=gap,
                angle=gap_angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        )

    output_bolt_radius = OUTPUT_FLANGE_HOLE_CIRCLE_DIAMETER / 2.0
    output_hole_angles = []
    for pad_index in range(OUTPUT_FLANGE_REGISTER_PAD_COUNT):
        pad_center_angle = 360.0 * pad_index / OUTPUT_FLANGE_REGISTER_PAD_COUNT
        for hole_index in range(OUTPUT_FLANGE_HOLES_PER_PAD):
            side = -1.0 if hole_index == 0 else 1.0
            output_hole_angles.append(pad_center_angle + side * OUTPUT_FLANGE_HOLE_OFFSET_DEGREES)

    for index, angle_degrees in enumerate(output_hole_angles):
        angle = math.radians(angle_degrees)
        x = output_bolt_radius * math.cos(angle)
        y = output_bolt_radius * math.sin(angle)

        # These holes sit on the raised pads rather than on a flat disk.  That is
        # the visible design cue from the reference actuator: the pad geometry is
        # a locating interface, and the screws clamp through that known land.
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=OUTPUT_FLANGE_HOLE_DIAMETER / 2.0,
                height=OUTPUT_FLANGE_THICKNESS + OUTPUT_FLANGE_REGISTER_HEIGHT + 1.0,
                bottom_face_center=(x, y, -0.5),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"{tag_prefix}.link.hole.i{index + 1}",
                result_tag=f"solid.{tag_prefix}.link.hole.i{index + 1}.cutter",
            )
        )
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=OUTPUT_FLANGE_HOLE_COUNTERBORE_DIAMETER / 2.0,
                height=OUTPUT_FLANGE_HOLE_COUNTERBORE_DEPTH + 0.3,
                bottom_face_center=(
                    x,
                    y,
                    OUTPUT_FLANGE_THICKNESS
                    + OUTPUT_FLANGE_REGISTER_HEIGHT
                    - OUTPUT_FLANGE_HOLE_COUNTERBORE_DEPTH,
                ),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"{tag_prefix}.link.counterbore.i{index + 1}",
                result_tag=f"solid.{tag_prefix}.link.counterbore.i{index + 1}.cutter",
            )
        )

    cap_bolt_radius = OUTPUT_FLANGE_CENTER_FASTENER_CIRCLE_DIAMETER / 2.0
    for index in range(OUTPUT_FLANGE_CENTER_FASTENER_COUNT):
        angle = 2.0 * math.pi * index / OUTPUT_FLANGE_CENTER_FASTENER_COUNT + math.radians(30.0)
        x = cap_bolt_radius * math.cos(angle)
        y = cap_bolt_radius * math.sin(angle)

        # The center screws read as output-cap retention hardware.  Keeping them
        # separate from the larger link-mount holes mirrors real actuator stackups:
        # service screws retain the internal cap; larger screws attach the robot.
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=OUTPUT_FLANGE_CENTER_FASTENER_DIAMETER / 2.0,
                height=OUTPUT_FLANGE_THICKNESS + OUTPUT_FLANGE_BOSS_HEIGHT + 1.0,
                bottom_face_center=(x, y, -0.5),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"{tag_prefix}.cap.hole.i{index + 1}",
                result_tag=f"solid.{tag_prefix}.cap.hole.i{index + 1}.cutter",
            )
        )
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=OUTPUT_FLANGE_CENTER_COUNTERBORE_DIAMETER / 2.0,
                height=OUTPUT_FLANGE_CENTER_COUNTERBORE_DEPTH + 0.3,
                bottom_face_center=(
                    x,
                    y,
                    OUTPUT_FLANGE_THICKNESS
                    + OUTPUT_FLANGE_BOSS_HEIGHT
                    - OUTPUT_FLANGE_CENTER_COUNTERBORE_DEPTH,
                ),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"{tag_prefix}.cap.counterbore.i{index + 1}",
                result_tag=f"solid.{tag_prefix}.cap.counterbore.i{index + 1}.cutter",
            )
        )

    flange = scad.cut_rsolid(flange, cutters, skip_non_intersecting=False)
    flange = _apply_tags(
        flange,
        tags=("role.output_register_pads", "role.link_mount_interface"),
    )
    print(
        f"output_flange_core: od={OUTPUT_FLANGE_OUTER_DIAMETER:.1f} "
        f"register_pads={OUTPUT_FLANGE_REGISTER_PAD_COUNT} link_holes={len(output_hole_angles)} "
        f"cap_holes={OUTPUT_FLANGE_CENTER_FASTENER_COUNT} faces={len(flange.get_faces())} "
        f"volume={flange.get_volume():.3f}"
    )
    return flange


@scad.requires_session
def _make_n_hole_flange_solid_rsolid(
    *,
    flange_outer_diameter: float,
    flange_inner_diameter: float,
    flange_thickness: float,
    boss_outer_diameter: float,
    boss_height: float,
    hole_diameter: float,
    hole_circle_diameter: float,
    hole_count: int,
    counterbore_diameter: float | None = None,
    counterbore_depth: float = 0.0,
    tag_prefix: str,
) -> scad.Solid:
    """Build a flange without edge-pick features so FreeCAD export is stable."""

    outer = scad.make_cylinder_rsolid(
        radius=flange_outer_diameter / 2.0,
        height=flange_thickness,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.base",
        result_tag=f"solid.{tag_prefix}.base",
    )
    boss = scad.make_cylinder_rsolid(
        radius=boss_outer_diameter / 2.0,
        height=boss_height + 0.05,
        bottom_face_center=(0.0, 0.0, flange_thickness - 0.05),
        axis=(0.0, 0.0, 1.0),
        tag_prefix=f"{tag_prefix}.boss",
        result_tag=f"solid.{tag_prefix}.boss",
    )
    flange = scad.union_rsolid([outer, boss], glue=False)

    cutters = [
        scad.make_cylinder_rsolid(
            radius=flange_inner_diameter / 2.0,
            height=flange_thickness + boss_height + 2.0,
            bottom_face_center=(0.0, 0.0, -1.0),
            axis=(0.0, 0.0, 1.0),
            tag_prefix=f"{tag_prefix}.center.bore",
            result_tag=f"solid.{tag_prefix}.center.bore.cutter",
        )
    ]
    bolt_circle_radius = hole_circle_diameter / 2.0
    for index in range(hole_count):
        angle = 2.0 * math.pi * index / hole_count
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=hole_diameter / 2.0,
                height=flange_thickness + boss_height + 2.0,
                bottom_face_center=(
                    bolt_circle_radius * math.cos(angle),
                    bolt_circle_radius * math.sin(angle),
                    -1.0,
                ),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"{tag_prefix}.mount.hole.i{index + 1}",
                result_tag=f"solid.{tag_prefix}.mount.hole.i{index + 1}.cutter",
            )
        )
        if counterbore_diameter is not None and counterbore_depth > 0.0:
            # Even the input-side service flange gets proper screw head relief.
            # Otherwise the front end looks realistic while the motor/input side
            # remains a bare demo disk with no way to sit flush against a cover.
            cutters.append(
                scad.make_cylinder_rsolid(
                    radius=counterbore_diameter / 2.0,
                    height=counterbore_depth + 0.3,
                    bottom_face_center=(
                        bolt_circle_radius * math.cos(angle),
                        bolt_circle_radius * math.sin(angle),
                        flange_thickness - counterbore_depth,
                    ),
                    axis=(0.0, 0.0, 1.0),
                    tag_prefix=f"{tag_prefix}.mount.counterbore.i{index + 1}",
                    result_tag=f"solid.{tag_prefix}.mount.counterbore.i{index + 1}.cutter",
                )
            )
    flange = scad.cut_rsolid(flange, cutters, skip_non_intersecting=False)
    print(
        f"flange_core: od={flange_outer_diameter:.1f} id={flange_inner_diameter:.1f} "
        f"holes={hole_count} hole_d={hole_diameter:.1f} faces={len(flange.get_faces())} "
        f"volume={flange.get_volume():.3f}"
    )
    return flange
