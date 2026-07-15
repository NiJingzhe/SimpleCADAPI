"""Shared CAD construction, grounding, and semantic-signature helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import simplecadapi as scad
from simplecadapi import ql


def apply_tags(*, shape: scad.Solid, tags: Iterable[str]) -> scad.Solid:
    tagged = shape
    for tag in tags:
        tagged = scad.apply_tag(shape=tagged, tag=tag)
    return tagged


def make_connector(
    *,
    connector_id: str,
    origin: tuple[float, float, float],
    x_axis: tuple[float, float, float] = (1.0, 0.0, 0.0),
    y_axis: tuple[float, float, float] = (0.0, 1.0, 0.0),
    name: str | None = None,
) -> scad.Connector:
    return scad.make_placement_connector_rconnector(
        connector_id=connector_id,
        placement=scad.make_placement_rplacement(
            origin=origin,
            x_axis=x_axis,
            y_axis=y_axis,
        ),
        name=name,
    )


def make_part(
    *,
    part_id: str,
    name: str,
    body: scad.Solid,
    material: scad.Material,
    connectors: Iterable[scad.Connector],
) -> scad.Part:
    part = scad.make_part_rpart(part_id=part_id, body=body, name=name)
    part = scad.assign_material_rpart(part=part, material=material)
    for connector in connectors:
        part = scad.add_connector_rpart(part=part, connector=connector)
    ground_solid(label=part_id, solid=body)
    print(
        f"part_{part_id}: connectors={len(part.connector_ids())} "
        f"material={material.material_id}"
    )
    return part


def connector_ref(*, component_id: str, connector_id: str) -> scad.ConnectorRef:
    return scad.make_connector_ref_rconnectorref(
        component_id=component_id,
        connector_id=connector_id,
    )


def ground_solid(*, label: str, solid: scad.Solid) -> None:
    faces = ql.select(items=solid.get_faces()).all()
    print(
        f"{label}: faces={len(faces)} volume={solid.get_volume():.3f} "
        f"tags={','.join(scad.list_tags(shape=solid))}"
    )


def ground_assembly(*, label: str, assembly: scad.Assembly) -> None:
    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=assembly)
    worst_translation = max(
        (item.translation_error for item in report.residuals), default=0.0
    )
    worst_angle = max(
        (item.angular_error_degrees for item in report.residuals), default=0.0
    )
    print(
        f"{label}: solved={report.solved} components={len(assembly.component_ids())} "
        f"constraints={len(assembly.constraint_ids())} unsolved={len(report.unsolved_component_ids)} "
        f"max_translation={worst_translation:.6g} max_angle={worst_angle:.6g}"
    )


def semantic_signature(item: scad.Part | scad.Assembly) -> dict[str, Any]:
    """Return replay-comparable product and essential geometry facts."""

    if isinstance(item, scad.Part):
        return {
            "kind": "part",
            "id": item.part_id,
            "name": item.name,
            "material": item.material.material_id if item.material else None,
            "volume": round(item.body.get_volume(), 9),
            "tags": scad.list_tags(shape=item.body),
            "connectors": [
                {
                    "id": connector.connector_id,
                    "placement": connector.placement.to_dict(),
                }
                for connector in item.connectors
            ],
        }
    return {
        "kind": "assembly",
        "id": item.assembly_id,
        "name": item.name,
        "grounded": list(item.grounded_component_ids),
        "connectors": [
            {
                "id": connector.connector_id,
                "placement": connector.placement.to_dict(),
            }
            for connector in item.connectors
        ],
        "constraints": [constraint.to_dict() for constraint in item.constraints],
        "components": [
            {
                "id": component.component_id,
                "name": component.name,
                "placement": component.placement.to_dict(),
                "item": semantic_signature(component.item),
            }
            for component in item.components
        ],
    }
