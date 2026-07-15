"""Layered terrain, streets, sidewalks, and markings for Example 22."""

from __future__ import annotations

import simplecadapi as scad

from common import add_box, ground_assembly
from dimensions import (
    EAST_AVENUE_WIDTH,
    EAST_AVENUE_X,
    MAIN_STREET_WIDTH,
    MAIN_STREET_Y,
    PLATFORM_BASE_HEIGHT,
    PLATFORM_BASE_Z,
    PLATFORM_DEPTH,
    PLATFORM_WIDTH,
    ROAD_HEIGHT,
    ROAD_Z,
    SIDEWALK_Z,
)


def make_terrain(*, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build the cutaway platform and public circulation surfaces."""

    terrain = scad.make_assembly_rassembly(
        assembly_id="city_terrain",
        name="Layered cutaway terrain and street grid",
    )
    terrain = add_box(
        assembly=terrain,
        component_id="earth_base",
        width=PLATFORM_WIDTH,
        height=PLATFORM_DEPTH,
        depth=PLATFORM_BASE_HEIGHT,
        center=(PLATFORM_WIDTH / 2.0, PLATFORM_DEPTH / 2.0, PLATFORM_BASE_Z),
        material=materials["earth"],
        name="Cutaway earth base",
        tags=("role.terrain",),
    )
    terrain = add_box(
        assembly=terrain,
        component_id="lower_trim",
        width=PLATFORM_WIDTH + 4.0,
        height=PLATFORM_DEPTH + 4.0,
        depth=1.4,
        center=(PLATFORM_WIDTH / 2.0, PLATFORM_DEPTH / 2.0, PLATFORM_BASE_Z - 1.2),
        material=materials["earth_trim"],
        name="Lower display-base trim",
        tags=("role.terrain",),
    )
    terrain = add_box(
        assembly=terrain,
        component_id="ground_cap",
        width=PLATFORM_WIDTH,
        height=PLATFORM_DEPTH,
        depth=4.0,
        center=(PLATFORM_WIDTH / 2.0, PLATFORM_DEPTH / 2.0, 0.0),
        material=materials["ground"],
        name="City ground cap",
        tags=("role.terrain",),
    )

    terrain = add_box(
        assembly=terrain,
        component_id="main_street",
        width=PLATFORM_WIDTH,
        height=MAIN_STREET_WIDTH,
        depth=ROAD_HEIGHT,
        center=(PLATFORM_WIDTH / 2.0, MAIN_STREET_Y + MAIN_STREET_WIDTH / 2.0, ROAD_Z),
        material=materials["road"],
        name="Main Street",
        tags=("role.road",),
    )
    terrain = add_box(
        assembly=terrain,
        component_id="east_avenue",
        width=EAST_AVENUE_WIDTH,
        height=PLATFORM_DEPTH,
        depth=ROAD_HEIGHT,
        center=(EAST_AVENUE_X + EAST_AVENUE_WIDTH / 2.0, PLATFORM_DEPTH / 2.0, ROAD_Z),
        material=materials["road"],
        name="East Avenue",
        tags=("role.road",),
    )
    perimeter_roads = (
        ("south_edge_road", PLATFORM_WIDTH, 10.0, (PLATFORM_WIDTH / 2.0, 7.0, ROAD_Z)),
        ("north_edge_road", PLATFORM_WIDTH, 10.0, (PLATFORM_WIDTH / 2.0, 213.0, ROAD_Z)),
        ("west_edge_road", 10.0, PLATFORM_DEPTH, (7.0, PLATFORM_DEPTH / 2.0, ROAD_Z)),
        ("east_edge_road", 10.0, PLATFORM_DEPTH, (253.0, PLATFORM_DEPTH / 2.0, ROAD_Z)),
    )
    for component_id, width, height, center in perimeter_roads:
        terrain = add_box(
            assembly=terrain,
            component_id=component_id,
            width=width,
            height=height,
            depth=ROAD_HEIGHT,
            center=center,
            material=materials["road"],
            name=component_id.replace("_", " ").title(),
            tags=("role.road",),
        )

    sidewalk_blocks = (
        ("northwest_walk", 104.0, 80.0, (64.0, 166.0, SIDEWALK_Z)),
        ("northeast_walk", 104.0, 80.0, (196.0, 166.0, SIDEWALK_Z)),
        ("southwest_walk", 104.0, 82.0, (64.0, 56.0, SIDEWALK_Z)),
        ("southeast_walk", 104.0, 82.0, (196.0, 56.0, SIDEWALK_Z)),
    )
    for component_id, width, height, center in sidewalk_blocks:
        terrain = add_box(
            assembly=terrain,
            component_id=component_id,
            width=width,
            height=height,
            depth=1.3,
            center=center,
            material=materials["sidewalk"],
            name=component_id.replace("_", " ").title(),
            tags=("role.sidewalk",),
        )

    terrain = add_box(
        assembly=terrain,
        component_id="civic_plaza",
        width=30.0,
        height=30.0,
        depth=1.0,
        center=(130.0, 112.0, SIDEWALK_Z + 0.5),
        material=materials["cream"],
        name="Intersection civic plaza",
        tags=("role.sidewalk",),
    )

    for index, x in enumerate(range(20, 244, 18), start=1):
        terrain = add_box(
            assembly=terrain,
            component_id=f"main_lane_mark_{index}",
            width=9.0,
            height=0.7,
            depth=0.15,
            center=(float(x), 112.0, ROAD_Z + ROAD_HEIGHT),
            material=materials["road_marking"],
            name=f"Main Street lane mark {index}",
            tags=("role.road_marking",),
        )
    for index, y in enumerate(range(20, 204, 18), start=1):
        terrain = add_box(
            assembly=terrain,
            component_id=f"avenue_lane_mark_{index}",
            width=0.7,
            height=9.0,
            depth=0.15,
            center=(130.0, float(y), ROAD_Z + ROAD_HEIGHT),
            material=materials["road_marking"],
            name=f"East Avenue lane mark {index}",
            tags=("role.road_marking",),
        )

    stripe_index = 0
    for x in (109.0, 145.0):
        for offset in range(0, 20, 4):
            stripe_index += 1
            terrain = add_box(
                assembly=terrain,
                component_id=f"crosswalk_vertical_{stripe_index}",
                width=2.2,
                height=8.0,
                depth=0.16,
                center=(x, 103.0 + offset, ROAD_Z + ROAD_HEIGHT + 0.02),
                material=materials["white"],
                name=f"Vertical crosswalk stripe {stripe_index}",
                tags=("role.road_marking",),
            )
    for y in (91.0, 129.0):
        for offset in range(0, 20, 4):
            stripe_index += 1
            terrain = add_box(
                assembly=terrain,
                component_id=f"crosswalk_horizontal_{stripe_index}",
                width=8.0,
                height=2.2,
                depth=0.16,
                center=(121.0 + offset, y, ROAD_Z + ROAD_HEIGHT + 0.02),
                material=materials["white"],
                name=f"Horizontal crosswalk stripe {stripe_index}",
                tags=("role.road_marking",),
            )

    ground_assembly(label="city_terrain", assembly=terrain)
    return terrain
