"""Design constants for the four-planet single-stage planetary reducer."""

from __future__ import annotations

import math


MODULE = 1.5
PRESSURE_ANGLE = 20.0
GEAR_HEIGHT = 8.0
BACKLASH = 0.04
ADDENDUM_FACTOR = 1.0
CLEARANCE_FACTOR = 0.25

SUN_TEETH = 24
PLANET_TEETH = 18
PLANET_COUNT = 4
RING_TEETH = SUN_TEETH + 2 * PLANET_TEETH

SUN_PITCH_RADIUS = MODULE * SUN_TEETH / 2.0
PLANET_PITCH_RADIUS = MODULE * PLANET_TEETH / 2.0
RING_PITCH_RADIUS = MODULE * RING_TEETH / 2.0
PLANET_CENTER_RADIUS = SUN_PITCH_RADIUS + PLANET_PITCH_RADIUS
FIXED_RING_REDUCTION = 1.0 + RING_TEETH / SUN_TEETH

RING_RIM_THICKNESS = 4.0
GEAR_AXIS_Z = GEAR_HEIGHT / 2.0

SUN_BORE_RADIUS = 3.0
PLANET_PIN_RADIUS = 2.6
PLANET_PIN_CLEARANCE_RADIUS = 3.2

CARRIER_BOTTOM_Z = -5.0
CARRIER_THICKNESS = 4.0
CARRIER_HUB_RADIUS = 10.0
CARRIER_ARM_WIDTH = 6.0
CARRIER_PIN_BOSS_RADIUS = 5.2
CARRIER_PIN_HEIGHT = GEAR_HEIGHT + 6.0


def planet_angle_degrees(*, index: int) -> float:
    """Return the equally spaced carrier angle for one planet index."""

    return 360.0 * index / PLANET_COUNT


def planet_center_xy(*, index: int) -> tuple[float, float]:
    """Return the XY pitch-center location for one planet."""

    angle = math.radians(planet_angle_degrees(index=index))
    return (
        PLANET_CENTER_RADIUS * math.cos(angle),
        PLANET_CENTER_RADIUS * math.sin(angle),
    )
