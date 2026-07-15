"""Small functional helpers shared by the city-block builders."""

from __future__ import annotations

from collections.abc import Iterable
import math

import simplecadapi as scad
from simplecadapi import ql


def tagged(*, shape: scad.Solid, tags: Iterable[str]) -> scad.Solid:
    """Attach semantic role tags through the public functional API."""

    result = shape
    for tag in tags:
        result = scad.apply_tag(shape=result, tag=tag)
    return result


def make_part(
    *,
    part_id: str,
    body: scad.Solid,
    material: scad.Material,
    name: str,
    tags: Iterable[str] = (),
) -> scad.Part:
    """Tag, wrap, and color one semantic solid."""

    body = tagged(shape=body, tags=tags)
    part = scad.make_part_rpart(part_id=part_id, body=body, name=name)
    return scad.assign_material_rpart(part=part, material=material)


def add_part(
    *,
    assembly: scad.Assembly,
    component_id: str,
    part: scad.Part,
    placement: scad.Placement | None = None,
    name: str | None = None,
) -> scad.Assembly:
    """Add a part with an identity placement by default."""

    return scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id=component_id,
        placement=placement or scad.identity_placement_rplacement(),
        name=name,
    )


def add_box(
    *,
    assembly: scad.Assembly,
    component_id: str,
    width: float,
    height: float,
    depth: float,
    center: tuple[float, float, float],
    material: scad.Material,
    name: str,
    tags: Iterable[str] = (),
) -> scad.Assembly:
    """Create and add one axis-aligned box in the parent-local frame."""

    body = scad.make_box_rsolid(
        width=width,
        height=height,
        depth=depth,
        bottom_face_center=center,
    )
    part = make_part(
        part_id=f"{assembly.assembly_id}_{component_id}",
        body=body,
        material=material,
        name=name,
        tags=tags,
    )
    return add_part(assembly=assembly, component_id=component_id, part=part, name=name)


def add_cylinder(
    *,
    assembly: scad.Assembly,
    component_id: str,
    radius: float,
    height: float,
    center: tuple[float, float, float],
    material: scad.Material,
    name: str,
    tags: Iterable[str] = (),
) -> scad.Assembly:
    """Create and add one vertical cylinder."""

    body = scad.make_cylinder_rsolid(
        radius=radius,
        height=height,
        bottom_face_center=center,
        axis=(0.0, 0.0, 1.0),
    )
    part = make_part(
        part_id=f"{assembly.assembly_id}_{component_id}",
        body=body,
        material=material,
        name=name,
        tags=tags,
    )
    return add_part(assembly=assembly, component_id=component_id, part=part, name=name)


def add_sphere(
    *,
    assembly: scad.Assembly,
    component_id: str,
    radius: float,
    center: tuple[float, float, float],
    material: scad.Material,
    name: str,
    tags: Iterable[str] = (),
) -> scad.Assembly:
    """Create and add one spherical accent."""

    body = scad.make_sphere_rsolid(radius=radius, center=center)
    part = make_part(
        part_id=f"{assembly.assembly_id}_{component_id}",
        body=body,
        material=material,
        name=name,
        tags=tags,
    )
    return add_part(assembly=assembly, component_id=component_id, part=part, name=name)


def placement_xy(*, origin: tuple[float, float, float], angle_degrees: float = 0.0) -> scad.Placement:
    """Create a placement rotated around the scene's vertical axis."""

    angle = math.radians(angle_degrees)
    return scad.make_placement_rplacement(
        origin=origin,
        x_axis=(math.cos(angle), math.sin(angle), 0.0),
        y_axis=(-math.sin(angle), math.cos(angle), 0.0),
    )


def ground_solid(*, label: str, solid: scad.Solid) -> None:
    """Print a compact QL-backed fact for one construction step."""

    faces = ql.select(items=solid.get_faces()).all()
    print(
        f"{label}: faces={len(faces)} volume={solid.get_volume():.2f} "
        f"tags={','.join(scad.list_tags(shape=solid))}"
    )


def ground_assembly(
    *,
    label: str,
    assembly: scad.Assembly,
    record_result: bool = False,
) -> scad.Compound:
    """Flatten an assembly for grounding without creating an intermediate result."""

    if record_result:
        compound = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    else:
        with scad.suspend_graph_recording():
            compound = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    solids = ql.select(items=compound.get_solids()).all()
    print(
        f"{label}: components={len(assembly.component_ids())} "
        f"solids={len(solids)} volume={compound.get_volume():.2f}"
    )
    return compound


def make_colored_preview_solids(
    *,
    assembly: scad.Assembly,
    preview: scad.Compound,
) -> list[scad.Solid]:
    """Restore material groups on placed solids for the SDK screenshot renderer."""

    parts: list[scad.Part] = []

    def collect_parts(item: scad.Part | scad.Assembly) -> None:
        if isinstance(item, scad.Part):
            parts.append(item)
            return
        for component in item.components:
            collect_parts(component.item)

    collect_parts(assembly)
    solids = ql.select(items=preview.get_solids()).all()
    if len(parts) != len(solids):
        raise ValueError(
            f"preview material mapping mismatch: parts={len(parts)} solids={len(solids)}"
        )

    material_groups = {
        "city_wood": "role.preview.warm",
        "city_wood_light": "role.preview.warm",
        "city_furniture": "role.preview.warm",
        "city_interior_floor": "role.preview.warm",
        "city_interior_wall": "role.preview.warm",
        "city_counter": "role.preview.warm",
        "city_plaster": "role.preview.warm",
        "city_cream": "role.preview.warm",
        "city_sign_purple": "role.preview.purple",
        "city_sign_yellow": "role.preview.yellow",
        "city_lamp": "role.preview.yellow",
        "city_road_marking": "role.preview.yellow",
        "city_glass": "role.preview.blue",
        "city_glass_light": "role.preview.blue",
        "city_water": "role.preview.blue",
        "city_brick": "role.preview.brick",
        "city_brick_dark": "role.preview.brick",
        "city_sign_red": "role.preview.red",
        "city_upholstery": "role.preview.red",
        "city_plant": "role.preview.green",
        "city_plant_light": "role.preview.green",
        "city_ground": "role.preview.green",
        "city_earth": "role.preview.earth",
        "city_earth_trim": "role.preview.earth",
    }
    colored = []
    counts: dict[str, int] = {}
    for part, solid in zip(parts, solids):
        material_id = part.material.material_id if part.material is not None else ""
        tag = material_groups.get(material_id)
        if tag is not None:
            solid = scad.apply_tag(shape=solid, tag=tag)
            counts[tag] = counts.get(tag, 0) + 1
        colored.append(solid)
    print(
        "preview_color_groups: "
        + ",".join(f"{tag.rsplit('.', 1)[-1]}={counts.get(tag, 0)}" for tag in sorted(set(material_groups.values())))
    )
    return colored
