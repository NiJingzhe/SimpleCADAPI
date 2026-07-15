"""Candidate D0 materials; no candidate is a manufacturing release selection."""

from __future__ import annotations

import simplecadapi as scad


def make_guide_materials() -> dict[str, scad.Material]:
    materials = {
        "guide_polymer": scad.make_material_rmaterial(
            material_id="peek_candidate",
            name="PEEK candidate, validation pending",
            color=(0.62, 0.48, 0.24),
        ),
        "ceramic": scad.make_material_rmaterial(
            material_id="alumina_candidate",
            name="High-purity alumina candidate, validation pending",
            color=(0.94, 0.94, 0.90),
        ),
        "wear_rail": scad.make_material_rmaterial(
            material_id="uhmw_pe_candidate",
            name="UHMW-PE candidate, validation pending",
            color=(0.35, 0.55, 0.78),
        ),
    }
    print("guide_materials: candidates=" + ",".join(sorted(materials)))
    return materials


def make_machine_materials() -> dict[str, scad.Material]:
    """Return the complete representative-machine visualization palette."""

    materials = make_guide_materials()
    materials.update(
        {
            "structural_steel": scad.make_material_rmaterial(
                material_id="painted_structural_steel_candidate",
                name="Stress-relieved painted structural steel candidate",
                color=(0.20, 0.24, 0.30),
            ),
            "machined_aluminum": scad.make_material_rmaterial(
                material_id="machined_aluminum_candidate",
                name="Machined aluminum candidate",
                color=(0.52, 0.58, 0.64),
            ),
            "stainless": scad.make_material_rmaterial(
                material_id="polished_stainless_candidate",
                name="Polished stainless yarn-contact candidate",
                color=(0.78, 0.80, 0.82),
            ),
            "drive": scad.make_material_rmaterial(
                material_id="drive_envelope_candidate",
                name="Supplier-neutral drive envelope",
                color=(0.62, 0.12, 0.10),
            ),
            "belt": scad.make_material_rmaterial(
                material_id="belt_chain_envelope_candidate",
                name="Belt and chain envelope candidate",
                color=(0.10, 0.12, 0.13),
            ),
            "guard": scad.make_material_rmaterial(
                material_id="guard_panel_candidate",
                name="Machine guard panel candidate",
                color=(0.18, 0.42, 0.58),
            ),
            "clamp_pad": scad.make_material_rmaterial(
                material_id="segmented_clamp_pad_candidate",
                name="Segmented polyurethane clamp pad candidate",
                color=(0.16, 0.32, 0.20),
            ),
        }
    )
    print("machine_materials: candidates=" + ",".join(sorted(materials)))
    return materials
