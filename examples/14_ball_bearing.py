"""Example 14: parameterized ball bearing standard assembly.

This example builds a small radial ball bearing through
``scad.std.bearing.make_ball_bearing_rassembly`` and then keeps working inside
that assembly by binding a demo shaft to the inner ring and a demo housing to
the outer ring.  The important bearing semantics are product-level, not just
geometry: stable component ids expose the rings and balls, and the inner and
outer rings are connected by a revolute constraint.
"""

from __future__ import annotations

import json
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql


OUT_DIR = Path("examples/out/ball_bearing_608_demo")

BORE_DIAMETER = 8.0
OUTER_DIAMETER = 22.0
BEARING_WIDTH = 5.0
BALL_DIAMETER = 3.0
BALL_COUNT = 7
RACEWAY_CLEARANCE = 0.05
EDGE_CHAMFER = 0.08
INNER_RING_ANGLE = 35.0


def _axis_part(part_id: str, solid: scad.Solid, name: str) -> scad.Part:
    part = scad.make_part_rpart(part_id, solid, name=name)
    top_face = max(
        solid.get_faces(),
        key=lambda face: face.get_center().z if face.get_normal_at().z > 0.7 else -999.0,
    )
    axis = scad.make_face_connector_rconnector("axis", top_face)
    return scad.add_connector_rpart(part, axis)


def _make_demo_shaft() -> scad.Part:
    shaft = scad.make_cylinder_rsolid(
        radius=BORE_DIAMETER / 2.0 - 0.2,
        height=BEARING_WIDTH + 4.0,
        bottom_face_center=(0.0, 0.0, -BEARING_WIDTH / 2.0 - 4.0),
        axis=(0.0, 0.0, 1.0),
    )
    shaft = scad.apply_tag(shaft, "role.demo_shaft")
    return _axis_part("demo_shaft", shaft, "Demo shaft bound to inner ring")


def _make_demo_housing() -> scad.Part:
    housing_outer = scad.make_cylinder_rsolid(
        radius=OUTER_DIAMETER / 2.0 + 3.0,
        height=BEARING_WIDTH + 0.75,
        bottom_face_center=(0.0, 0.0, -BEARING_WIDTH / 2.0 - 0.75),
        axis=(0.0, 0.0, 1.0),
    )
    bearing_pocket = scad.make_cylinder_rsolid(
        radius=OUTER_DIAMETER / 2.0 + 0.25,
        height=BEARING_WIDTH + 3.5,
        bottom_face_center=(0.0, 0.0, -BEARING_WIDTH / 2.0 - 1.75),
        axis=(0.0, 0.0, 1.0),
    )
    housing = scad.cut_rsolid(
        housing_outer,
        bearing_pocket,
        skip_non_intersecting=False,
    )
    housing = scad.apply_tag(housing, "role.demo_housing")
    return _axis_part("demo_housing", housing, "Demo housing bound to outer ring")


def build_ball_bearing_demo():
    with scad.GraphSession() as session:
        bearing = scad.std.bearing.make_ball_bearing_rassembly(
            BORE_DIAMETER,
            OUTER_DIAMETER,
            BEARING_WIDTH,
            BALL_DIAMETER,
            BALL_COUNT,
            RACEWAY_CLEARANCE,
            EDGE_CHAMFER,
            "ball_bearing_608_demo",
            INNER_RING_ANGLE,
        )
        meta = bearing.get_metadata("std.bearing.ball_bearing")

        outer_ring = bearing.get_component("outer_ring").item.body
        inner_ring = bearing.get_component("inner_ring").item.body
        print(
            "bearing_core",
            f"components={len(bearing.component_ids())}",
            f"balls={meta['ball_count']}",
            f"constraint={meta['revolute_constraint_id']}",
        )
        print(
            "ring_geometry",
            f"outer_faces={len(ql.faces().resolve(outer_ring))}",
            f"inner_faces={len(ql.faces().resolve(inner_ring))}",
            f"outer_volume={outer_ring.get_volume():.2f}",
            f"inner_volume={inner_ring.get_volume():.2f}",
        )

        bearing = scad.add_component_rassembly(
            bearing,
            _make_demo_shaft(),
            component_id="demo_shaft",
            placement=scad.identity_placement_rplacement(),
        )
        bearing = scad.add_component_rassembly(
            bearing,
            _make_demo_housing(),
            component_id="demo_housing",
            placement=scad.identity_placement_rplacement(),
        )
        bearing = scad.add_fixed_constraint_rassembly(
            bearing,
            "shaft_to_inner_ring",
            scad.make_connector_ref_rconnectorref("inner_ring", "axis"),
            scad.make_connector_ref_rconnectorref("demo_shaft", "axis"),
        )
        bearing = scad.add_fixed_constraint_rassembly(
            bearing,
            "housing_to_outer_ring",
            scad.make_connector_ref_rconnectorref("outer_ring", "axis"),
            scad.make_connector_ref_rconnectorref("demo_housing", "axis"),
        )
        bearing = scad.solve_assembly_constraints_rassembly(bearing)
        report = scad.inspect_assembly_constraints_rconstraintreport(bearing)
        preview = scad.make_compound_from_assembly_rcompound(bearing)
        model_json = scad.export_model_json(session)

    return bearing, report, preview, model_json


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    assembly, report, preview, model_json = build_ball_bearing_demo()

    model_path = OUT_DIR / "ball_bearing_608_demo.model.json"
    step_path = OUT_DIR / "ball_bearing_608_demo.step"
    fcstd_path = OUT_DIR / "ball_bearing_608_demo.FCStd"
    model_path.write_text(model_json, encoding="utf-8")
    scad.export_step(preview, str(step_path))

    fcstd_status = str(fcstd_path)
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(model_json, str(fcstd_path.resolve()))
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__})"

    payload = json.loads(model_json)
    print("assembly", assembly.assembly_id)
    print("components", assembly.component_ids())
    print("constraints", assembly.constraint_ids())
    print("solved", report.solved)
    print("preview_solids", len(preview.get_solids()))
    print("preview_volume", round(preview.get_volume(), 2))
    print("graph_nodes", len(payload["graph"]["nodes"]))
    print("wrote", model_path)
    print("wrote", step_path)
    print("fcstd", fcstd_status)


if __name__ == "__main__":
    main()
