"""Materials for the leg-wheel robot dog leg example."""

from __future__ import annotations

import simplecadapi as scad


def make_leg_materials_rdict() -> dict[str, scad.Material]:
    """Create reusable material definitions for the leg assembly."""

    return {
        "link": scad.make_material_rmaterial(
            material_id="leg_link_turquoise_7075",
            name="Turquoise anodized 7075 link plates",
            density=2.81e-6,
            density_unit="kg/mm^3",
            color=(0.02, 0.67, 0.78),
        ),
        "linkage": scad.make_material_rmaterial(
            material_id="leg_linkage_orange_ti",
            name="Orange anodized titanium linkage hardware",
            density=4.43e-6,
            density_unit="kg/mm^3",
            color=(0.95, 0.25, 0.06),
        ),
        "bracket": scad.make_material_rmaterial(
            material_id="leg_bracket_violet_7075",
            name="Violet anodized 7075 actuator clamps",
            density=2.81e-6,
            density_unit="kg/mm^3",
            color=(0.48, 0.19, 0.76),
        ),
        "wheel_hub": scad.make_material_rmaterial(
            material_id="leg_wheel_hub_gold_7075",
            name="Gold anodized 7075 wheel hub",
            density=2.81e-6,
            density_unit="kg/mm^3",
            color=(0.94, 0.62, 0.05),
        ),
        "fastener": scad.make_material_rmaterial(
            material_id="leg_fastener_black_12_9_steel",
            name="Black oxide class 12.9 fastener steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.08, 0.10, 0.13),
        ),
        "bushing": scad.make_material_rmaterial(
            material_id="leg_bushing_bronze",
            name="Oil-impregnated bearing bronze",
            density=8.80e-6,
            density_unit="kg/mm^3",
            color=(0.63, 0.34, 0.12),
        ),
        "tire": scad.make_material_rmaterial(
            material_id="leg_wheel_rubber",
            name="Dark rubber tire",
            density=1.15e-6,
            density_unit="kg/mm^3",
            color=(0.025, 0.03, 0.035),
        ),
    }
