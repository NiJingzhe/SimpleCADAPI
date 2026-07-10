"""Material records for structural, magnetic, and electronic parts."""

from __future__ import annotations

import simplecadapi as scad


def make_actuator_materials_rdict() -> dict[str, scad.Material]:
    """Create the materials used by Case 20."""

    materials = {
        "housing": scad.make_material_rmaterial(
            material_id="aluminum_6061_t6",
            name="Hard-anodized 6061-T6 aluminum",
            density=2.70e-6,
            density_unit="kg/mm^3",
            color=(0.12, 0.15, 0.18),
        ),
        "carrier": scad.make_material_rmaterial(
            material_id="aluminum_7075_t6",
            name="7075-T6 aluminum",
            density=2.81e-6,
            density_unit="kg/mm^3",
            color=(0.72, 0.74, 0.78),
        ),
        "gear": scad.make_material_rmaterial(
            material_id="case_hardened_gear_steel",
            name="Case-hardened alloy gear steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.46, 0.50, 0.56),
        ),
        "electrical_steel": scad.make_material_rmaterial(
            material_id="laminated_electrical_steel",
            name="Laminated electrical steel",
            density=7.65e-6,
            density_unit="kg/mm^3",
            color=(0.20, 0.27, 0.35),
        ),
        "copper": scad.make_material_rmaterial(
            material_id="enameled_copper",
            name="Enameled copper winding",
            density=8.96e-6,
            density_unit="kg/mm^3",
            color=(0.78, 0.27, 0.06),
        ),
        "magnet": scad.make_material_rmaterial(
            material_id="ndfeb_n42sh",
            name="NdFeB N42SH magnet",
            density=7.50e-6,
            density_unit="kg/mm^3",
            color=(0.14, 0.34, 0.75),
        ),
        "pcb": scad.make_material_rmaterial(
            material_id="fr4_copper_laminate",
            name="FR-4 copper laminate",
            density=1.85e-6,
            density_unit="kg/mm^3",
            color=(0.03, 0.42, 0.16),
        ),
        "terminal": scad.make_material_rmaterial(
            material_id="high_temperature_terminal_polymer",
            name="High-temperature connector polymer",
            density=1.45e-6,
            density_unit="kg/mm^3",
            color=(0.88, 0.70, 0.16),
        ),
    }
    print("materials: " + ",".join(sorted(materials)))
    return materials
