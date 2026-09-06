"""Hex-head pivot bolts for the four-bar linkage joints.

Each bolt is a hex-prism head, a washer shoulder, and a plain shank the bar
stack rotates on. The thread is not modeled: MJCF and STEP outputs treat each
joint pivot as a smooth pin, and the hex head carries the fastener identity
visually and for assembly documentation.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import simplecadapi as scad

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dimensions import (  # noqa: E402
    PIVOT_BOLT_HEAD_RADIUS,
    PIVOT_BOLT_HEAD_THICKNESS,
    PIVOT_BOLT_SHAFT_RADIUS,
)


def _hex_prism(radius: float, height: float, bottom_z: float) -> scad.Solid:
    """Regular hexagonal prism along Z starting at bottom_z."""

    points = [
        (
            radius * math.cos(math.radians(60.0 * index)),
            radius * math.sin(math.radians(60.0 * index)),
            0.0,
        )
        for index in range(6)
    ]
    wire = scad.make_polyline_rwire(points=[*points, points[0]])
    face = scad.make_face_from_wire_rface(wire=wire)
    solid = scad.extrude_rsolid(
        face, direction=(0.0, 0.0, 1.0), distance=height
    )
    return scad.translate_shape(solid, vector=(0.0, 0.0, bottom_z))


def make_pivot_bolt_solid(shank_length: float) -> scad.Solid:
    """One hex-head pivot bolt along Z: head at top, shank through -Z."""

    head = _hex_prism(
        radius=PIVOT_BOLT_HEAD_RADIUS,
        height=PIVOT_BOLT_HEAD_THICKNESS,
        bottom_z=-PIVOT_BOLT_HEAD_THICKNESS,
    )
    shank = scad.make_cylinder_rsolid(
        radius=PIVOT_BOLT_SHAFT_RADIUS,
        height=shank_length,
        bottom_face_center=(0.0, 0.0, -shank_length),
    )
    shoulder = scad.make_cylinder_rsolid(
        radius=PIVOT_BOLT_HEAD_RADIUS * 0.8,
        height=0.6,
        bottom_face_center=(0.0, 0.0, -0.3),
    )
    body = scad.union_rsolid([head, shank, shoulder])
    return scad.apply_tag(shape=body, tag="role.pivot_bolt")


def make_pivot_bolt_part(
    part_id: str,
    shank_length: float,
    *,
    material: "scad.Material | None" = None,
) -> scad.Part:
    """One bolt Part with a Z-axis connector at the head center."""

    body = make_pivot_bolt_solid(shank_length)
    part = scad.make_part_rpart(
        part_id=part_id, body=body, name=part_id.replace("_", " ")
    )
    if material is not None:
        part = scad.assign_material_rpart(part=part, material=material)
    return scad.add_connector_rpart(
        part=part,
        connector=scad.make_placement_connector_rconnector(
            connector_id="axis",
            placement=scad.identity_placement_rplacement(),
        ),
    )
