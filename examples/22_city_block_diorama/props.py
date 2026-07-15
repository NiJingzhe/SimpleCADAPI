"""Reusable static public-realm props for the city-block diorama."""

from __future__ import annotations

import simplecadapi as scad

from common import add_box, add_cylinder, add_part, add_sphere, ground_assembly, make_part


def make_tree(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build a compact stylized street tree with layered foliage."""

    tree = scad.make_assembly_rassembly(assembly_id="street_tree", name="Layered street tree")
    tree = add_cylinder(
        assembly=tree,
        component_id="trunk",
        radius=1.0,
        height=8.0,
        center=(0.0, 0.0, 0.0),
        material=materials["wood"],
        name="Tree trunk",
        tags=("role.landscape",),
    )
    lower = scad.make_cone_rsolid(
        bottom_radius=4.2,
        height=8.0,
        top_radius=1.0,
        bottom_face_center=(0.0, 0.0, 5.5),
        axis=(0.0, 0.0, 1.0),
    )
    tree = add_part(
        assembly=tree,
        component_id="lower_canopy",
        part=make_part(
            part_id="lower_canopy",
            body=lower,
            material=materials["plant"],
            name="Dark conical foliage",
            tags=("role.landscape",),
        ),
    )
    tree = add_sphere(
        assembly=tree,
        component_id="upper_canopy",
        radius=3.4,
        center=(0.0, 0.0, 12.2),
        material=materials["plant_light"],
        name="Light upper foliage",
        tags=("role.landscape",),
    )
    ground_assembly(label="street_tree", assembly=tree)
    return tree


def make_street_lamp(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build a traditional two-headed street lamp."""

    lamp = scad.make_assembly_rassembly(assembly_id="street_lamp", name="Twin street lamp")
    lamp = add_cylinder(
        assembly=lamp,
        component_id="base",
        radius=1.3,
        height=1.2,
        center=(0.0, 0.0, 0.0),
        material=materials["steel"],
        name="Lamp base",
        tags=("role.street_furniture",),
    )
    lamp = add_cylinder(
        assembly=lamp,
        component_id="pole",
        radius=0.42,
        height=10.0,
        center=(0.0, 0.0, 1.0),
        material=materials["steel"],
        name="Lamp pole",
        tags=("role.street_furniture",),
    )
    lamp = add_box(
        assembly=lamp,
        component_id="crossarm",
        width=6.0,
        height=0.6,
        depth=0.6,
        center=(0.0, 0.0, 10.0),
        material=materials["steel"],
        name="Lamp crossarm",
        tags=("role.street_furniture",),
    )
    for index, x in enumerate((-2.5, 2.5), start=1):
        lamp = add_sphere(
            assembly=lamp,
            component_id=f"lantern_{index}",
            radius=1.05,
            center=(x, 0.0, 9.6),
            material=materials["lamp"],
            name=f"Lantern {index}",
            tags=("role.street_furniture", "role.light"),
        )
    ground_assembly(label="street_lamp", assembly=lamp)
    return lamp


def make_bench(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build a small slatted public bench."""

    bench = scad.make_assembly_rassembly(assembly_id="street_bench", name="Wood street bench")
    bench = add_box(
        assembly=bench,
        component_id="seat",
        width=8.0,
        height=2.4,
        depth=0.6,
        center=(0.0, 0.0, 2.5),
        material=materials["wood_light"],
        name="Bench seat",
        tags=("role.street_furniture",),
    )
    bench = add_box(
        assembly=bench,
        component_id="back",
        width=8.0,
        height=0.5,
        depth=2.8,
        center=(0.0, 2.1, 2.8),
        material=materials["wood_light"],
        name="Bench back",
        tags=("role.street_furniture",),
    )
    for index, x in enumerate((1.0, 7.0), start=1):
        bench = add_box(
            assembly=bench,
            component_id=f"leg_{index}",
            width=0.7,
            height=2.0,
            depth=2.5,
            center=(x, 0.2, 0.0),
            material=materials["steel"],
            name=f"Bench leg {index}",
            tags=("role.street_furniture",),
        )
    ground_assembly(label="street_bench", assembly=bench)
    return bench


def make_planter(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build a square masonry planter with a clipped shrub."""

    planter = scad.make_assembly_rassembly(assembly_id="street_planter", name="Shrub planter")
    planter = add_box(
        assembly=planter,
        component_id="pot",
        width=5.0,
        height=5.0,
        depth=2.0,
        center=(0.0, 0.0, 0.0),
        material=materials["brick_dark"],
        name="Planter pot",
        tags=("role.street_furniture",),
    )
    shrub = scad.make_cone_rsolid(
        bottom_radius=2.5,
        height=5.0,
        top_radius=1.3,
        bottom_face_center=(2.5, 2.5, 1.5),
        axis=(0.0, 0.0, 1.0),
    )
    planter = add_part(
        assembly=planter,
        component_id="shrub",
        part=make_part(
            part_id="shrub",
            body=shrub,
            material=materials["plant_light"],
            name="Clipped shrub",
            tags=("role.landscape",),
        ),
    )
    ground_assembly(label="street_planter", assembly=planter)
    return planter


def make_fountain(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build the central civic fountain as concentric static parts."""

    fountain = scad.make_assembly_rassembly(assembly_id="civic_fountain", name="Central fountain")
    fountain = add_cylinder(
        assembly=fountain,
        component_id="stone_base",
        radius=8.5,
        height=1.6,
        center=(0.0, 0.0, 0.0),
        material=materials["concrete"],
        name="Fountain stone base",
        tags=("role.street_furniture",),
    )
    fountain = add_cylinder(
        assembly=fountain,
        component_id="water_basin",
        radius=7.1,
        height=0.5,
        center=(0.0, 0.0, 1.5),
        material=materials["water"],
        name="Fountain water basin",
        tags=("role.water",),
    )
    fountain = add_cylinder(
        assembly=fountain,
        component_id="pedestal",
        radius=1.5,
        height=5.0,
        center=(0.0, 0.0, 1.6),
        material=materials["cream"],
        name="Fountain pedestal",
        tags=("role.street_furniture",),
    )
    fountain = add_sphere(
        assembly=fountain,
        component_id="finial",
        radius=1.8,
        center=(0.0, 0.0, 7.0),
        material=materials["water"],
        name="Fountain water finial",
        tags=("role.water",),
    )
    for index, (x, y) in enumerate(((3.8, 0.0), (-3.8, 0.0), (0.0, 3.8), (0.0, -3.8)), start=1):
        jet = scad.make_cone_rsolid(
            bottom_radius=0.55,
            height=3.2,
            top_radius=0.12,
            bottom_face_center=(x, y, 1.8),
            axis=(0.0, 0.0, 1.0),
        )
        fountain = add_part(
            assembly=fountain,
            component_id=f"water_jet_{index}",
            part=make_part(
                part_id=f"water_jet_{index}",
                body=jet,
                material=materials["water"],
                name=f"Static water jet {index}",
                tags=("role.water",),
            ),
        )
    ground_assembly(label="civic_fountain", assembly=fountain)
    return fountain
