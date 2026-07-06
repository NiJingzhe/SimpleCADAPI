"""Bearing standard assemblies built from public SimpleCAD product APIs.

The factories in this module return product-level assemblies rather than a
single merged solid when the standard part has meaningful internal motion.  A
ball bearing is a small assembly: the important kinematic relationship is the
revolute axis between the outer ring and the inner ring, while direct sphere
balls sit in continuous toroidal raceway grooves at authored positions.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from ..product import Assembly, Part
from ..operations import (
    add_component_rassembly,
    add_connector_rpart,
    add_revolute_constraint_rassembly,
    apply_tag,
    chamfer_rsolid,
    forward_connector_rassembly,
    identity_placement_rplacement,
    make_assembly_rassembly,
    make_connector_ref_rconnectorref,
    make_face_connector_rconnector,
    make_face_from_wire_rface,
    make_line_redge,
    make_part_rpart,
    make_placement_rplacement,
    make_sphere_rsolid,
    make_three_point_arc_redge,
    make_wire_from_edges_rwire,
    revolve_rsolid,
)
from ..core import Face, Solid

__all__ = ["make_ball_bearing_rassembly"]


def _validate_positive_finite(name: str, value: float) -> float:
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"{name} must be finite")
    if resolved <= 0.0:
        raise ValueError(f"{name} must be positive")
    return resolved


def _validate_non_negative_finite(name: str, value: float) -> float:
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ValueError(f"{name} must be finite")
    if resolved < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return resolved


def _infer_ball_count(ball_pitch_radius: float, ball_diameter: float) -> int:
    circumference = 2.0 * math.pi * ball_pitch_radius
    # A conservative visual default leaves room for a printed cage/gap between
    # adjacent balls instead of packing tangent spheres around the pitch circle.
    return max(3, int(math.floor(circumference / (1.5 * ball_diameter))))


def _validate_ball_count(
    ball_count: Optional[int],
    ball_pitch_radius: float,
    ball_diameter: float,
) -> int:
    if ball_count is None:
        resolved = _infer_ball_count(ball_pitch_radius, ball_diameter)
    else:
        resolved = int(ball_count)
    if resolved < 3:
        raise ValueError("ball_count must be at least 3")

    chord_spacing = 2.0 * ball_pitch_radius * math.sin(math.pi / resolved)
    if chord_spacing <= ball_diameter:
        raise ValueError(
            "ball_count is too high for ball_diameter on the bearing pitch circle"
        )
    return resolved


def _candidate_chamfer_edges(solid: Solid, bearing_width: float) -> List[object]:
    circular_min_length = max(1e-6, bearing_width * 1.1)
    return [edge for edge in solid.get_edges() if edge.get_length() > circular_min_length]


def _apply_edge_chamfer(solid: Solid, edge_chamfer: float, bearing_width: float) -> Solid:
    if edge_chamfer <= 0.0:
        return solid
    edges = _candidate_chamfer_edges(solid, bearing_width)
    if not edges:
        return solid
    return chamfer_rsolid(solid, edges, edge_chamfer)


def _make_race_ring_solid(
    bore_or_inner_radius: float,
    outer_or_shoulder_radius: float,
    ball_pitch_radius: float,
    groove_radius: float,
    bearing_width: float,
    edge_chamfer: float,
    role: str,
) -> Solid:
    half_width = bearing_width / 2.0
    if role == "inner_ring":
        inner_radius = bore_or_inner_radius
        outer_radius = outer_or_shoulder_radius
        mouth_offset = ball_pitch_radius - outer_radius
        if mouth_offset <= 0.0 or mouth_offset >= groove_radius:
            raise ValueError("inner ring shoulder radius must expose the raceway groove")
        mouth_z = math.sqrt(max(0.0, groove_radius * groove_radius - mouth_offset * mouth_offset))
        points = [
            (inner_radius, 0.0, -half_width),
            (outer_radius, 0.0, -half_width),
            (outer_radius, 0.0, -mouth_z),
            (ball_pitch_radius - groove_radius, 0.0, 0.0),
            (outer_radius, 0.0, mouth_z),
            (outer_radius, 0.0, half_width),
            (inner_radius, 0.0, half_width),
        ]
        arc_start = points[2]
        arc_mid = points[3]
        arc_end = points[4]
        edges = [
            make_line_redge(points[0], points[1]),
            make_line_redge(points[1], arc_start),
            make_three_point_arc_redge(arc_start, arc_mid, arc_end),
            make_line_redge(arc_end, points[5]),
            make_line_redge(points[5], points[6]),
            make_line_redge(points[6], points[0]),
        ]
    elif role == "outer_ring":
        inner_radius = bore_or_inner_radius
        outer_radius = outer_or_shoulder_radius
        mouth_offset = inner_radius - ball_pitch_radius
        if mouth_offset <= 0.0 or mouth_offset >= groove_radius:
            raise ValueError("outer ring shoulder radius must expose the raceway groove")
        mouth_z = math.sqrt(max(0.0, groove_radius * groove_radius - mouth_offset * mouth_offset))
        points = [
            (inner_radius, 0.0, -half_width),
            (outer_radius, 0.0, -half_width),
            (outer_radius, 0.0, half_width),
            (inner_radius, 0.0, half_width),
            (inner_radius, 0.0, mouth_z),
            (ball_pitch_radius + groove_radius, 0.0, 0.0),
            (inner_radius, 0.0, -mouth_z),
        ]
        arc_start = points[4]
        arc_mid = points[5]
        arc_end = points[6]
        edges = [
            make_line_redge(points[0], points[1]),
            make_line_redge(points[1], points[2]),
            make_line_redge(points[2], points[3]),
            make_line_redge(points[3], arc_start),
            make_three_point_arc_redge(arc_start, arc_mid, arc_end),
            make_line_redge(arc_end, points[0]),
        ]
    else:
        raise ValueError("role must be inner_ring or outer_ring")

    profile = make_face_from_wire_rface(
        make_wire_from_edges_rwire(edges),
        normal=(0.0, -1.0, 0.0),
    )
    ring = revolve_rsolid(
        profile,
        axis=(0.0, 0.0, 1.0),
        angle=360.0,
        origin=(0.0, 0.0, 0.0),
    )
    ring = apply_tag(ring, f"role.{role}")
    ring = apply_tag(ring, "group.ball_bearing")
    ring = _apply_edge_chamfer(ring, edge_chamfer, bearing_width)
    ring.set_metadata(
        "std.bearing.ring",
        {
            "role": role,
            "inner_radius": inner_radius,
            "outer_radius": outer_radius,
            "ball_pitch_radius": ball_pitch_radius,
            "groove_radius": groove_radius,
            "raceway_mouth_z": mouth_z,
            "bearing_width": bearing_width,
            "edge_chamfer": edge_chamfer,
        },
    )
    return ring


def _axis_face(solid: Solid, target_z: float) -> Face:
    candidates = []
    for face in solid.get_faces():
        normal = face.get_normal_at()
        if normal.z < 0.7:
            continue
        center = face.get_center()
        candidates.append((abs(center.z - target_z), -face.get_area(), face))
    if not candidates:
        raise ValueError("no +Z bearing axis face found")
    return min(candidates, key=lambda item: item[0:2])[2]


def _part_with_axis_connector(
    part_id: str,
    body: Solid,
    name: str,
    target_z: float,
) -> Part:
    part = make_part_rpart(part_id, body, name=name)
    axis = make_face_connector_rconnector("axis", _axis_face(body, target_z))
    return add_connector_rpart(part, axis)


def _ball_placement(ball_pitch_radius: float, angle_degrees: float):
    angle = math.radians(angle_degrees)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return make_placement_rplacement(
        origin=(ball_pitch_radius * cos_a, ball_pitch_radius * sin_a, 0.0),
        x_axis=(cos_a, sin_a, 0.0),
        y_axis=(-sin_a, cos_a, 0.0),
    )


def make_ball_bearing_rassembly(
    bore_diameter: float,
    outer_diameter: float,
    bearing_width: float,
    ball_diameter: float,
    ball_count: Optional[int] = None,
    raceway_clearance: float = 0.02,
    edge_chamfer: float = 0.0,
    assembly_id: str = "ball_bearing",
    drive_angle_degrees: Optional[float] = None,
) -> Assembly:
    """Create a parameterized radial ball bearing assembly.

    This factory returns an `Assembly`, not a merged `Solid`, because a bearing
    has useful internal structure.  The returned assembly contains stable
    component ids `outer_ring`, `inner_ring`, and `ball_00`, `ball_01`, ... .
    The inner and outer rings each carry an `axis` connector, and the assembly
    includes one revolute constraint named `inner_outer_revolute` between those
    two axes.  Use `bearing.get_component("inner_ring").item.body` to access
    the inner-ring geometry directly, or use connector refs such as
    `make_connector_ref_rconnectorref("inner_ring", "axis")` when adding shaft
    or housing constraints to the same assembly.

    Parameters use explicit SDK-style names rather than compact catalog labels:
    `bore_diameter` maps to common `id`, `outer_diameter` maps to `od`,
    `bearing_width` maps to axial bearing thickness, `ball_diameter` maps to
    ball size, `raceway_clearance` maps to print clearance around the balls, and
    `edge_chamfer` maps to edge break/chamfer.  There is intentionally no
    Python keyword-only `*` separator in this signature so the function remains
    callable with either positional or keyword arguments.

    `ball_count=None` lets the factory infer a conservative visual ball count
    from the pitch circle.  Explicit `ball_count` is accepted when you need to
    match a real bearing or a printed cage design.  Balls are direct sphere
    primitive solids, and the inner and outer rings are revolved from arc-groove
    profiles to create continuous toroidal raceway grooves.  Balls are visual
    rolling elements fixed at their authored positions; the currently modeled
    kinematic degree of freedom is only the inner-ring-to-outer-ring revolute
    joint.

    For printable bearings, the classic checks from many parametric generators
    are still useful: `((outer_diameter - bore_diameter) / 2) - ball_diameter`
    should leave enough radial wall thickness, and `bearing_width - ball_diameter`
    should be positive so balls do not protrude axially.
    """

    bore_diameter_value = _validate_positive_finite("bore_diameter", bore_diameter)
    outer_diameter_value = _validate_positive_finite("outer_diameter", outer_diameter)
    bearing_width_value = _validate_positive_finite("bearing_width", bearing_width)
    ball_diameter_value = _validate_positive_finite("ball_diameter", ball_diameter)
    raceway_clearance_value = _validate_non_negative_finite(
        "raceway_clearance",
        raceway_clearance,
    )
    edge_chamfer_value = _validate_non_negative_finite("edge_chamfer", edge_chamfer)

    if outer_diameter_value <= bore_diameter_value:
        raise ValueError("outer_diameter must be greater than bore_diameter")

    bore_radius = bore_diameter_value / 2.0
    outer_radius = outer_diameter_value / 2.0
    ball_radius = ball_diameter_value / 2.0
    ball_pitch_radius = (bore_radius + outer_radius) / 2.0
    groove_radius = ball_radius + raceway_clearance_value
    inner_groove_root_radius = ball_pitch_radius - groove_radius
    outer_groove_root_radius = ball_pitch_radius + groove_radius
    inner_wall_thickness = inner_groove_root_radius - bore_radius
    outer_wall_thickness = outer_radius - outer_groove_root_radius
    axial_clearance = bearing_width_value / 2.0 - groove_radius

    if inner_wall_thickness <= 0.0 or outer_wall_thickness <= 0.0:
        raise ValueError(
            "ball_diameter plus raceway_clearance leaves no radial wall thickness"
        )
    if axial_clearance <= 0.0:
        raise ValueError(
            "bearing_width must be greater than ball_diameter plus raceway_clearance"
        )

    smallest_feature = min(inner_wall_thickness, outer_wall_thickness, axial_clearance)
    if edge_chamfer_value >= smallest_feature:
        raise ValueError("edge_chamfer must be smaller than the thinnest bearing feature")

    resolved_ball_count = _validate_ball_count(
        ball_count,
        ball_pitch_radius,
        ball_diameter_value,
    )

    outer_ring = _make_race_ring_solid(
        ball_pitch_radius + ball_radius * 0.75,
        outer_radius,
        ball_pitch_radius,
        groove_radius,
        bearing_width_value,
        edge_chamfer_value,
        "outer_ring",
    )
    inner_ring = _make_race_ring_solid(
        bore_radius,
        ball_pitch_radius - ball_radius * 0.75,
        ball_pitch_radius,
        groove_radius,
        bearing_width_value,
        edge_chamfer_value,
        "inner_ring",
    )
    ball = make_sphere_rsolid(radius=ball_radius, center=(0.0, 0.0, 0.0))
    ball = apply_tag(ball, "role.rolling_element")
    ball = apply_tag(ball, "group.ball_bearing")
    ball.set_metadata(
        "std.bearing.ball",
        {
            "diameter": ball_diameter_value,
            "pitch_radius": ball_pitch_radius,
        },
    )

    outer_part = _part_with_axis_connector(
        "outer_ring",
        outer_ring,
        "Outer bearing ring",
        bearing_width_value / 2.0,
    )
    inner_part = _part_with_axis_connector(
        "inner_ring",
        inner_ring,
        "Inner bearing ring",
        bearing_width_value / 2.0,
    )
    ball_part = make_part_rpart("ball", ball, name="Bearing ball")

    assembly = make_assembly_rassembly(assembly_id, name="Ball bearing")
    assembly = add_component_rassembly(
        assembly,
        outer_part,
        component_id="outer_ring",
        placement=identity_placement_rplacement(),
    )
    assembly = add_component_rassembly(
        assembly,
        inner_part,
        component_id="inner_ring",
        placement=identity_placement_rplacement(),
    )

    ball_component_ids: List[str] = []
    ball_angles: Dict[str, float] = {}
    digits = max(2, len(str(resolved_ball_count - 1)))
    for index in range(resolved_ball_count):
        component_id = f"ball_{index:0{digits}d}"
        angle_degrees = 360.0 * index / resolved_ball_count
        ball_component_ids.append(component_id)
        ball_angles[component_id] = angle_degrees
        assembly = add_component_rassembly(
            assembly,
            ball_part,
            component_id=component_id,
            placement=_ball_placement(ball_pitch_radius, angle_degrees),
        )

    assembly = add_revolute_constraint_rassembly(
        assembly,
        "inner_outer_revolute",
        make_connector_ref_rconnectorref("outer_ring", "axis"),
        make_connector_ref_rconnectorref("inner_ring", "axis"),
        drive_angle_degrees=drive_angle_degrees,
        name="Inner ring spins in outer ring",
    )
    public_axis_offset = make_placement_rplacement(
        origin=(0.0, 0.0, -bearing_width_value / 2.0),
    )
    assembly = forward_connector_rassembly(
        assembly,
        connector_id="outer_axis",
        source_component_id="outer_ring",
        source_connector_id="axis",
        name="Outer ring housing axis",
        offset=public_axis_offset,
    )
    assembly = forward_connector_rassembly(
        assembly,
        connector_id="inner_axis",
        source_component_id="inner_ring",
        source_connector_id="axis",
        name="Inner ring shaft axis",
        offset=public_axis_offset,
    )
    assembly.set_metadata(
        "std.bearing.ball_bearing",
        {
            "bore_diameter": bore_diameter_value,
            "outer_diameter": outer_diameter_value,
            "bearing_width": bearing_width_value,
            "ball_diameter": ball_diameter_value,
            "ball_count": resolved_ball_count,
            "raceway_clearance": raceway_clearance_value,
            "edge_chamfer": edge_chamfer_value,
            "ball_pitch_radius": ball_pitch_radius,
            "groove_radius": groove_radius,
            "inner_groove_root_radius": inner_groove_root_radius,
            "outer_groove_root_radius": outer_groove_root_radius,
            "inner_wall_thickness": inner_wall_thickness,
            "outer_wall_thickness": outer_wall_thickness,
            "axial_clearance": axial_clearance,
            "outer_component_id": "outer_ring",
            "inner_component_id": "inner_ring",
            "ball_component_ids": ball_component_ids,
            "ball_angles_degrees": ball_angles,
            "axis_connector_id": "axis",
            "outer_axis_connector_id": "outer_axis",
            "inner_axis_connector_id": "inner_axis",
            "revolute_constraint_id": "inner_outer_revolute",
        },
    )
    return assembly
