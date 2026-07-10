"""Shared helpers for Example 19."""

from __future__ import annotations

import math

import simplecadapi as scad
from simplecadapi import ql


def make_z_rotation_rplacement(
    *,
    origin: tuple[float, float, float],
    angle_degrees: float,
) -> scad.Placement:
    """Create a placement rotated about local Z and translated to origin."""

    angle = math.radians(angle_degrees)
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=(math.cos(angle), math.sin(angle), 0.0),
        y_axis=(-math.sin(angle), math.cos(angle), 0.0),
    )


def add_axis_connector_rpart(
    *,
    part: scad.Part,
    connector_id: str,
    origin: tuple[float, float, float],
    name: str,
) -> scad.Part:
    """Attach a topology-free Z-axis datum connector to a part."""

    connector = scad.make_placement_connector_rconnector(
        connector_id=connector_id,
        placement=scad.make_placement_rplacement(
            origin=origin,
            x_axis=(1.0, 0.0, 0.0),
            y_axis=(0.0, 1.0, 0.0),
        ),
        name=name,
    )
    return scad.add_connector_rpart(part=part, connector=connector)


def make_axis_part_rpart(
    *,
    part_id: str,
    body: scad.Solid,
    name: str,
    material: scad.Material,
    connector_specs: tuple[tuple[str, tuple[float, float, float], str], ...],
) -> scad.Part:
    """Wrap one solid as a part and attach named axis connectors."""

    part = scad.make_part_rpart(part_id=part_id, body=body, name=name)
    part = scad.assign_material_rpart(part=part, material=material)
    for connector_id, origin, connector_name in connector_specs:
        part = add_axis_connector_rpart(
            part=part,
            connector_id=connector_id,
            origin=origin,
            name=connector_name,
        )
    print(f"part_{part_id}: connectors={len(part.connectors)} volume={body.get_volume():.3f}")
    return part


def ground_solid(*, label: str, solid: scad.Solid) -> None:
    """Print a small QL-grounded summary for a generated solid."""

    faces = ql.select(items=solid.get_faces()).all()
    edges = ql.select(items=solid.get_edges()).all()
    print(
        f"{label}: faces={len(faces)} edges={len(edges)} "
        f"volume={solid.get_volume():.3f} tags={','.join(scad.list_tags(shape=solid))}"
    )
