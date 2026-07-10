"""Materials for the four-planet planetary reducer example."""

from __future__ import annotations

import simplecadapi as scad


def make_materials_rdict() -> dict[str, scad.Material]:
    """Create simple material definitions for the exposed gearset."""

    materials = {
        "gear": scad.make_material_rmaterial(
            material_id="case_hardened_steel",
            name="Case hardened gear steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.70, 0.70, 0.74),
        ),
        "ring": scad.make_material_rmaterial(
            material_id="nitrided_internal_ring_steel",
            name="Nitrided internal ring steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.44, 0.46, 0.50),
        ),
        "carrier": scad.make_material_rmaterial(
            material_id="aluminum_7075_t6",
            name="7075-T6 aluminum carrier",
            density=2.81e-6,
            density_unit="kg/mm^3",
            color=(0.14, 0.48, 0.70),
        ),
    }
    print("materials: " + ",".join(sorted(materials)))
    return materials
