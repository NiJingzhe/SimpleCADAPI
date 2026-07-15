"""Global composition for the static city-block diorama."""

from __future__ import annotations

import simplecadapi as scad

from buildings import make_building
from common import placement_xy
from dimensions import BUILDING_Z, BUILDINGS, ROAD_Z, SIDEWALK_Z
from props import make_bench, make_fountain, make_planter, make_street_lamp, make_tree
from terrain import make_terrain


def make_city_block_assembly(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build the complete city scene from reusable architectural subassemblies."""

    city = scad.make_assembly_rassembly(
        assembly_id="city_block_diorama",
        name="Example 22 static city block diorama",
    )

    terrain = make_terrain(materials=materials)
    city = scad.add_component_rassembly(
        assembly=city,
        item=terrain,
        component_id="terrain",
        placement=scad.identity_placement_rplacement(),
        name="Layered city terrain",
    )

    for spec in BUILDINGS:
        building = make_building(spec=spec, materials=materials)
        city = scad.add_component_rassembly(
            assembly=city,
            item=building,
            component_id=f"building_{spec.code.lower()}",
            placement=placement_xy(
                origin=(spec.x + spec.width / 2.0, spec.y + spec.depth / 2.0, BUILDING_Z),
                angle_degrees=spec.rotation_degrees,
            ),
            name=f"Building {spec.code} {spec.kind.replace('_', ' ')}",
        )
    print(f"city_buildings: count={len(BUILDINGS)} labels={','.join(spec.code for spec in BUILDINGS)}")

    tree = make_tree(materials=materials)
    tree_positions = (
        (12.0, 92.0),
        (108.0, 90.0),
        (151.0, 90.0),
        (238.0, 92.0),
        (112.0, 177.0),
        (150.0, 177.0),
        (112.0, 42.0),
        (150.0, 42.0),
    )
    for index, (x, y) in enumerate(tree_positions, start=1):
        city = scad.add_component_rassembly(
            assembly=city,
            item=tree,
            component_id=f"tree_{index}",
            placement=placement_xy(origin=(x, y, SIDEWALK_Z + 0.7)),
            name=f"Street tree {index}",
        )

    lamp = make_street_lamp(materials=materials)
    lamp_positions = ((92.0, 112.0), (168.0, 112.0), (130.0, 78.0), (130.0, 146.0))
    for index, (x, y) in enumerate(lamp_positions, start=1):
        city = scad.add_component_rassembly(
            assembly=city,
            item=lamp,
            component_id=f"lamp_{index}",
            placement=placement_xy(origin=(x, y, ROAD_Z + 0.2)),
            name=f"Street lamp {index}",
        )

    bench = make_bench(materials=materials)
    for index, (x, y, angle) in enumerate(
        ((113.0, 119.0, 0.0), (147.0, 119.0, 180.0), (122.0, 105.0, 90.0), (138.0, 105.0, -90.0)),
        start=1,
    ):
        city = scad.add_component_rassembly(
            assembly=city,
            item=bench,
            component_id=f"bench_{index}",
            placement=placement_xy(origin=(x, y, SIDEWALK_Z + 0.6), angle_degrees=angle),
            name=f"Plaza bench {index}",
        )

    planter = make_planter(materials=materials)
    for index, (x, y) in enumerate(((103.0, 121.0), (157.0, 121.0), (130.0, 96.0), (130.0, 128.0)), start=1):
        city = scad.add_component_rassembly(
            assembly=city,
            item=planter,
            component_id=f"planter_{index}",
            placement=placement_xy(origin=(x, y, SIDEWALK_Z + 0.7)),
            name=f"Plaza planter {index}",
        )

    fountain = make_fountain(materials=materials)
    city = scad.add_component_rassembly(
        assembly=city,
        item=fountain,
        component_id="central_fountain",
        placement=placement_xy(origin=(130.0, 112.0, SIDEWALK_Z + 0.5)),
        name="Central fountain",
    )

    print(
        f"city_components: top_level={len(city.component_ids())} "
        "vehicles=0 interiors=required"
    )
    return city
