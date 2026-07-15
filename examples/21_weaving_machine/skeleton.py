"""A00 master datums for the whole machine."""

from __future__ import annotations

import simplecadapi as scad

from .common import make_connector
from .inventory import TOP_LEVEL_COMPONENT_IDS
from .parameters import MachineParameters
from .representative_parts import (
    ComponentSpec,
    make_box_part,
    make_static_assembly,
)


def make_machine_skeleton(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    datum_block = make_box_part(
        part_id="a00_datum_block",
        name="A/B/C/D physical datum witness",
        size=(36.0, 36.0, 18.0),
        material=materials["machined_aluminum"],
        tags=(
            "role.machine_skeleton",
            "anchor.datum.a",
            "anchor.datum.b",
            "anchor.datum.c",
            "anchor.datum.d",
        ),
    )
    components = [
        ComponentSpec(
            "datum_block",
            datum_block,
            (0.0, 0.0, parameters.base_datum_z.value + 40.0),
            datum_block.name,
        ),
    ]
    mount_connectors = tuple(
        make_connector(
            connector_id=f"mount_{component_id}",
            origin=(0.0, 0.0, 0.0),
            name=f"Skeleton mount for {component_id}",
        )
        for component_id in TOP_LEVEL_COMPONENT_IDS
        if component_id != "a00_skeleton"
    )
    skeleton = make_static_assembly(
        assembly_id="a00_machine_skeleton",
        name="A00 master machine datums",
        components=components,
        public_connectors=mount_connectors,
    )
    print(
        "a00_skeleton: "
        f"stations={parameters.x_guide.value:g},{parameters.x_needle.value:g},"
        f"{parameters.x_rapier.value:g},0,{parameters.x_takeup.value:g} "
        "process_reference_geometry=omitted"
    )
    return skeleton
