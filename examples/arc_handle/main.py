"""Parametric arched handle with rounded capsule mounting lands.

X: hole span. Y: bow height and countersunk-hole axis. Z: section width.
The handle is one fused solid. Bolt insertion envelopes are subtractive
installation clearances, not display-only validation geometry.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import simplecadapi as scad
from simplecadapi import ql

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "out" / "arc_handle"
PACKAGE_PATH = OUTPUT_DIR / "arc_handle.scadpkg"
RENDER_PATH = OUTPUT_DIR / "arc_handle.png"

ROD_RADIUS = 8.5
LAND_DEPTH = 5.0
COUNTERSINK_RADIAL_ALLOWANCE = 2.75
LAND_RADIAL_MARGIN = 3.5
ROOT_PAD_RADIUS = 12.0
ROOT_OFFSET_CLEARANCE = 1.5
LAND_EDGE_FILLET = 1.2
ROOT_FILLET_RADIUS = 2.5
COUNTERSINK_DEPTH = 2.0
CUT_OVERSHOOT = 1.0
BOLT_DIAMETRAL_CLEARANCE = 0.2
INSERTION_START_Y = LAND_DEPTH / 2.0 + 2.0 * ROD_RADIUS + CUT_OVERSHOOT
BOLT_TRAVEL_HEIGHT = INSERTION_START_Y + LAND_DEPTH + 2.0 * CUT_OVERSHOOT
THROUGH_CUT_HEIGHT = LAND_DEPTH + 2.0 * ROD_RADIUS + 2.0 * CUT_OVERSHOOT


def _validate_dimensions(*, span: float, sag: float, left_diameter: float, right_diameter: float) -> None:
    if span <= 4.0 * ROOT_PAD_RADIUS:
        raise ValueError("hole span is too short for the capsule lands")
    if sag <= 0.0:
        raise ValueError("bow height must be positive")
    if COUNTERSINK_DEPTH >= LAND_DEPTH:
        raise ValueError("countersink depth must be less than land depth")
    for label, diameter in (("left", left_diameter), ("right", right_diameter)):
        if diameter <= 0.0:
            raise ValueError(f"{label} through-hole diameter must be positive")
        if diameter / 2.0 + COUNTERSINK_RADIAL_ALLOWANCE >= diameter / 2.0 + LAND_RADIAL_MARGIN + COUNTERSINK_RADIAL_ALLOWANCE:
            raise ValueError(f"{label} countersink leaves no land rim")


def _print_stage(label: str, solid: scad.Solid) -> None:
    faces = cast(list[scad.Face], solid.get_faces())
    edges = cast(list[scad.Edge], solid.get_edges())
    print(f"{label}: faces={len(faces)} edges={len(edges)} volume={solid.get_volume():.3f}")


def _capsule_land(*, hole_x: float, root_x: float, hole_radius: float, label: str) -> scad.Solid:
    hole_pad = scad.make_cylinder_rsolid(
        radius=hole_radius,
        height=LAND_DEPTH,
        bottom_face_center=(hole_x, -LAND_DEPTH / 2.0, 0.0),
        axis=(0.0, 1.0, 0.0),
        tag_prefix=f"arc_handle.{label}.hole_pad",
        end_face_tag=f"arc_handle.{label}.pad.front",
        result_tag=f"solid.arc_handle.{label}.hole_pad",
    )
    root_pad = scad.make_cylinder_rsolid(
        radius=ROOT_PAD_RADIUS,
        height=LAND_DEPTH,
        bottom_face_center=(root_x, -LAND_DEPTH / 2.0, 0.0),
        axis=(0.0, 1.0, 0.0),
        tag_prefix=f"arc_handle.{label}.root_pad",
        end_face_tag=f"arc_handle.{label}.pad.front",
        result_tag=f"solid.arc_handle.{label}.root_pad",
    )
    bridge = scad.make_box_rsolid(
        width=abs(root_x - hole_x),
        height=LAND_DEPTH,
        depth=2.0 * ROOT_PAD_RADIUS,
        bottom_face_center=((hole_x + root_x) / 2.0, 0.0, -ROOT_PAD_RADIUS),
        tag_prefix=f"arc_handle.{label}.capsule_bridge",
        front_face_tag=f"arc_handle.{label}.pad.front",
        result_tag=f"solid.arc_handle.{label}.capsule_bridge",
    )
    land = scad.union_rsolid([hole_pad, root_pad, bridge], clean=True, glue=False)
    rim = ql.edges().where(
        ql.and_(
            ql.prop("geom.type", "==", "CIRCLE"),
            ql.or_(
                ql.prop("geom.center.y", ">", LAND_DEPTH / 2.0 - 0.01),
                ql.prop("geom.center.y", "<", -LAND_DEPTH / 2.0 + 0.01),
            ),
        )
    ).exactly(4)
    rim_edges = rim.resolve(land)
    print(f"ql_{label}_land_rim_edges={len(rim_edges)}")
    return scad.fillet_rsolid(
        solid=land,
        edges=rim_edges,
        radius=LAND_EDGE_FILLET,
        result_tag=f"solid.arc_handle.{label}.rounded_capsule_land",
    )


def _root_blend_edges(*, body: scad.Solid, label: str) -> list[scad.Edge]:
    side = "<" if label == "left" else ">"
    pad_face = ql.faces().where(
        ql.and_(
            ql.prop("geom.normal.y", ">", 0.9),
            ql.prop("geom.center.y", ">", 1.0),
            ql.prop("geom.center.x", side, 0.0),
        )
    ).exactly(1)
    rod_face = ql.faces().where(
        ql.and_(
            ql.tag("arc_handle.rod.side"),
            ql.prop("geom.center.x", side, 0.0),
        )
    ).exactly(1)
    shared = pad_face.shared_boundary(rod_face, to_kind="edge").exactly(1)
    edges = shared.resolve(body)
    print(f"ql_{label}_root_shared_edges={len(edges)}")
    return edges


def _through_and_countersink_cutters(*, center_x: float, through_diameter: float) -> tuple[scad.Solid, scad.Solid]:
    through_radius = through_diameter / 2.0
    countersink_radius = through_radius + COUNTERSINK_RADIAL_ALLOWANCE
    outside_radius = countersink_radius + (countersink_radius - through_radius) * CUT_OVERSHOOT / COUNTERSINK_DEPTH
    through = scad.make_cylinder_rsolid(
        radius=through_radius,
        height=THROUGH_CUT_HEIGHT,
        bottom_face_center=(center_x, -LAND_DEPTH / 2.0 - CUT_OVERSHOOT, 0.0),
        axis=(0.0, 1.0, 0.0),
        tag_prefix="arc_handle.hole.through",
        result_tag="solid.arc_handle.hole.through.cutter",
    )
    countersink = scad.make_cone_rsolid(
        bottom_radius=countersink_radius,
        top_radius=outside_radius,
        height=COUNTERSINK_DEPTH + CUT_OVERSHOOT,
        bottom_face_center=(center_x, LAND_DEPTH / 2.0 + CUT_OVERSHOOT, 0.0),
        axis=(0.0, -1.0, 0.0),
        tag_prefix="arc_handle.hole.countersink",
        result_tag="solid.arc_handle.hole.countersink.cutter",
    )
    return through, countersink


def _countersunk_bolt_insertion_envelope(*, center_x: float, through_diameter: float, label: str) -> scad.Solid:
    shaft_radius = (through_diameter - BOLT_DIAMETRAL_CLEARANCE) / 2.0
    head_radius = (through_diameter + 2.0 * COUNTERSINK_RADIAL_ALLOWANCE - BOLT_DIAMETRAL_CLEARANCE) / 2.0
    shaft = scad.make_cylinder_rsolid(
        radius=shaft_radius,
        height=BOLT_TRAVEL_HEIGHT,
        bottom_face_center=(center_x, -LAND_DEPTH / 2.0 - CUT_OVERSHOOT, 0.0),
        axis=(0.0, 1.0, 0.0),
        tag_prefix=f"arc_handle.validation.{label}.shaft",
        result_tag=f"solid.arc_handle.validation.{label}.shaft",
    )
    moving_head = scad.make_cylinder_rsolid(
        radius=head_radius,
        height=INSERTION_START_Y + LAND_DEPTH / 2.0,
        bottom_face_center=(center_x, INSERTION_START_Y, 0.0),
        axis=(0.0, -1.0, 0.0),
        tag_prefix=f"arc_handle.validation.{label}.head",
        result_tag=f"solid.arc_handle.validation.{label}.head",
    )
    return scad.union_rsolid([shaft, moving_head], clean=True, glue=False, tracking_policy="graph")


def _validate_insertion(*, body: scad.Solid, center_x: float, diameter: float, label: str) -> float:
    envelope = _countersunk_bolt_insertion_envelope(center_x=center_x, through_diameter=diameter, label=label)
    remaining = scad.cut_rsolid(envelope, body, skip_non_intersecting=True, tracking_policy="graph")
    overlap = max(0.0, envelope.get_volume() - remaining.get_volume())
    if overlap > 1.0e-7:
        raise ValueError(f"{label} bolt insertion overlap={overlap:.9f} mm^3")
    print(f"{label}_countersunk_bolt_insertion: path=+Y_to_-Y overlap_volume={overlap:.9f}")
    return overlap


@scad.part(id="arc_handle", revision="4.0.0", cache="off", project_root=Path(__file__).resolve().parents[2])
def build_arc_handle_part() -> scad.Part:
    span = scad.var(name="hole_span", default=110.0, comment="center-to-center hole span along X", unit="mm", tolerance=0.1)
    sag = scad.var(name="bow_height", default=24.0, comment="arc midpoint height along Y", unit="mm", tolerance=0.1)
    left_diameter = scad.var(name="left_hole_diameter", default=5.5, comment="left through-hole diameter", unit="mm", tolerance=0.05)
    right_diameter = scad.var(name="right_hole_diameter", default=5.5, comment="right through-hole diameter", unit="mm", tolerance=0.05)
    _validate_dimensions(span=float(span), sag=float(sag), left_diameter=float(left_diameter), right_diameter=float(right_diameter))

    half_span = span / 2.0
    left_x = -half_span
    right_x = half_span
    left_hole_radius = float(left_diameter) / 2.0 + COUNTERSINK_RADIAL_ALLOWANCE + LAND_RADIAL_MARGIN
    right_hole_radius = float(right_diameter) / 2.0 + COUNTERSINK_RADIAL_ALLOWANCE + LAND_RADIAL_MARGIN
    head_radius = (float(left_diameter) + 2.0 * COUNTERSINK_RADIAL_ALLOWANCE - BOLT_DIAMETRAL_CLEARANCE) / 2.0
    root_offset = head_radius + ROOT_PAD_RADIUS + ROOT_OFFSET_CLEARANCE
    left_root_x = left_x + root_offset
    right_root_x = right_x - root_offset
    control_y = sag * 4.0 / 3.0

    path = scad.make_spline_rwire(
        control_points=[(left_root_x, 0.0, 0.0), (left_root_x, control_y, 0.0), (right_root_x, control_y, 0.0), (right_root_x, 0.0, 0.0)],
        degree=3,
    )
    profile = scad.make_circle_rface(center=(float(left_root_x), 0.0, 0.0), radius=ROD_RADIUS, normal=(0.0, 1.0, 0.0), tag_prefix="arc_handle.rod.profile")
    rod = scad.sweep_rsolid(profile=profile, path=path, is_frenet=True, tag_prefix="arc_handle.rod", side_faces_tag="arc_handle.rod.side", result_tag="solid.arc_handle.arched_rod")
    left_land = _capsule_land(hole_x=float(left_x), root_x=float(left_root_x), hole_radius=left_hole_radius, label="left")
    right_land = _capsule_land(hole_x=float(right_x), root_x=float(right_root_x), hole_radius=right_hole_radius, label="right")
    body = scad.union_rsolid([rod, left_land, right_land], clean=True, glue=False)
    _print_stage("fused_capsule_handle", body)

    blend_edges = _root_blend_edges(body=body, label="left") + _root_blend_edges(body=body, label="right")
    if len(blend_edges) != 2:
        raise ValueError(f"expected two QL-selected root edges, got {len(blend_edges)}")
    body = scad.fillet_rsolid(solid=body, edges=blend_edges, radius=ROOT_FILLET_RADIUS, result_tag="solid.arc_handle.root_blends")

    left_through, left_countersink = _through_and_countersink_cutters(center_x=float(left_x), through_diameter=float(left_diameter))
    right_through, right_countersink = _through_and_countersink_cutters(center_x=float(right_x), through_diameter=float(right_diameter))
    left_envelope = _countersunk_bolt_insertion_envelope(center_x=float(left_x), through_diameter=float(left_diameter), label="left")
    right_envelope = _countersunk_bolt_insertion_envelope(center_x=float(right_x), through_diameter=float(right_diameter), label="right")
    body = scad.cut_rsolid(body, [left_through, left_countersink, right_through, right_countersink, left_envelope, right_envelope], skip_non_intersecting=False)
    body = cast(scad.Solid, scad.apply_tag(shape=body, tag="role.arc_handle.continuous_body"))
    body = cast(scad.Solid, scad.apply_tag(shape=body, tag="role.arc_handle.full_bolt_installation_clearance"))
    body.set_metadata("coordinate_convention", "X=span, Y=bow-height and hole axis, Z=thickness")
    body.set_metadata("hole_axis", (0.0, 1.0, 0.0))
    body.set_metadata("countersink_opening_face", "+Y capsule-land faces")
    body.set_metadata("hole_span_mm", float(span))
    body.set_metadata("left_hole_diameter_mm", float(left_diameter))
    body.set_metadata("right_hole_diameter_mm", float(right_diameter))
    body.set_metadata("left_mounting_land_radius_mm", left_hole_radius)
    body.set_metadata("right_mounting_land_radius_mm", right_hole_radius)
    body.set_metadata("root_pad_radius_mm", ROOT_PAD_RADIUS)
    body.set_metadata("root_offset_mm", root_offset)
    body.set_metadata("root_blend_radius_mm", ROOT_FILLET_RADIUS)
    body.set_metadata("countersink_depth_mm", COUNTERSINK_DEPTH)
    _print_stage("finished_body", body)
    return scad.make_part_rpart(part_id="arc_handle", body=body, name="Parametric capsule-land arched handle with countersunk through holes")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = cast(Any, build_arc_handle_part)()
    body = result.part.body
    hole_span = float(body.get_metadata("hole_span_mm"))
    left_overlap = _validate_insertion(body=body, center_x=-hole_span / 2.0, diameter=float(body.get_metadata("left_hole_diameter_mm")), label="left")
    right_overlap = _validate_insertion(body=body, center_x=hole_span / 2.0, diameter=float(body.get_metadata("right_hole_diameter_mm")), label="right")
    body.set_metadata("left_bolt_overlap_volume_mm3", left_overlap)
    body.set_metadata("right_bolt_overlap_volume_mm3", right_overlap)
    scad.capture(result, PACKAGE_PATH, include_scene=True)
    scad.render_screenshot_rpath(shapes=body, output_path=str(RENDER_PATH), view="auto", image_size=(1568, 1176), show_axes=True, show_legend=True, zoom=3.2)
    print(f"package={PACKAGE_PATH}")
    print(f"render={RENDER_PATH}")
    print(f"hole_axis={body.get_metadata('hole_axis')}")
    print(f"countersink_face={body.get_metadata('countersink_opening_face')}")
    print(f"tags={','.join(scad.list_tags(shape=body))}")
    print(f"package_bytes={PACKAGE_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
