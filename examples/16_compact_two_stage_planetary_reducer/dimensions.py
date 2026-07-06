"""Design constants for the compact two-stage planetary reducer."""

from __future__ import annotations

from dataclasses import dataclass


PLANET_COUNT = 3
MODULE = 0.75
PRESSURE_ANGLE = 20.0
HELIX_ANGLE = 27.0
GEAR_HEIGHT = 4.60
ADDENDUM_FACTOR = 1.0
CLEARANCE_FACTOR = 0.25
RING_RIM_THICKNESS = 1.90
FIXED_RING_HOUSING_SUPPORT_OVERLAP = 0.30
BACKLASH = 0.02

HOUSING_OUTER_RADIUS = 25.0
HOUSING_INNER_RADIUS = 21.70
HOUSING_DATUM_INNER_RADIUS = 20.95
HOUSING_DATUM_OUTER_RADIUS = 21.85
HOUSING_BOTTOM_Z = -15.0
HOUSING_HEIGHT = 30.0

INPUT_FLANGE_BOTTOM_Z = -15.0
INPUT_FLANGE_THICKNESS = 2.0
INPUT_FLANGE_BOSS_HEIGHT = 1.0
INPUT_FLANGE_TOP_Z = INPUT_FLANGE_BOTTOM_Z + INPUT_FLANGE_THICKNESS + INPUT_FLANGE_BOSS_HEIGHT
INPUT_FLANGE_OUTER_DIAMETER = 23.0
INPUT_FLANGE_INNER_DIAMETER = 3.0
INPUT_FLANGE_BOSS_OUTER_DIAMETER = 8.0
INPUT_FLANGE_HOLE_DIAMETER = 1.6
INPUT_FLANGE_HOLE_CIRCLE_DIAMETER = 17.0
INPUT_FLANGE_HOLE_COUNT = 6

OUTPUT_FLANGE_BOTTOM_Z = 12.0
OUTPUT_FLANGE_THICKNESS = 2.0
OUTPUT_FLANGE_BOSS_HEIGHT = 1.0
OUTPUT_FLANGE_TOP_Z = OUTPUT_FLANGE_BOTTOM_Z + OUTPUT_FLANGE_THICKNESS + OUTPUT_FLANGE_BOSS_HEIGHT
OUTPUT_FLANGE_OUTER_DIAMETER = 25.0
OUTPUT_FLANGE_INNER_DIAMETER = 3.4
OUTPUT_FLANGE_BOSS_OUTER_DIAMETER = 9.0
OUTPUT_FLANGE_HOLE_DIAMETER = 1.8
OUTPUT_FLANGE_HOLE_CIRCLE_DIAMETER = 18.5
OUTPUT_FLANGE_HOLE_COUNT = 6

INPUT_SHAFT_RADIUS = 1.45
STAGE1_CARRIER_SHAFT_RADIUS = 1.35
OUTPUT_SHAFT_RADIUS = 1.50

STAGE1_CARRIER_PLATE_BOTTOM_Z = -3.25
STAGE1_CARRIER_PLATE_THICKNESS = 1.65
STAGE1_PIN_BOTTOM_Z = -8.15
STAGE1_PIN_RADIUS = 1.10
STAGE1_PIN_LAND_RADIUS = 1.18
STAGE1_HUB_RADIUS = 3.40
STAGE1_ARM_WIDTH = 2.50
STAGE1_PAD_RADIUS = 4.10

STAGE2_CARRIER_PLATE_BOTTOM_Z = 6.45
STAGE2_CARRIER_PLATE_THICKNESS = 1.65
STAGE2_PIN_BOTTOM_Z = 1.45
STAGE2_PIN_RADIUS = 0.82
STAGE2_PIN_LAND_RADIUS = 0.93
STAGE2_HUB_RADIUS = 3.35
STAGE2_ARM_WIDTH = 2.35
STAGE2_PAD_RADIUS = 3.20

INPUT_BEARING_Z = -11.0
INTERMEDIATE_BEARING_Z = 0.0
OUTPUT_BEARING_Z = 10.8


@dataclass(frozen=True)
class StageSpec:
    """A tooth-count and axial-location spec for one planetary stage."""

    stage_id: str
    label: str
    sun_teeth: int
    planet_teeth: int
    bottom_z: float
    sun_helix_angle: float

    @property
    def ring_teeth(self) -> int:
        return self.sun_teeth + 2 * self.planet_teeth

    @property
    def planet_helix_angle(self) -> float:
        return -self.sun_helix_angle

    @property
    def ring_helix_angle(self) -> float:
        return self.planet_helix_angle

    @property
    def gear_height(self) -> float:
        return GEAR_HEIGHT

    @property
    def top_z(self) -> float:
        return self.bottom_z + self.gear_height

    @property
    def mid_z(self) -> float:
        return self.bottom_z + self.gear_height / 2.0

    @property
    def sun_pitch_radius(self) -> float:
        return MODULE * self.sun_teeth / 2.0

    @property
    def planet_pitch_radius(self) -> float:
        return MODULE * self.planet_teeth / 2.0

    @property
    def ring_pitch_radius(self) -> float:
        return MODULE * self.ring_teeth / 2.0

    @property
    def planet_center_radius(self) -> float:
        return MODULE * (self.sun_teeth + self.planet_teeth) / 2.0

    @property
    def fixed_ring_ratio(self) -> float:
        return 1.0 + self.ring_teeth / self.sun_teeth

    @property
    def ring_outer_radius(self) -> float:
        tooth_root_allowance = MODULE * (ADDENDUM_FACTOR + CLEARANCE_FACTOR)
        return self.ring_pitch_radius + tooth_root_allowance + RING_RIM_THICKNESS


@dataclass(frozen=True)
class BearingSpec:
    """A small radial ball bearing package."""

    bore_diameter: float
    outer_diameter: float
    width: float
    ball_diameter: float
    ball_count: int
    raceway_clearance: float = 0.03
    edge_chamfer: float = 0.0


STAGE_1 = StageSpec(
    stage_id="stage1",
    label="Stage 1",
    sun_teeth=12,
    planet_teeth=18,
    bottom_z=-8.40,
    sun_helix_angle=HELIX_ANGLE,
)
STAGE_2 = StageSpec(
    stage_id="stage2",
    label="Stage 2",
    sun_teeth=12,
    planet_teeth=12,
    bottom_z=1.20,
    sun_helix_angle=HELIX_ANGLE,
)

UNIVERSAL_RADIAL_BEARING = BearingSpec(
    bore_diameter=3.2,
    outer_diameter=6.6,
    width=2.0,
    ball_diameter=0.55,
    ball_count=8,
)
INPUT_SHAFT_BEARING = UNIVERSAL_RADIAL_BEARING
INTERMEDIATE_SHAFT_BEARING = UNIVERSAL_RADIAL_BEARING
OUTPUT_SHAFT_BEARING = UNIVERSAL_RADIAL_BEARING
STAGE1_PLANET_BEARING = UNIVERSAL_RADIAL_BEARING
STAGE2_PLANET_BEARING = UNIVERSAL_RADIAL_BEARING

TOTAL_REDUCTION = STAGE_1.fixed_ring_ratio * STAGE_2.fixed_ring_ratio
