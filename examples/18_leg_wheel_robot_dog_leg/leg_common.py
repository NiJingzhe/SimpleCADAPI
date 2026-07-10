"""Shared geometry helpers for Example 18."""

from __future__ import annotations

import math
from collections.abc import Iterable

import simplecadapi as scad
from simplecadapi import ql


Point3 = tuple[float, float, float]


def bolt_circle_points(
    *,
    center: Point3,
    radius: float,
    angles_degrees: Iterable[float],
) -> tuple[Point3, ...]:
    """Return XY bolt-center points on a named bolt-circle datum."""

    points = []
    for angle_degrees in angles_degrees:
        angle = math.radians(angle_degrees)
        points.append(
            (
                center[0] + radius * math.cos(angle),
                center[1] + radius * math.sin(angle),
                center[2],
            )
        )
    return tuple(points)


def make_bolt_circle_cutters_rsolidlist(
    *,
    center: Point3,
    bolt_circle_radius: float,
    angles_degrees: Iterable[float],
    hole_radius: float,
    z_min: float,
    height: float,
    counterbore_radius: float | None = None,
    counterbore_depth: float = 0.0,
    counterbore_from_top: bool = True,
    counterbore_face_z: float | None = None,
) -> list[scad.Solid]:
    """Build through-hole and optional counterbore cutters for a bolt circle."""

    cutters: list[scad.Solid] = []
    for point in bolt_circle_points(
        center=center,
        radius=bolt_circle_radius,
        angles_degrees=angles_degrees,
    ):
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=hole_radius,
                height=height,
                bottom_face_center=(point[0], point[1], z_min),
                axis=(0.0, 0.0, 1.0),
            )
        )
        if counterbore_radius is not None and counterbore_depth > 0.0:
            face_z = counterbore_face_z
            if face_z is None:
                face_z = z_min + height if counterbore_from_top else z_min
            counterbore_z = face_z - counterbore_depth if counterbore_from_top else face_z - 0.2
            cutters.append(
                scad.make_cylinder_rsolid(
                    radius=counterbore_radius,
                    height=counterbore_depth + 0.2,
                    bottom_face_center=(point[0], point[1], counterbore_z),
                    axis=(0.0, 0.0, 1.0),
                )
            )
    return cutters


def make_rounded_slot_cutter_rsolid(
    *,
    center: Point3,
    length: float,
    width: float,
    height: float,
    angle_degrees: float,
    tag: str,
) -> scad.Solid:
    """Build a capsule-shaped cutter for a lightening pocket."""

    if length <= width:
        raise ValueError("rounded slot length must exceed width")
    radius = width / 2.0
    straight = length - width
    z_min = center[2] - height / 2.0
    bridge = scad.make_box_rsolid(
        width=straight,
        height=width,
        depth=height,
        bottom_face_center=(0.0, 0.0, z_min),
    )
    left = scad.make_cylinder_rsolid(
        radius=radius,
        height=height,
        bottom_face_center=(-straight / 2.0, 0.0, z_min),
        axis=(0.0, 0.0, 1.0),
    )
    right = scad.make_cylinder_rsolid(
        radius=radius,
        height=height,
        bottom_face_center=(straight / 2.0, 0.0, z_min),
        axis=(0.0, 0.0, 1.0),
    )
    cutter = scad.union_rsolid([bridge, left, right], glue=False)
    cutter = scad.rotate_shape(
        shape=cutter,
        angle=angle_degrees,
        axis=(0.0, 0.0, 1.0),
        origin=(0.0, 0.0, center[2]),
    )
    cutter = scad.translate_shape(shape=cutter, vector=(center[0], center[1], 0.0))
    return scad.apply_tag(shape=cutter, tag=tag)


def make_axis_placement_rplacement(
    *,
    origin: Point3,
    axis: str = "z",
) -> scad.Placement:
    """Create a placement whose local Z axis is the requested world axis."""

    if axis == "z":
        return scad.make_placement_rplacement(
            origin=origin,
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
        )
    if axis == "y":
        return scad.make_placement_rplacement(
            origin=origin,
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 0.0, -1.0),
        )
    if axis == "-z":
        return scad.make_placement_rplacement(
            origin=origin,
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, -1.0, 0.0),
        )
    if axis == "x":
        return scad.make_placement_rplacement(
            origin=origin,
            x_axis=(0.0, 1.0, 0.0),
            y_axis=(0.0, 0.0, 1.0),
        )
    raise ValueError(f"unsupported axis {axis!r}")


def make_actuator_target_rplacement(
    *,
    output_axis_origin: Point3,
    output_axis_local_z: float,
    axis: str,
) -> scad.Placement:
    """Place an actuator so its forwarded output/case axis lands on a world point."""

    if axis == "z":
        origin = (
            output_axis_origin[0],
            output_axis_origin[1],
            output_axis_origin[2] - output_axis_local_z,
        )
    elif axis == "y":
        origin = (
            output_axis_origin[0],
            output_axis_origin[1] - output_axis_local_z,
            output_axis_origin[2],
        )
    elif axis == "-z":
        origin = (
            output_axis_origin[0],
            output_axis_origin[1],
            output_axis_origin[2] + output_axis_local_z,
        )
    else:
        raise ValueError(f"unsupported axis {axis!r}")
    return make_axis_placement_rplacement(origin=origin, axis=axis)


def add_datum_connector_rpart(
    *,
    part: scad.Part,
    connector_id: str,
    origin: Point3,
    axis: str = "z",
    name: str | None = None,
) -> scad.Part:
    """Attach a topology-free connector datum to a part."""

    connector = scad.make_placement_connector_rconnector(
        connector_id=connector_id,
        placement=make_axis_placement_rplacement(origin=origin, axis=axis),
        name=name,
    )
    return scad.add_connector_rpart(part=part, connector=connector)


def make_part_with_connectors_rpart(
    *,
    part_id: str,
    body: scad.Solid,
    name: str,
    material: scad.Material,
    connectors: Iterable[tuple[str, Point3, str, str | None]],
) -> scad.Part:
    """Wrap a solid as a materialized Part and add placement connectors."""

    part = scad.make_part_rpart(part_id=part_id, body=body, name=name)
    part = scad.assign_material_rpart(part=part, material=material)
    for connector_id, origin, axis, connector_name in connectors:
        part = add_datum_connector_rpart(
            part=part,
            connector_id=connector_id,
            origin=origin,
            axis=axis,
            name=connector_name,
        )
    print(f"part_{part_id}: connectors={len(part.connectors)} volume={body.get_volume():.3f}")
    return part


def make_rounded_bar_rsolid(
    *,
    start: Point3,
    end: Point3,
    width: float,
    thickness: float,
    end_hole_radius: float,
    lightening_hole_radius: float | None = None,
    lightening_count: int = 0,
    tag: str,
) -> scad.Solid:
    """Build a planar rounded-end plate between two XY points at constant Z."""

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length <= width:
        raise ValueError("rounded bar length must exceed width")
    z_center = start[2]
    z_min = z_center - thickness / 2.0
    radius = width / 2.0
    bridge = scad.make_box_rsolid(
        width=length,
        height=width,
        depth=thickness,
        bottom_face_center=(length / 2.0, 0.0, z_min),
    )
    left = scad.make_cylinder_rsolid(
        radius=radius,
        height=thickness,
        bottom_face_center=(0.0, 0.0, z_min),
        axis=(0.0, 0.0, 1.0),
    )
    right = scad.make_cylinder_rsolid(
        radius=radius,
        height=thickness,
        bottom_face_center=(length, 0.0, z_min),
        axis=(0.0, 0.0, 1.0),
    )
    body = scad.union_rsolid([bridge, left, right], glue=False)
    cutters = [
        scad.make_cylinder_rsolid(
            radius=end_hole_radius,
            height=thickness + 2.0,
            bottom_face_center=(0.0, 0.0, z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=end_hole_radius,
            height=thickness + 2.0,
            bottom_face_center=(length, 0.0, z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
    ]
    if lightening_hole_radius is not None and lightening_count > 0:
        for index in range(lightening_count):
            fraction = (index + 1.0) / (lightening_count + 1.0)
            cutters.append(
                scad.make_cylinder_rsolid(
                    radius=lightening_hole_radius,
                    height=thickness + 2.0,
                    bottom_face_center=(length * fraction, 0.0, z_min - 1.0),
                    axis=(0.0, 0.0, 1.0),
                )
            )
    body = scad.cut_rsolid(body, cutters, skip_non_intersecting=False)
    body = scad.rotate_shape(
        shape=body,
        angle=math.degrees(math.atan2(dy, dx)),
        axis=(0.0, 0.0, 1.0),
        origin=(0.0, 0.0, z_center),
    )
    body = scad.translate_shape(shape=body, vector=(start[0], start[1], 0.0))
    body = scad.apply_tag(shape=body, tag=tag)
    _ground_solid(label=tag, solid=body)
    return body


def _ground_solid(*, label: str, solid: scad.Solid) -> None:
    faces = ql.select(items=solid.get_faces()).all()
    print(f"{label}: faces={len(faces)} volume={solid.get_volume():.3f}")


def _axis_vector(*, axis: str) -> Point3:
    if axis == "z":
        return (0.0, 0.0, 1.0)
    if axis == "y":
        return (0.0, 1.0, 0.0)
    if axis == "x":
        return (1.0, 0.0, 0.0)
    if axis == "-z":
        return (0.0, 0.0, -1.0)
    raise ValueError(f"unsupported axis {axis!r}")


def ground_compound(*, label: str, compound: scad.Compound) -> None:
    """Print compact grounding facts for an assembly preview."""

    solids = ql.select(items=compound.get_solids()).all()
    face_count = sum(len(ql.select(items=solid.get_faces()).all()) for solid in solids)
    print(
        f"{label}: solids={len(solids)} faces={face_count} "
        f"volume={compound.get_volume():.3f}"
    )


def connector_ref(*, component_id: str, connector_id: str) -> scad.ConnectorRef:
    return scad.make_connector_ref_rconnectorref(
        component_id=component_id,
        connector_id=connector_id,
    )
