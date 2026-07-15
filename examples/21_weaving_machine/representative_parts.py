"""Reusable geometry and static-assembly helpers for the representative machine."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import simplecadapi as scad

from .common import apply_tags, ground_assembly, make_connector, make_part


@dataclass(frozen=True)
class ComponentSpec:
    component_id: str
    item: scad.Part | scad.Assembly
    origin: tuple[float, float, float]
    name: str
    x_axis: tuple[float, float, float] = (1.0, 0.0, 0.0)
    y_axis: tuple[float, float, float] = (0.0, 1.0, 0.0)


def placement(
    origin: tuple[float, float, float],
    *,
    x_axis: tuple[float, float, float] = (1.0, 0.0, 0.0),
    y_axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
) -> scad.Placement:
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=x_axis,
        y_axis=y_axis,
    )


def make_box_part(
    *,
    part_id: str,
    name: str,
    size: tuple[float, float, float],
    material: scad.Material,
    tags: Iterable[str],
) -> scad.Part:
    body = scad.make_box_rsolid(
        width=size[0],
        height=size[1],
        depth=size[2],
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    body = apply_tags(shape=body, tags=tags)
    return make_part(
        part_id=part_id,
        name=name,
        body=body,
        material=material,
        connectors=(),
    )


def make_cylinder_part(
    *,
    part_id: str,
    name: str,
    radius: float,
    length: float,
    axis: tuple[float, float, float],
    material: scad.Material,
    tags: Iterable[str],
) -> scad.Part:
    body = scad.make_cylinder_rsolid(
        radius=radius,
        height=length,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=axis,
    )
    body = apply_tags(shape=body, tags=tags)
    return make_part(
        part_id=part_id,
        name=name,
        body=body,
        material=material,
        connectors=(),
    )


def make_spool_part(
    *,
    part_id: str,
    name: str,
    material: scad.Material,
    tags: Iterable[str],
    length: float = 70.0,
    core_radius: float = 22.0,
    flange_radius: float = 30.0,
) -> scad.Part:
    core = scad.make_cylinder_rsolid(
        radius=core_radius,
        height=length,
        bottom_face_center=(-length / 2.0, 0.0, 0.0),
        axis=(1.0, 0.0, 0.0),
    )
    flanges = tuple(
        scad.make_cylinder_rsolid(
            radius=flange_radius,
            height=7.0,
            bottom_face_center=(offset, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        for offset in (-length / 2.0, length / 2.0 - 7.0)
    )
    body = scad.union_rsolid(core, flanges, glue=False)
    body = apply_tags(shape=body, tags=tags)
    return make_part(
        part_id=part_id,
        name=name,
        body=body,
        material=material,
        connectors=(),
    )


def make_u_part(
    *,
    part_id: str,
    name: str,
    outer_width: float,
    height: float,
    depth: float,
    wall: float,
    material: scad.Material,
    tags: Iterable[str],
) -> scad.Part:
    base = scad.make_box_rsolid(
        width=outer_width,
        height=wall,
        depth=depth,
        bottom_face_center=(0.0, -(height - wall) / 2.0, 0.0),
    )
    sides = tuple(
        scad.make_box_rsolid(
            width=wall,
            height=height,
            depth=depth,
            bottom_face_center=(side * (outer_width - wall) / 2.0, 0.0, 0.0),
        )
        for side in (-1.0, 1.0)
    )
    body = scad.union_rsolid(base, sides, glue=False)
    body = apply_tags(shape=body, tags=tags)
    return make_part(
        part_id=part_id,
        name=name,
        body=body,
        material=material,
        connectors=(),
    )


def make_path_part(
    *,
    part_id: str,
    name: str,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    material: scad.Material,
    tags: Iterable[str],
) -> scad.Part:
    vector = tuple(end[index] - start[index] for index in range(3))
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 0.0:
        raise ValueError("path endpoints must be distinct")
    axis = tuple(value / length for value in vector)
    body = scad.make_cylinder_rsolid(
        radius=radius,
        height=length,
        bottom_face_center=start,
        axis=axis,
    )
    body = apply_tags(shape=body, tags=tags)
    return make_part(
        part_id=part_id,
        name=name,
        body=body,
        material=material,
        connectors=(),
    )


def make_static_assembly(
    *,
    assembly_id: str,
    name: str,
    components: Sequence[ComponentSpec],
    public_connectors: Iterable[scad.Connector] = (),
) -> scad.Assembly:
    if not components:
        raise ValueError(f"{assembly_id} requires at least one component")
    assembly = scad.make_assembly_rassembly(assembly_id=assembly_id, name=name)
    for component in components:
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=component.item,
            component_id=component.component_id,
            placement=placement(
                component.origin,
                x_axis=component.x_axis,
                y_axis=component.y_axis,
            ),
            name=component.name,
        )
        assembly = scad.ground_component_rassembly(
            assembly=assembly,
            component_id=component.component_id,
        )
    assembly = scad.add_connector_rassembly(
        assembly=assembly,
        connector=make_connector(
            connector_id="machine_mount",
            origin=(0.0, 0.0, 0.0),
            name="A00 skeleton mount",
        ),
    )
    for connector in public_connectors:
        assembly = scad.add_connector_rassembly(
            assembly=assembly,
            connector=connector,
        )
    assembly = scad.solve_assembly_constraints_rassembly(assembly=assembly, strict=True)
    ground_assembly(label=assembly_id, assembly=assembly)
    return assembly
