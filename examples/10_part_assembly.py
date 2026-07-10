"""Build a hydraulic rod assembly with separate sleeve and piston-rod parts."""

from __future__ import annotations

import json
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql


OUT_DIR = Path("examples/out/hydraulic_rod_assembly")


def build_hydraulic_rod_assembly():
    flange_holes = [
        (0.0, 16.0),
        (16.0, 0.0),
        (0.0, -16.0),
        (-16.0, 0.0),
    ]

    with scad.GraphSession() as session:
        barrel = scad.make_cylinder_rsolid(
            radius=16.0,
            height=120.0,
            bottom_face_center=(-60.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        rod_gland_flange = scad.make_cylinder_rsolid(
            radius=22.0,
            height=12.0,
            bottom_face_center=(50.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        rod_gland_nose = scad.make_cylinder_rsolid(
            radius=13.0,
            height=10.0,
            bottom_face_center=(58.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        base_cap = scad.make_cylinder_rsolid(
            radius=18.0,
            height=12.0,
            bottom_face_center=(-66.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        rear_eye = scad.make_cylinder_rsolid(
            radius=14.0,
            height=12.0,
            bottom_face_center=(-80.0, -6.0, 0.0),
            axis=(0.0, 1.0, 0.0),
        )
        rear_eye_neck = scad.make_box_rsolid(
            18.0,
            14.0,
            16.0,
            bottom_face_center=(-68.0, 0.0, -8.0),
        )
        sleeve_raw = scad.union_rsolid(
            barrel,
            rod_gland_flange,
            rod_gland_nose,
            base_cap,
            rear_eye,
            rear_eye_neck,
            glue=False,
        )
        sleeve_solid = scad.cut_rsolid(
            sleeve_raw,
            scad.make_cylinder_rsolid(
                radius=10.5,
                height=136.0,
                bottom_face_center=(-68.0, 0.0, 0.0),
                axis=(1.0, 0.0, 0.0),
            ),
        )
        sleeve_solid = scad.cut_rsolid(
            sleeve_solid,
            scad.make_cylinder_rsolid(
                radius=4.6,
                height=26.0,
                bottom_face_center=(-80.0, -13.0, 0.0),
                axis=(0.0, 1.0, 0.0),
            ),
        )
        for y, z in flange_holes:
            sleeve_solid = scad.cut_rsolid(
                sleeve_solid,
                scad.make_cylinder_rsolid(
                    radius=1.8,
                    height=16.0,
                    bottom_face_center=(48.0, y, z),
                    axis=(1.0, 0.0, 0.0),
                ),
            )

        piston_land_left = scad.make_cylinder_rsolid(
            radius=10.0,
            height=3.2,
            bottom_face_center=(-6.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        piston_seal_groove = scad.make_cylinder_rsolid(
            radius=9.0,
            height=6.0,
            bottom_face_center=(-3.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        piston_land_right = scad.make_cylinder_rsolid(
            radius=10.0,
            height=3.2,
            bottom_face_center=(2.6, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        chrome_rod = scad.make_cylinder_rsolid(
            radius=6.5,
            height=132.0,
            bottom_face_center=(3.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
        )
        rod_eye = scad.make_cylinder_rsolid(
            radius=13.0,
            height=9.0,
            bottom_face_center=(143.0, -4.5, 0.0),
            axis=(0.0, 1.0, 0.0),
        )
        rod_eye_neck = scad.make_box_rsolid(
            20.0,
            8.0,
            13.0,
            bottom_face_center=(130.0, 0.0, -6.5),
        )
        piston_rod_raw = scad.union_rsolid(
            piston_land_left,
            piston_seal_groove,
            piston_land_right,
            chrome_rod,
            rod_eye,
            rod_eye_neck,
            glue=False,
        )
        rod_eye_pin_hole = scad.make_cylinder_rsolid(
            radius=5.5,
            height=13.0,
            bottom_face_center=(143.0, -6.5, 0.0),
            axis=(0.0, 1.0, 0.0),
        )
        piston_rod_solid = scad.cut_rsolid(piston_rod_raw, rod_eye_pin_hole)

        black_oxide_steel = scad.make_material_rmaterial(
            "black_oxide_steel",
            name="Black oxide steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.10, 0.11, 0.12),
        )
        chrome_steel = scad.make_material_rmaterial(
            "chrome_plated_steel",
            name="Chrome plated steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.78, 0.80, 0.82),
        )

        sleeve_part = scad.make_part_rpart(
            "outer_sleeve", sleeve_solid, name="Outer sleeve with clevis and gland"
        )
        sleeve_part = scad.assign_material_rpart(sleeve_part, black_oxide_steel)
        sleeve_faces = ql.faces().resolve(sleeve_solid)
        sleeve_end_face = None
        for f in sleeve_faces:
            n = f.get_normal_at()
            if abs(abs(n.x) - 1.0) < 0.01 and f.get_area() < 1000.0:
                sleeve_end_face = f
                break
        sleeve_connector = scad.make_face_connector_rconnector("slide_axis", sleeve_end_face)
        sleeve_part = scad.add_connector_rpart(sleeve_part, sleeve_connector)

        piston_rod_part = scad.make_part_rpart(
            "piston_rod", piston_rod_solid, name="Inner piston rod with eye end"
        )
        piston_rod_part = scad.assign_material_rpart(piston_rod_part, chrome_steel)
        rod_faces = ql.faces().resolve(piston_rod_solid)
        rod_end_face = None
        for f in rod_faces:
            n = f.get_normal_at()
            if abs(abs(n.x) - 1.0) < 0.01 and f.get_area() < 1000.0:
                rod_end_face = f
                break
        sleeve_normal = sleeve_end_face.get_normal_at()
        rod_normal = rod_end_face.get_normal_at()
        rod_flip = (sleeve_normal.x * rod_normal.x) < 0
        rod_connector = scad.make_face_connector_rconnector("slide_axis", rod_end_face, flip=rod_flip)
        piston_rod_part = scad.add_connector_rpart(piston_rod_part, rod_connector)

        hydraulic_assembly = scad.make_assembly_rassembly(
            "hydraulic_rod_assembly", name="Hydraulic rod assembly"
        )
        hydraulic_assembly = scad.add_component_rassembly(
            hydraulic_assembly,
            sleeve_part,
            component_id="outer_sleeve",
            placement=scad.identity_placement_rplacement(),
        )
        hydraulic_assembly = scad.add_component_rassembly(
            hydraulic_assembly,
            piston_rod_part,
            component_id="inner_piston_rod",
            placement=scad.identity_placement_rplacement(),
        )
        hydraulic_assembly = scad.ground_component_rassembly(
            hydraulic_assembly, "outer_sleeve"
        )
        hydraulic_assembly = scad.add_prismatic_constraint_rassembly(
            hydraulic_assembly,
            "rod_slide",
            scad.make_connector_ref_rconnectorref("outer_sleeve", "slide_axis"),
            scad.make_connector_ref_rconnectorref("inner_piston_rod", "slide_axis"),
            drive_distance=0.0,
            distance_limit=scad.make_scalar_limit_rscalarlimit(0.0, 100.0),
        )
        hydraulic_assembly = scad.solve_assembly_constraints_rassembly(
            hydraulic_assembly
        )

        preview = scad.make_compound_from_assembly_rcompound(hydraulic_assembly)
        model_json = scad.export_model_json(session)

    return hydraulic_assembly, preview, model_json


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assembly, preview, model_json = build_hydraulic_rod_assembly()

    model_path = OUT_DIR / "hydraulic_rod_assembly.model.json"
    step_path = OUT_DIR / "hydraulic_rod_assembly.step"
    fcstd_path = OUT_DIR / "hydraulic_rod_assembly.FCStd"
    model_path.write_text(model_json, encoding="utf-8")
    scad.export_step(preview, str(step_path))
    fcstd_status = "skipped"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(model_json, str(fcstd_path.resolve()))
        fcstd_status = str(fcstd_path)
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__})"

    payload = json.loads(model_json)
    face_count = len(ql.faces().resolve(preview))
    print("assembly", assembly.assembly_id)
    print("components", assembly.component_ids())
    print("preview_solids", len(preview.get_solids()))
    print("preview_faces", face_count)
    print("preview_volume", round(preview.get_volume(), 3))
    print("graph_nodes", len(payload["graph"]["nodes"]))
    print("wrote", model_path)
    print("wrote", step_path)
    print("fcstd", fcstd_status)


if __name__ == "__main__":
    main()
