"""Top-down dimensions and placement inventory for Example 22."""

from __future__ import annotations

from dataclasses import dataclass


PLATFORM_WIDTH = 260.0
PLATFORM_DEPTH = 220.0
PLATFORM_BASE_Z = -10.0
PLATFORM_BASE_HEIGHT = 10.0
GROUND_TOP_Z = 0.0
ROAD_Z = 4.0
ROAD_HEIGHT = 1.5
SIDEWALK_Z = 5.5
BUILDING_Z = 6.8

MAIN_STREET_Y = 100.0
MAIN_STREET_WIDTH = 24.0
EAST_AVENUE_X = 118.0
EAST_AVENUE_WIDTH = 24.0


@dataclass(frozen=True)
class BuildingSpec:
    """A building envelope owned by the global layout."""

    code: str
    kind: str
    x: float
    y: float
    width: float
    depth: float
    floors: int
    floor_height: float
    rotation_degrees: float = 0.0

    @property
    def total_height(self) -> float:
        return self.floors * self.floor_height


BUILDINGS = (
    BuildingSpec("A", "glass_tower", 16.0, 150.0, 44.0, 48.0, 6, 11.0),
    BuildingSpec("H", "midrise_cafe", 68.0, 151.0, 40.0, 38.0, 3, 9.0),
    BuildingSpec("D", "noodle_bar", 16.0, 125.0, 44.0, 23.0, 1, 8.0),
    BuildingSpec("G", "game_cafe", 68.0, 125.0, 38.0, 23.0, 1, 8.0),
    BuildingSpec("B", "brick_residential", 164.0, 150.0, 44.0, 48.0, 5, 10.0),
    BuildingSpec("I", "blue_mixed_use", 212.0, 151.0, 34.0, 38.0, 2, 10.0),
    BuildingSpec("C", "noodle_bar", 164.0, 125.0, 42.0, 23.0, 1, 8.0),
    BuildingSpec("E", "corner_retail", 16.0, 18.0, 44.0, 42.0, 2, 10.0),
    BuildingSpec("J", "small_corner_shop", 68.0, 20.0, 38.0, 34.0, 2, 9.0),
    BuildingSpec("F", "office_block", 164.0, 18.0, 46.0, 42.0, 3, 10.0),
)


def validate_dimensions() -> None:
    """Fail early if a scene envelope is accidentally moved out of bounds."""

    if len(BUILDINGS) != 10:
        raise ValueError("Example 22 requires exactly ten labeled buildings")
    for spec in BUILDINGS:
        if spec.x < 8.0 or spec.y < 8.0:
            raise ValueError(f"building {spec.code} crosses the platform margin")
        if spec.x + spec.width > PLATFORM_WIDTH - 8.0:
            raise ValueError(f"building {spec.code} crosses the east platform edge")
        if spec.y + spec.depth > PLATFORM_DEPTH - 8.0:
            raise ValueError(f"building {spec.code} crosses the north platform edge")
        if spec.floors < 1 or spec.floor_height <= 0.0:
            raise ValueError(f"building {spec.code} has an invalid vertical envelope")
