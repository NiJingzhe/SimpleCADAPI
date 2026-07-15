"""Shared construction and grounding helpers for the reducer example."""

from __future__ import annotations

import math
from collections.abc import Iterable

import simplecadapi as scad
from simplecadapi import ql


def make_z_rotation_rplacement(
    *,
    origin: tuple[float, float, float],
    angle_degrees: float,
) -> scad.Placement:
    """Return a placement rotated about the local Z axis."""

    angle_radians = math.radians(angle_degrees)
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=(cos_a, sin_a, 0.0),
        y_axis=(-sin_a, cos_a, 0.0),
    )


def make_annular_cylinder_rsolid(
    *,
    outer_radius: float,
    inner_radius: float,
    height: float,
    bottom_z: float,
    tag: str,
) -> scad.Solid:
    """Create a single hollow cylindrical solid with a through bore."""

    if inner_radius <= 0.0 or outer_radius <= inner_radius:
        raise ValueError("annular cylinder requires 0 < inner_radius < outer_radius")
    outer = scad.make_cylinder_rsolid(
        radius=outer_radius,
        height=height,
        bottom_face_center=(0.0, 0.0, bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    bore = scad.make_cylinder_rsolid(
        radius=inner_radius,
        height=height + 2.0,
        bottom_face_center=(0.0, 0.0, bottom_z - 1.0),
        axis=(0.0, 0.0, 1.0),
    )
    annular = scad.cut_rsolid(outer, bore, skip_non_intersecting=False)
    annular = scad.apply_tag(shape=annular, tag=tag)
    _ground_solid(label=tag, solid=annular)
    return annular


def make_axis_connector_rconnector(
    *,
    connector_id: str,
    solid: scad.Solid,
    center_xy: tuple[float, float],
    target_z: float,
    normal_z: float,
    name: str | None = None,
    flip: bool = False,
) -> scad.Connector:
    """Create a face connector on the axial face nearest the requested center."""

    face = _axis_face(
        label=connector_id,
        solid=solid,
        center_xy=center_xy,
        target_z=target_z,
        normal_z=normal_z,
    )
    return scad.make_face_connector_rconnector(
        connector_id=connector_id,
        face=face,
        name=name,
        flip=flip,
    )


def make_axis_part_rpart(
    *,
    part_id: str,
    solid: scad.Solid,
    name: str,
    connector_specs: Iterable[dict[str, object]],
    material: scad.Material | None = None,
) -> scad.Part:
    """Wrap a solid as a Part and attach axial face connectors."""

    part = scad.make_part_rpart(part_id=part_id, body=solid, name=name)
    if material is not None:
        part = scad.assign_material_rpart(part=part, material=material)
    for spec in connector_specs:
        part = scad.add_connector_rpart(
            part=part,
            connector=make_axis_connector_rconnector(
                connector_id=str(spec["connector_id"]),
                solid=solid,
                center_xy=spec["center_xy"],  # type: ignore[arg-type]
                target_z=float(spec["target_z"]),
                normal_z=float(spec["normal_z"]),
                name=spec.get("name"),  # type: ignore[arg-type]
                flip=bool(spec.get("flip", False)),
            ),
        )
    print(f"part_{part_id}: connectors={len(part.connectors)} material={bool(material)}")
    return part


def add_placement_axis_connector_rpart(
    *,
    part: scad.Part,
    connector_id: str,
    origin: tuple[float, float, float],
    name: str | None = None,
) -> scad.Part:
    """Attach a topology-free axis connector at an explicit local placement."""

    connector = scad.make_placement_connector_rconnector(
        connector_id=connector_id,
        placement=scad.make_placement_rplacement(origin=origin),
        name=name,
    )
    return scad.add_connector_rpart(part=part, connector=connector)


def _apply_tags(shape: scad.Solid, tags: Iterable[str]) -> scad.Solid:
    """Apply normalized tags through the public SimpleCAD tag API."""

    tagged = shape
    for tag in tags:
        tagged = scad.apply_tag(shape=tagged, tag=tag)
    return tagged


def _axis_face(
    *,
    label: str,
    solid: scad.Solid,
    center_xy: tuple[float, float],
    target_z: float,
    normal_z: float,
) -> scad.Face:
    candidates = []
    for face in ql.select(items=solid.get_faces()).all():
        normal = face.get_normal_at()
        if normal_z > 0.0 and normal.z < 0.65:
            continue
        if normal_z < 0.0 and normal.z > -0.65:
            continue
        center = face.get_center()
        xy_error = math.hypot(center.x - center_xy[0], center.y - center_xy[1])
        z_error = abs(center.z - target_z)
        candidates.append((z_error * 1000.0 + xy_error, face, center, normal))

    if not candidates:
        raise ValueError(f"no axial connector face found for {label}")

    _score, face, center, normal = min(candidates, key=lambda item: item[0])
    print(
        f"connector_{label}: center=({center.x:.3f},{center.y:.3f},{center.z:.3f}) "
        f"normal=({normal.x:.2f},{normal.y:.2f},{normal.z:.2f}) area={face.get_area():.3f}"
    )
    return face


def _ground_solid(*, label: str, solid: scad.Solid) -> None:
    faces = ql.select(items=solid.get_faces()).all()
    local_roles = [
        tag
        for tag in scad.list_tags(shape=solid, scope="local")
        if tag.startswith("role.")
    ]
    print(
        f"{label}: faces={len(faces)} local_roles={len(local_roles)} "
        f"volume={solid.get_volume():.3f} tags={','.join(scad.list_tags(shape=solid))}"
    )


def _ground_compound(*, label: str, compound: scad.Compound) -> None:
    """Print a compact QL-backed summary of an assembly preview compound."""

    solids = ql.select(items=compound.get_solids()).all()
    face_count = sum(len(ql.select(items=solid.get_faces()).all()) for solid in solids)
    volume = sum(solid.get_volume() for solid in solids)
    print(f"{label}: solids={len(solids)} faces={face_count} volume={volume:.3f}")
