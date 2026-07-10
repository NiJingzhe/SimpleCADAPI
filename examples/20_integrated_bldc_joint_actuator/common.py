"""Shared construction, tagging, connector, and grounding helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable

import simplecadapi as scad
from simplecadapi import ql


def apply_tags(*, shape: scad.Solid, tags: Iterable[str]) -> scad.Solid:
    """Apply semantic tags through the public functional API."""

    tagged = shape
    for tag in tags:
        tagged = scad.apply_tag(shape=tagged, tag=tag)
    return tagged


def make_annulus_rsolid(
    *,
    outer_radius: float,
    inner_radius: float,
    bottom_z: float,
    height: float,
    tags: Iterable[str],
) -> scad.Solid:
    """Create a strict single-solid annular cylinder."""

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
    annulus = scad.cut_rsolid(outer, bore, skip_non_intersecting=False)
    return apply_tags(shape=annulus, tags=tags)


def make_axis_part_rpart(
    *,
    part_id: str,
    body: scad.Solid,
    name: str,
    material: scad.Material,
    connectors: Iterable[tuple[str, tuple[float, float, float], str]],
) -> scad.Part:
    """Create a single-body part with stable placement-based axis datums."""

    part = scad.make_part_rpart(part_id=part_id, body=body, name=name)
    part = scad.assign_material_rpart(part=part, material=material)
    connector_count = 0
    for connector_id, origin, connector_name in connectors:
        connector = scad.make_placement_connector_rconnector(
            connector_id=connector_id,
            placement=scad.make_placement_rplacement(origin=origin),
            name=connector_name,
        )
        part = scad.add_connector_rpart(part=part, connector=connector)
        connector_count += 1
    ground_solid(label=part_id, solid=body)
    print(f"part_{part_id}: connectors={connector_count} material={material.material_id}")
    return part


def make_z_rotation_rplacement(
    *,
    origin: tuple[float, float, float],
    angle_degrees: float,
) -> scad.Placement:
    """Return a right-handed placement rotated about Z."""

    angle = math.radians(angle_degrees)
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=(math.cos(angle), math.sin(angle), 0.0),
        y_axis=(-math.sin(angle), math.cos(angle), 0.0),
    )


def radial_centers(*, count: int, radius: float, angle_offset: float = 0.0):
    """Yield index, angle in degrees, and XY center on a bolt/pole circle."""

    for index in range(count):
        angle_degrees = angle_offset + 360.0 * index / count
        angle = math.radians(angle_degrees)
        yield index, angle_degrees, (radius * math.cos(angle), radius * math.sin(angle))


def make_axial_hole_cutters_rsolids(
    *,
    count: int,
    pcd: float,
    hole_radius: float,
    bottom_z: float,
    height: float,
    angle_offset: float = 0.0,
) -> list[scad.Solid]:
    """Create equally spaced axial hole cutters."""

    cutters = []
    for _index, _angle, center in radial_centers(
        count=count,
        radius=pcd / 2.0,
        angle_offset=angle_offset,
    ):
        cutters.append(
            scad.make_cylinder_rsolid(
                radius=hole_radius,
                height=height,
                bottom_face_center=(center[0], center[1], bottom_z),
                axis=(0.0, 0.0, 1.0),
            )
        )
    return cutters


def ground_solid(*, label: str, solid: scad.Solid) -> None:
    """Print a concise QL-backed solid summary."""

    faces = ql.select(items=solid.get_faces()).all()
    role_faces = ql.select(items=faces).where(ql.tag(pattern="role.*")).all()
    print(
        f"{label}: faces={len(faces)} role_faces={len(role_faces)} "
        f"volume={solid.get_volume():.3f} tags={','.join(scad.list_tags(shape=solid))}"
    )


def ground_compound(*, label: str, compound: scad.Compound) -> None:
    """Print a concise QL-backed assembly projection summary."""

    solids = ql.select(items=compound.get_solids()).all()
    faces = sum(len(ql.select(items=solid.get_faces()).all()) for solid in solids)
    volume = sum(solid.get_volume() for solid in solids)
    print(f"{label}: solids={len(solids)} faces={faces} volume={volume:.3f}")


def connector_ref(*, component_id: str, connector_id: str) -> scad.ConnectorRef:
    """Create a component-scoped connector reference."""

    return scad.make_connector_ref_rconnectorref(
        component_id=component_id,
        connector_id=connector_id,
    )


def ground_constraint_report(*, label: str, assembly: scad.Assembly) -> None:
    """Print solved state and only non-zero residual facts."""

    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=assembly)
    worst_translation = max((item.translation_error for item in report.residuals), default=0.0)
    worst_angle = max((item.angular_error_degrees for item in report.residuals), default=0.0)
    print(
        f"{label}_constraints: solved={report.solved} components={len(assembly.component_ids())} "
        f"constraints={len(assembly.constraint_ids())} unsolved={len(report.unsolved_component_ids)} "
        f"max_translation={worst_translation:.6g} max_angle={worst_angle:.6g}"
    )
