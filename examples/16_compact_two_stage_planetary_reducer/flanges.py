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
    INPUT_FLANGE_HOLE_DIAMETER,
    INPUT_FLANGE_INNER_DIAMETER,
    INPUT_FLANGE_OUTER_DIAMETER,
    INPUT_FLANGE_THICKNESS,
    INPUT_FLANGE_TOP_Z,
    OUTPUT_FLANGE_BOSS_HEIGHT,
    OUTPUT_FLANGE_BOSS_OUTER_DIAMETER,
    OUTPUT_FLANGE_BOTTOM_Z,
    OUTPUT_FLANGE_HOLE_CIRCLE_DIAMETER,
    OUTPUT_FLANGE_HOLE_COUNT,
    OUTPUT_FLANGE_HOLE_DIAMETER,
    OUTPUT_FLANGE_INNER_DIAMETER,
    OUTPUT_FLANGE_OUTER_DIAMETER,
    OUTPUT_FLANGE_THICKNESS,
    OUTPUT_FLANGE_TOP_Z,
)


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


def make_output_flange_rpart(*, material: scad.Material) -> scad.Part:
    """Create the reducer output flange part with six bolt holes."""

    flange = _make_n_hole_flange_solid_rsolid(
        flange_outer_diameter=OUTPUT_FLANGE_OUTER_DIAMETER,
        flange_inner_diameter=OUTPUT_FLANGE_INNER_DIAMETER,
        flange_thickness=OUTPUT_FLANGE_THICKNESS,
        boss_outer_diameter=OUTPUT_FLANGE_BOSS_OUTER_DIAMETER,
        boss_height=OUTPUT_FLANGE_BOSS_HEIGHT,
        hole_diameter=OUTPUT_FLANGE_HOLE_DIAMETER,
        hole_circle_diameter=OUTPUT_FLANGE_HOLE_CIRCLE_DIAMETER,
        hole_count=OUTPUT_FLANGE_HOLE_COUNT,
    )
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
        f"top_z={OUTPUT_FLANGE_TOP_Z:.3f} faces={len(flange.get_faces())}"
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
) -> scad.Solid:
    """Build a flange without edge-pick features so FreeCAD export is stable."""

    outer = scad.make_cylinder_rsolid(
        radius=flange_outer_diameter / 2.0,
        height=flange_thickness,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
    )
    boss = scad.make_cylinder_rsolid(
        radius=boss_outer_diameter / 2.0,
        height=boss_height + 0.05,
        bottom_face_center=(0.0, 0.0, flange_thickness - 0.05),
        axis=(0.0, 0.0, 1.0),
    )
    flange = scad.union_rsolid([outer, boss], glue=False)

    cutters = [
        scad.make_cylinder_rsolid(
            radius=flange_inner_diameter / 2.0,
            height=flange_thickness + boss_height + 2.0,
            bottom_face_center=(0.0, 0.0, -1.0),
            axis=(0.0, 0.0, 1.0),
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
            )
        )
    flange = scad.cut_rsolid(flange, cutters, skip_non_intersecting=False)
    print(
        f"flange_core: od={flange_outer_diameter:.1f} id={flange_inner_diameter:.1f} "
        f"holes={hole_count} hole_d={hole_diameter:.1f} faces={len(flange.get_faces())} "
        f"volume={flange.get_volume():.3f}"
    )
    return flange
