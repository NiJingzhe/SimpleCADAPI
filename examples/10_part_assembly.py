"""Build a hydraulic rod assembly with separate sleeve and piston-rod parts."""

from __future__ import annotations

import json
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql


OUT_DIR = Path(__file__).resolve().parent / "out" / "hydraulic_rod_assembly"


@scad.model(graph_id="hydraulic_rod_assembly", export_dir=OUT_DIR)
def build_hydraulic_rod_assembly():
    flange_holes = [
        ("zplus", 0.0, 16.0),
        ("yplus", 16.0, 0.0),
        ("zminus", 0.0, -16.0),
        ("yminus", -16.0, 0.0),
    ]

    @scad.requires_session
    def _build_in_session():
        def _named_cylinder(
            *,
            radius: float,
            height: float,
            bottom_face_center: tuple[float, float, float],
            axis: tuple[float, float, float],
            start_face_tag: str,
            end_face_tag: str,
            side_faces_tag: str,
            tag_prefix: str,
            result_tag: str,
        ):
            return scad.make_cylinder_rsolid(
                radius=radius,
                height=height,
                bottom_face_center=bottom_face_center,
                axis=axis,
                tag_prefix=tag_prefix,
                result_tag=result_tag,
                start_face_tag=start_face_tag,
                end_face_tag=end_face_tag,
                side_face_tag=side_faces_tag,
            )

        def _named_box(
            *,
            width: float,
            height: float,
            depth: float,
            bottom_face_center: tuple[float, float, float],
            bottom_face_tag: str,
            top_face_tag: str,
            side_faces_tag: str,
            tag_prefix: str,
            result_tag: str,
        ):
            profile = scad.make_rectangle_rface(
                # Rectangle profile axes are Y/X for a +Z normal; swap the
                # dimensions to preserve make_box_rsolid's global X/Y layout.
                width=height,
                height=width,
                center=bottom_face_center,
                tag_prefix=f"{tag_prefix}.profile",
                edge_tags=("bottom", "right", "top", "left"),
            )
            return scad.extrude_rsolid(
                profile=profile,
                direction=(0.0, 0.0, 1.0),
                distance=depth,
                tag_prefix=tag_prefix,
                result_tag=result_tag,
                start_face_tag=bottom_face_tag,
                end_face_tag=top_face_tag,
                side_faces_tag=side_faces_tag,
            )

        def _require_complete_face_naming(solid, prefix: str) -> None:
            unnamed = [
                index
                for index, face in enumerate(solid.get_faces())
                if not any(
                    tag.startswith(prefix)
                    for tag in scad.list_tags(face, scope="local")
                )
            ]
            if unnamed:
                raise RuntimeError(
                    f"{prefix} final face naming is incomplete at indices {unnamed}"
                )

        def _require_shared_edge(solid, first_face_tag: str, second_face_tag: str):
            first = ql.faces().where(ql.tag(first_face_tag)).exactly(1)
            second = ql.faces().where(ql.tag(second_face_tag)).exactly(1)
            shared = first.shared_boundary(second).incident_face_count(exactly=2)
            incident = (
                ql.edges()
                .incident_to(first, second, distinct=True)
                .incident_face_count(exactly=2)
            )
            shared_edge = shared.exactly(1).resolve(solid)[0]
            incident_edge = incident.exactly(1).resolve(solid)[0]
            if shared_edge.topo_id != incident_edge.topo_id:
                raise RuntimeError(
                    f"Face pair {first_face_tag!r}, {second_face_tag!r} "
                    "did not resolve the same shared Edge"
                )
            return shared_edge

        barrel = _named_cylinder(
            radius=16.0,
            height=120.0,
            bottom_face_center=(-60.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="sleeve.barrel.face.rear",
            end_face_tag="sleeve.barrel.face.front",
            side_faces_tag="sleeve.barrel.face.outer",
            tag_prefix="hydraulic.sleeve.barrel",
            result_tag="part.hydraulic.sleeve.barrel",
        )
        rod_gland_flange = _named_cylinder(
            radius=22.0,
            height=12.0,
            bottom_face_center=(50.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="sleeve.gland.face.shoulder",
            end_face_tag="sleeve.gland.face.mount",
            side_faces_tag="sleeve.gland.face.outer",
            tag_prefix="hydraulic.sleeve.gland.flange",
            result_tag="part.hydraulic.sleeve.gland.flange",
        )
        rod_gland_nose = _named_cylinder(
            radius=13.0,
            height=10.0,
            bottom_face_center=(58.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="sleeve.gland.nose.face.rear",
            end_face_tag="sleeve.gland.nose.face.front",
            side_faces_tag="sleeve.gland.nose.face.outer",
            tag_prefix="hydraulic.sleeve.gland.nose",
            result_tag="part.hydraulic.sleeve.gland.nose",
        )
        base_cap = _named_cylinder(
            radius=18.0,
            height=12.0,
            bottom_face_center=(-66.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="sleeve.base.cap.face.rear",
            end_face_tag="sleeve.base.cap.face.front",
            side_faces_tag="sleeve.base.cap.face.outer",
            tag_prefix="hydraulic.sleeve.base.cap",
            result_tag="part.hydraulic.sleeve.base.cap",
        )
        rear_eye = _named_cylinder(
            radius=14.0,
            height=12.0,
            bottom_face_center=(-80.0, -6.0, 0.0),
            axis=(0.0, 1.0, 0.0),
            start_face_tag="sleeve.rear.eye.face.ymin",
            end_face_tag="sleeve.rear.eye.face.ymax",
            side_faces_tag="sleeve.rear.eye.face.outer",
            tag_prefix="hydraulic.sleeve.rear.eye",
            result_tag="part.hydraulic.sleeve.rear.eye",
        )
        rear_eye_neck = _named_box(
            width=18.0,
            height=14.0,
            depth=16.0,
            bottom_face_center=(-68.0, 0.0, -8.0),
            bottom_face_tag="sleeve.rear.neck.face.bottom",
            top_face_tag="sleeve.rear.neck.face.top",
            side_faces_tag="sleeve.rear.neck.face.side",
            tag_prefix="hydraulic.sleeve.rear.neck",
            result_tag="part.hydraulic.sleeve.rear.neck",
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
        barrel_bore = _named_cylinder(
            radius=10.5,
            height=136.0,
            bottom_face_center=(-68.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="sleeve.barrel.bore.face.rear",
            end_face_tag="sleeve.barrel.bore.face.front",
            side_faces_tag="sleeve.barrel.bore.face.wall",
            tag_prefix="hydraulic.sleeve.barrel.bore",
            result_tag="tool.hydraulic.sleeve.barrel.bore",
        )
        sleeve_solid = scad.cut_rsolid(sleeve_raw, barrel_bore)
        rear_eye_pin_bore = _named_cylinder(
            radius=4.6,
            height=26.0,
            bottom_face_center=(-80.0, -13.0, 0.0),
            axis=(0.0, 1.0, 0.0),
            start_face_tag="sleeve.rear.eye.pin.face.ymin",
            end_face_tag="sleeve.rear.eye.pin.face.ymax",
            side_faces_tag="sleeve.rear.eye.pin.face.wall",
            tag_prefix="hydraulic.sleeve.rear.eye.pin.bore",
            result_tag="tool.hydraulic.sleeve.rear.eye.pin_bore",
        )
        sleeve_solid = scad.cut_rsolid(sleeve_solid, rear_eye_pin_bore)
        for hole_id, y, z in flange_holes:
            bolt_hole = _named_cylinder(
                radius=1.8,
                height=16.0,
                bottom_face_center=(48.0, y, z),
                axis=(1.0, 0.0, 0.0),
                start_face_tag=f"sleeve.gland.bolt.{hole_id}.face.rear",
                end_face_tag=f"sleeve.gland.bolt.{hole_id}.face.front",
                side_faces_tag=f"sleeve.gland.bolt.{hole_id}.face.wall",
                tag_prefix=f"hydraulic.sleeve.gland.bolt.{hole_id}",
                result_tag=f"tool.hydraulic.sleeve.gland.bolt.{hole_id}",
            )
            sleeve_solid = scad.cut_rsolid(
                sleeve_solid,
                bolt_hole,
            )

        piston_land_left = _named_cylinder(
            radius=10.0,
            height=3.2,
            bottom_face_center=(-6.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="rod.piston.land.left.face.rear",
            end_face_tag="rod.piston.land.left.face.front",
            side_faces_tag="rod.piston.land.left.face.outer",
            tag_prefix="hydraulic.rod.piston.land.left",
            result_tag="part.hydraulic.rod.piston.land.left",
        )
        piston_seal_groove = _named_cylinder(
            radius=9.0,
            height=6.0,
            bottom_face_center=(-3.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="rod.piston.groove.face.rear",
            end_face_tag="rod.piston.groove.face.front",
            side_faces_tag="rod.piston.groove.face.outer",
            tag_prefix="hydraulic.rod.piston.groove",
            result_tag="part.hydraulic.rod.piston.groove",
        )
        piston_land_right = _named_cylinder(
            radius=10.0,
            height=3.2,
            bottom_face_center=(2.6, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="rod.piston.land.right.face.rear",
            end_face_tag="rod.piston.land.right.face.front",
            side_faces_tag="rod.piston.land.right.face.outer",
            tag_prefix="hydraulic.rod.piston.land.right",
            result_tag="part.hydraulic.rod.piston.land.right",
        )
        chrome_rod = _named_cylinder(
            radius=6.5,
            height=132.0,
            bottom_face_center=(3.0, 0.0, 0.0),
            axis=(1.0, 0.0, 0.0),
            start_face_tag="rod.shaft.face.piston",
            end_face_tag="rod.shaft.face.eye",
            side_faces_tag="rod.shaft.face.outer",
            tag_prefix="hydraulic.rod.shaft",
            result_tag="part.hydraulic.rod.shaft",
        )
        rod_eye = _named_cylinder(
            radius=13.0,
            height=9.0,
            bottom_face_center=(143.0, -4.5, 0.0),
            axis=(0.0, 1.0, 0.0),
            start_face_tag="rod.eye.face.ymin",
            end_face_tag="rod.eye.face.ymax",
            side_faces_tag="rod.eye.face.outer",
            tag_prefix="hydraulic.rod.eye",
            result_tag="part.hydraulic.rod.eye",
        )
        rod_eye_neck = _named_box(
            width=20.0,
            height=8.0,
            depth=13.0,
            bottom_face_center=(130.0, 0.0, -6.5),
            bottom_face_tag="rod.eye.neck.face.bottom",
            top_face_tag="rod.eye.neck.face.top",
            side_faces_tag="rod.eye.neck.face.side",
            tag_prefix="hydraulic.rod.eye.neck",
            result_tag="part.hydraulic.rod.eye.neck",
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
        rod_eye_pin_hole = _named_cylinder(
            radius=5.5,
            height=13.0,
            bottom_face_center=(143.0, -6.5, 0.0),
            axis=(0.0, 1.0, 0.0),
            start_face_tag="rod.eye.pin.face.ymin",
            end_face_tag="rod.eye.pin.face.ymax",
            side_faces_tag="rod.eye.pin.face.wall",
            tag_prefix="hydraulic.rod.eye.pin.bore",
            result_tag="tool.hydraulic.rod.eye.pin_bore",
        )
        piston_rod_solid = scad.cut_rsolid(piston_rod_raw, rod_eye_pin_hole)

        sleeve_solid = scad.apply_tag(
            shape=sleeve_solid,
            tag="part.hydraulic.sleeve.finished",
        )
        piston_rod_solid = scad.apply_tag(
            shape=piston_rod_solid,
            tag="part.hydraulic.rod.finished",
        )

        _require_complete_face_naming(sleeve_solid, "sleeve.")
        _require_complete_face_naming(piston_rod_solid, "rod.")
        _require_shared_edge(
            sleeve_solid,
            "sleeve.gland.face.mount",
            "sleeve.gland.face.outer",
        )
        _require_shared_edge(
            sleeve_solid,
            "sleeve.gland.nose.face.front",
            "sleeve.barrel.bore.face.wall",
        )
        for hole_id in ("zplus", "yplus"):
            _require_shared_edge(
                sleeve_solid,
                "sleeve.gland.face.mount",
                f"sleeve.gland.bolt.{hole_id}.face.wall",
            )

        black_oxide_steel = scad.make_material_rmaterial(
            material_id="black_oxide_steel",
            name="Black oxide steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.10, 0.11, 0.12),
        )
        chrome_steel = scad.make_material_rmaterial(
            material_id="chrome_plated_steel",
            name="Chrome plated steel",
            density=7.85e-6,
            density_unit="kg/mm^3",
            color=(0.78, 0.80, 0.82),
        )

        sleeve_part = scad.make_part_rpart(
            part_id="outer_sleeve",
            body=sleeve_solid,
            name="Outer sleeve with clevis and gland",
        )
        sleeve_part = scad.assign_material_rpart(
            part=sleeve_part, material=black_oxide_steel
        )
        sleeve_end_face = (
            ql.faces()
            .where(ql.tag("sleeve.gland.face.mount"))
            .exactly(1)
            .resolve(sleeve_solid)[0]
        )
        sleeve_connector = scad.make_face_connector_rconnector(
            connector_id="slide_axis", face=sleeve_end_face
        )
        sleeve_part = scad.add_connector_rpart(
            part=sleeve_part, connector=sleeve_connector
        )

        piston_rod_part = scad.make_part_rpart(
            part_id="piston_rod",
            body=piston_rod_solid,
            name="Inner piston rod with eye end",
        )
        piston_rod_part = scad.assign_material_rpart(
            part=piston_rod_part, material=chrome_steel
        )
        rod_end_face = (
            ql.faces()
            .where(ql.tag("rod.piston.land.left.face.rear"))
            .exactly(1)
            .resolve(piston_rod_solid)[0]
        )
        sleeve_normal = sleeve_end_face.get_normal_at()
        rod_normal = rod_end_face.get_normal_at()
        rod_flip = (sleeve_normal.x * rod_normal.x) < 0
        rod_connector = scad.make_face_connector_rconnector(
            connector_id="slide_axis", face=rod_end_face, flip=rod_flip
        )
        piston_rod_part = scad.add_connector_rpart(
            part=piston_rod_part, connector=rod_connector
        )

        hydraulic_assembly = scad.make_assembly_rassembly(
            assembly_id="hydraulic_rod_assembly", name="Hydraulic rod assembly"
        )
        hydraulic_assembly = scad.add_component_rassembly(
            assembly=hydraulic_assembly,
            item=sleeve_part,
            component_id="outer_sleeve",
            placement=scad.identity_placement_rplacement(),
        )
        hydraulic_assembly = scad.add_component_rassembly(
            assembly=hydraulic_assembly,
            item=piston_rod_part,
            component_id="inner_piston_rod",
            placement=scad.identity_placement_rplacement(),
        )
        hydraulic_assembly = scad.ground_component_rassembly(
            assembly=hydraulic_assembly, component_id="outer_sleeve"
        )
        hydraulic_assembly = scad.add_prismatic_constraint_rassembly(
            assembly=hydraulic_assembly,
            constraint_id="rod_slide",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="outer_sleeve", connector_id="slide_axis"
            ),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="inner_piston_rod", connector_id="slide_axis"
            ),
            drive_distance=0.0,
            distance_limit=scad.make_scalar_limit_rscalarlimit(
                lower_value=0.0, upper_value=100.0
            ),
        )
        hydraulic_assembly = scad.solve_assembly_constraints_rassembly(
            assembly=hydraulic_assembly
        )

        preview = scad.make_compound_from_assembly_rcompound(
            assembly=hydraulic_assembly
        )
        preview = scad.apply_tag(
            shape=preview,
            tag="assembly.hydraulic.preview",
        )
        return hydraulic_assembly, preview

    hydraulic_assembly, preview = _build_in_session()
    scad.capture_result(value=(hydraulic_assembly, preview))
    return hydraulic_assembly, preview


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = build_hydraulic_rod_assembly()
    assembly, preview = result.value

    fcstd_path = OUT_DIR / "hydraulic_rod_assembly.FCStd"
    fcstd_status = "skipped"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            json_str=result.model_json,
            output_path=str(fcstd_path.resolve()),
        )
        fcstd_status = str(fcstd_path)
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__})"

    payload = json.loads(result.model_json)
    face_count = len(ql.faces().resolve(preview))
    print("assembly", assembly.assembly_id)
    print("components", assembly.component_ids())
    print("preview_solids", len(preview.get_solids()))
    print("preview_faces", face_count)
    print("preview_volume", round(preview.get_volume(), 3))
    print("graph_nodes", len(payload["graph"]["nodes"]))
    for path in result.artifact_paths.values():
        print("wrote", path)
    print("fcstd", fcstd_status)


if __name__ == "__main__":
    main()
