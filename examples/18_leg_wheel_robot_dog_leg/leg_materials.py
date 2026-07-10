"""Materials for the leg-wheel robot dog leg example."""

from __future__ import annotations

import simplecadapi as scad


def make_leg_materials_rdict() -> dict[str, scad.Material]:
    """Create reusable material definitions for the leg assembly."""

    return {
        "actuator_case": scad.make_material_rmaterial(
            material_id="leg_actuator_dark_anodized_aluminum",
            name="Dark anodized actuator housings",
            density=2.70,
            density_unit="g/cm^3",
            color=(0.28, 0.32, 0.34),
        ),
        "motor": scad.make_material_rmaterial(
            material_id="leg_motor_black_shell",
            name="Black motor shell",
            density=2.20,
            density_unit="g/cm^3",
            color=(0.07, 0.08, 0.09),
        ),
        "link": scad.make_material_rmaterial(
            material_id="leg_link_turquoise_7075",
            name="Turquoise anodized 7075 link plates",
            density=2.81,
            density_unit="g/cm^3",
            color=(0.00, 0.78, 0.72),
        ),
        "linkage": scad.make_material_rmaterial(
            material_id="leg_linkage_magenta_ti",
            name="Magenta titanium linkage hardware",
            density=4.43,
            density_unit="g/cm^3",
            color=(0.95, 0.18, 0.62),
        ),
        "bracket": scad.make_material_rmaterial(
            material_id="leg_bracket_white_composite",
            name="White composite body mount brackets",
            density=1.55,
            density_unit="g/cm^3",
            color=(0.92, 0.90, 0.84),
        ),
        "tire": scad.make_material_rmaterial(
            material_id="leg_wheel_rubber",
            name="Dark rubber tire",
            density=1.15,
            density_unit="g/cm^3",
            color=(0.02, 0.02, 0.02),
        ),
    }
