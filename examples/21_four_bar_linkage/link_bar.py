"""Realistic forged connecting-rod bars for the four-bar linkage.

Each bar is a flat forged link: two circular bearing eyes joined by an I-beam
web, with a bearing bore in each eye, lightening holes in the web, chamfered
eye rims, and a small boss ring around each bore. Z-axis pivot connectors sit
at both eye centers.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import simplecadapi as scad

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dimensions import BAR_THICKNESS, EYE_OUTER_RADIUS, PIVOT_BORE_RADIUS  # noqa: E402

# Web joins the eyes; lightening holes sit between the bores.
WEB_WIDTH_FACTOR = 1.0  # web half-width as a multiple of eye radius
LIGHTENING_HOLE_RADIUS = 2.2
LIGHTENING_HOLE_INSET = 6.0


def _link_body(part_id: str, center_distance: float, lightening_holes: bool) -> scad.Solid:
    """One forged link body along +X from the pivot_a eye center."""
    # Two chamfered circular eyes at (0, 0) and (center_distance, 0), plus an
    # I-beam web: wide flanges top and bottom, thin mid web, single solid.
    def _eye(center: tuple[float, float]) -> scad.Solid:
        cylinder = scad.make_cylinder_rsolid(
            radius=EYE_OUTER_RADIUS,
            height=BAR_THICKNESS,
            bottom_face_center=(center[0], center[1], -BAR_THICKNESS / 2.0),
        )
        return scad.chamfer_rsolid(
            solid=cylinder,
            edges=[cylinder.get_edges(0), cylinder.get_edges(2)],
            distance=0.6,
        )

    eye_a = _eye((0.0, 0.0))
    eye_b = _eye((center_distance, 0.0))
    flange_half_width = WEB_WIDTH_FACTOR * EYE_OUTER_RADIUS * 0.55
    mid_web_half_width = flange_half_width * 0.45
    flange_thickness = BAR_THICKNESS * 0.3
    web_mid = scad.make_box_rsolid(
        width=center_distance + 2.0 * EYE_OUTER_RADIUS,
        height=mid_web_half_width * 2.0,
        depth=BAR_THICKNESS - 2.0 * flange_thickness,
        bottom_face_center=(
            center_distance / 2.0,
            0.0,
            -BAR_THICKNESS / 2.0 + flange_thickness,
        ),
    )
    bottom_flange = scad.make_box_rsolid(
        width=center_distance + 2.0 * EYE_OUTER_RADIUS,
        height=flange_half_width * 2.0,
        depth=flange_thickness,
        bottom_face_center=(
            center_distance / 2.0,
            0.0,
            -BAR_THICKNESS / 2.0,
        ),
    )
    top_flange = scad.make_box_rsolid(
        width=center_distance + 2.0 * EYE_OUTER_RADIUS,
        height=flange_half_width * 2.0,
        depth=flange_thickness,
        bottom_face_center=(
            center_distance / 2.0,
            0.0,
            BAR_THICKNESS / 2.0 - flange_thickness,
        ),
    )
    body = scad.union_rsolid([eye_a, eye_b, web_mid, bottom_flange, top_flange])

    # Bearing bores through both eyes.
    bore_a = scad.make_cylinder_rsolid(
        radius=PIVOT_BORE_RADIUS,
        height=BAR_THICKNESS + 2.0,
        bottom_face_center=(0.0, 0.0, -BAR_THICKNESS / 2.0 - 1.0),
    )
    bore_b = scad.make_cylinder_rsolid(
        radius=PIVOT_BORE_RADIUS,
        height=BAR_THICKNESS + 2.0,
        bottom_face_center=(center_distance, 0.0, -BAR_THICKNESS / 2.0 - 1.0),
    )
    body = scad.cut_rsolid(body, [bore_a, bore_b])

    # Lightening holes in the web between the eyes.
    if lightening_holes and center_distance > 3.0 * EYE_OUTER_RADIUS:
        hole_z = -BAR_THICKNESS / 2.0 - 1.0
        spacing = 0.5 * (center_distance - 2.0 * EYE_OUTER_RADIUS)
        cutters = []
        for sign in (-1.0, 1.0):
            cutters.append(
                scad.make_cylinder_rsolid(
                    radius=LIGHTENING_HOLE_RADIUS,
                    height=BAR_THICKNESS + 2.0,
                    bottom_face_center=(
                        center_distance / 2.0 + sign * spacing / 2.0,
                        0.0,
                        hole_z,
                    ),
                )
            )
        body = scad.cut_rsolid(body, cutters)

    body = scad.apply_tag(shape=body, tag=f"role.link_bar.{part_id}")
    return body


def make_link_part(
    part_id: str,
    center_distance: float,
    *,
    lightening_holes: bool = True,
    material: "scad.Material | None" = None,
) -> scad.Part:
    """One link Part with pivot connectors at both eye centers."""

    body = _link_body(part_id, center_distance, lightening_holes)
    part = scad.make_part_rpart(
        part_id=part_id, body=body, name=part_id.replace("_", " ")
    )
    if material is not None:
        part = scad.assign_material_rpart(part=part, material=material)
    for connector_id, x in (("pivot_a", 0.0), ("pivot_b", center_distance)):
        part = scad.add_connector_rpart(
            part=part,
            connector=scad.make_placement_connector_rconnector(
                connector_id=connector_id,
                placement=scad.make_placement_rplacement(origin=(x, 0.0, 0.0)),
            ),
        )
    return part


def link_faces_and_volume(body: scad.Solid) -> tuple[int, float]:
    """QL grounding facts for one finished link body."""

    return len(body.get_faces()), body.get_volume()
