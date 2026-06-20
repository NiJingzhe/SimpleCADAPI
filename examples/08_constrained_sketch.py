"""Constrained sketch-first modeling with isomorphic SimpleCADAPI calls.

Run from the repository root with:
    uv run python examples/08_constrained_sketch.py

Generated files:
    examples/out/constrained_sketch.model.json
    examples/out/constrained_sketch.step
    examples/out/constrained_sketch.fcstd

When the intent is a sketch/profile, use the sketch APIs. Concrete geometry
APIs remain for paths, pure geometry, and lowering targets.
"""

from __future__ import annotations

import json
from pathlib import Path

import simplecadapi as scad


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)
MODEL_JSON_PATH = OUT / "constrained_sketch.model.json"
STEP_PATH = OUT / "constrained_sketch.step"
FCSTD_PATH = OUT / "constrained_sketch.fcstd"
FREECAD_CMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")


def _solve_and_report(name: str, sketch: scad.Sketch) -> None:
    result = scad.inspect_sketch_rsketchresult(
        sketch,
        require_fully_constrained=True,
    )
    points = sorted(
        (point_id, round(point[0], 3), round(point[1], 3))
        for point_id, point in result.solved_points.items()
    )
    scalars = sorted(
        (key, round(value, 3)) for key, value in result.solved_scalars.items()
    )
    print(
        f"{name}_sketch",
        result.status,
        "dof",
        result.dof,
        "residual",
        f"{result.residual_norm:.2e}",
        "points",
        points[:4],
        "scalars",
        scalars[:2],
    )


def _promote_face(name: str, sketch: scad.Sketch):
    _solve_and_report(name, sketch)
    return scad.make_face_from_sketch_rface(
        sketch,
        require_fully_constrained=True,
    )


def make_rect_profile(name, x0, y0, width, height):
    sketch = scad.make_sketch_rsketch(name, plane="XY")

    sketch = scad.add_point_rsketch(sketch, "p0", x0, y0)
    sketch = scad.add_point_rsketch(sketch, "p1", x0 + width, y0)
    sketch = scad.add_point_rsketch(sketch, "p2", x0 + width, y0 + height)
    sketch = scad.add_point_rsketch(sketch, "p3", x0, y0 + height)

    sketch = scad.add_line_rsketch(sketch, "bottom", "p0", "p1")
    sketch = scad.add_line_rsketch(sketch, "right", "p1", "p2")
    sketch = scad.add_line_rsketch(sketch, "top", "p2", "p3")
    sketch = scad.add_line_rsketch(sketch, "left", "p3", "p0")

    sketch = scad.constrain_horizontal_rsketch(sketch, "bottom")
    sketch = scad.constrain_vertical_rsketch(sketch, "right")
    sketch = scad.constrain_parallel_rsketch(sketch, "bottom", "top")
    sketch = scad.constrain_parallel_rsketch(sketch, "left", "right")
    sketch = scad.constrain_perpendicular_rsketch(sketch, "bottom", "right")
    sketch = scad.constrain_equal_length_rsketch(sketch, "bottom", "top")
    sketch = scad.constrain_equal_length_rsketch(sketch, "left", "right")
    sketch = scad.constrain_distance_rsketch(sketch, "p0", "p1", width)
    sketch = scad.constrain_distance_rsketch(sketch, "p0", "p3", height)
    sketch = scad.constrain_fix_rsketch(sketch, "p0")
    return _promote_face(name, sketch)


def make_circle_profile(name, center_x, center_y, radius, circle_id):
    sketch = scad.make_sketch_rsketch(name, plane="XY")
    sketch = scad.add_point_rsketch(sketch, "center", center_x, center_y)
    sketch = scad.add_circle_rsketch(sketch, circle_id, "center", radius)
    sketch = scad.constrain_fix_rsketch(sketch, "center")
    sketch = scad.constrain_radius_rsketch(sketch, circle_id, radius)
    return _promote_face(name, sketch)


def make_guided_diamond_profile(name, center_x, center_y, width, height, guide_gap):
    half_w = width / 2.0
    half_h = height / 2.0
    sketch = scad.make_sketch_rsketch(name, plane="XY")

    sketch = scad.add_point_rsketch(sketch, "center", center_x, center_y)
    sketch = scad.add_point_rsketch(sketch, "left", center_x - half_w, center_y)
    sketch = scad.add_point_rsketch(sketch, "top", center_x, center_y + half_h)
    sketch = scad.add_point_rsketch(sketch, "right", center_x + half_w, center_y)
    sketch = scad.add_point_rsketch(sketch, "bottom", center_x, center_y - half_h)

    sketch = scad.add_point_rsketch(sketch, "guide_upper_start", center_x - half_w, center_y + guide_gap)
    sketch = scad.add_point_rsketch(sketch, "guide_upper_end", center_x, center_y + half_h + guide_gap)
    sketch = scad.add_point_rsketch(sketch, "guide_lower_start", center_x + half_w, center_y - guide_gap)
    sketch = scad.add_point_rsketch(sketch, "guide_lower_end", center_x, center_y - half_h - guide_gap)

    sketch = scad.add_line_rsketch(sketch, "bottom_left", "left", "bottom")
    sketch = scad.add_line_rsketch(sketch, "right_bottom", "bottom", "right")
    sketch = scad.add_line_rsketch(sketch, "top_right", "right", "top")
    sketch = scad.add_line_rsketch(sketch, "left_top", "top", "left")
    sketch = scad.add_line_rsketch(sketch, "guide_upper", "guide_upper_start", "guide_upper_end", construction=True)
    sketch = scad.add_line_rsketch(sketch, "guide_lower", "guide_lower_start", "guide_lower_end", construction=True)

    sketch = scad.constrain_fix_rsketch(sketch, "center")
    sketch = scad.constrain_distance_x_rsketch(sketch, "left", "center", half_w)
    sketch = scad.constrain_distance_y_rsketch(sketch, "left", "center", 0.0)
    sketch = scad.constrain_distance_x_rsketch(sketch, "center", "right", half_w)
    sketch = scad.constrain_distance_y_rsketch(sketch, "center", "right", 0.0)
    sketch = scad.constrain_distance_x_rsketch(sketch, "center", "top", 0.0)
    sketch = scad.constrain_distance_y_rsketch(sketch, "center", "top", half_h)
    sketch = scad.constrain_distance_x_rsketch(sketch, "bottom", "center", 0.0)
    sketch = scad.constrain_distance_y_rsketch(sketch, "bottom", "center", half_h)

    sketch = scad.constrain_parallel_rsketch(sketch, "left_top", "right_bottom")
    sketch = scad.constrain_parallel_rsketch(sketch, "top_right", "bottom_left")
    sketch = scad.constrain_equal_length_rsketch(sketch, "left_top", "top_right")
    sketch = scad.constrain_equal_length_rsketch(sketch, "top_right", "right_bottom")
    sketch = scad.constrain_equal_length_rsketch(sketch, "right_bottom", "bottom_left")

    sketch = scad.constrain_distance_x_rsketch(sketch, "left", "guide_upper_start", 0.0)
    sketch = scad.constrain_distance_y_rsketch(sketch, "left", "guide_upper_start", guide_gap)
    sketch = scad.constrain_distance_x_rsketch(sketch, "top", "guide_upper_end", 0.0)
    sketch = scad.constrain_distance_y_rsketch(sketch, "top", "guide_upper_end", guide_gap)
    sketch = scad.constrain_distance_x_rsketch(sketch, "guide_lower_start", "right", 0.0)
    sketch = scad.constrain_distance_y_rsketch(sketch, "guide_lower_start", "right", guide_gap)
    sketch = scad.constrain_distance_x_rsketch(sketch, "guide_lower_end", "bottom", 0.0)
    sketch = scad.constrain_distance_y_rsketch(sketch, "guide_lower_end", "bottom", guide_gap)

    sketch = scad.constrain_parallel_rsketch(sketch, "guide_upper", "guide_lower")
    sketch = scad.constrain_parallel_rsketch(sketch, "guide_upper", "right_bottom")
    sketch = scad.constrain_parallel_rsketch(sketch, "guide_lower", "left_top")
    sketch = scad.constrain_equal_length_rsketch(sketch, "guide_upper", "right_bottom")
    sketch = scad.constrain_equal_length_rsketch(sketch, "guide_lower", "left_top")
    return _promote_face(name, sketch)


def make_curve_guided_relief_profile(name, center_x, center_y, radius, guide_span):
    sketch = scad.make_sketch_rsketch(name, plane="XY")

    sketch = scad.add_point_rsketch(sketch, "center", center_x, center_y)
    sketch = scad.add_point_rsketch(sketch, "rim", center_x + radius, center_y)
    sketch = scad.add_point_rsketch(sketch, "clearance_center", center_x, center_y)
    sketch = scad.add_point_rsketch(sketch, "upper_left", center_x - guide_span, center_y + radius)
    sketch = scad.add_point_rsketch(sketch, "upper_right", center_x + guide_span, center_y + radius)
    sketch = scad.add_point_rsketch(sketch, "lower_left", center_x - guide_span, center_y - radius)
    sketch = scad.add_point_rsketch(sketch, "lower_right", center_x + guide_span, center_y - radius)

    sketch = scad.add_circle_rsketch(sketch, "relief", "center", radius)
    sketch = scad.add_circle_rsketch(sketch, "clearance", "clearance_center", radius, construction=True)
    sketch = scad.add_line_rsketch(sketch, "radius_probe", "center", "rim", construction=True)
    sketch = scad.add_line_rsketch(sketch, "upper_rail", "upper_left", "upper_right", construction=True)
    sketch = scad.add_line_rsketch(sketch, "lower_rail", "lower_left", "lower_right", construction=True)

    sketch = scad.constrain_fix_rsketch(sketch, "center")
    sketch = scad.constrain_radius_rsketch(sketch, "relief", radius)
    sketch = scad.constrain_point_on_rsketch(sketch, "rim", "relief")
    sketch = scad.constrain_horizontal_rsketch(sketch, "radius_probe")
    sketch = scad.constrain_length_rsketch(sketch, "radius_probe", radius)

    sketch = scad.constrain_concentric_rsketch(sketch, "relief", "clearance")
    sketch = scad.constrain_equal_radius_rsketch(sketch, "relief", "clearance")
    sketch = scad.constrain_horizontal_rsketch(sketch, "upper_rail")
    sketch = scad.constrain_horizontal_rsketch(sketch, "lower_rail")
    sketch = scad.constrain_tangent_rsketch(sketch, "upper_rail", "relief")
    sketch = scad.constrain_tangent_rsketch(sketch, "lower_rail", "relief")

    sketch = scad.constrain_distance_x_rsketch(sketch, "center", "upper_left", -guide_span)
    sketch = scad.constrain_distance_x_rsketch(sketch, "center", "upper_right", guide_span)
    sketch = scad.constrain_distance_x_rsketch(sketch, "center", "lower_left", -guide_span)
    sketch = scad.constrain_distance_x_rsketch(sketch, "center", "lower_right", guide_span)
    return _promote_face(name, sketch)


plate_w = scad.var("plate_w", 96.0, comment="plate width")
plate_h = scad.var("plate_h", 54.0, comment="plate height")
plate_t = scad.var("plate_t", 6.0, comment="plate thickness")
boss_r = scad.var("boss_r", 14.0, comment="raised center boss radius")
boss_h = scad.var("boss_h", 5.0, comment="raised center boss height")
bore_r = scad.var("bore_r", 5.0, comment="through bore radius")
mount_r = scad.var("mount_r", 3.0, comment="mounting hole radius")
margin_x = scad.var("mount_margin_x", 12.0, comment="mounting hole x margin")
margin_y = scad.var("mount_margin_y", 9.0, comment="mounting hole y margin")
slot_w = scad.var("slot_w", 34.0, comment="service slot width")
slot_h = scad.var("slot_h", 8.0, comment="service slot height")
slot_y = scad.var("slot_center_y", 16.0, comment="service slot center y")
diamond_w = scad.var("guided_diamond_w", 14.0, comment="guided diamond pocket width")
diamond_h = scad.var("guided_diamond_h", 8.0, comment="guided diamond pocket height")
diamond_guide_gap = scad.var("guided_diamond_guide_gap", 5.0, comment="parallel guide rail offset")
relief_r = scad.var("curve_relief_r", 4.0, comment="curve-guided relief radius")
relief_guide_span = scad.var("curve_relief_guide_span", 9.0, comment="curve relief construction rail half span")

center_x = plate_w / 2.0
center_y = plate_h / 2.0


with scad.GraphSession() as session:
    plate_profile = make_rect_profile("plate_outline", 0.0, 0.0, plate_w, plate_h)
    plate_profile = scad.apply_tag(plate_profile, "demo.profile.plate")
    plate = scad.extrude_rsolid(plate_profile, (0.0, 0.0, 1.0), plate_t)
    plate = scad.apply_tag(plate, "demo.body.base_plate")

    boss_profile = make_circle_profile(
        "center_boss",
        center_x,
        center_y,
        boss_r,
        "boss_outer",
    )
    boss_overlap = 1.0
    boss = scad.extrude_rsolid(boss_profile, (0.0, 0.0, 1.0), boss_h + boss_overlap)
    boss = scad.translate_shape(boss, (0.0, 0.0, plate_t - boss_overlap))
    boss = scad.apply_tag(boss, "demo.body.raised_boss")

    body = scad.union_rsolid(plate, boss, glue=False)

    bore_profile = make_circle_profile(
        "center_bore",
        center_x,
        center_y,
        bore_r,
        "bore",
    )
    bore_cutter = scad.extrude_rsolid(
        bore_profile,
        (0.0, 0.0, 1.0),
        plate_t + boss_h + 2.0,
    )
    bore_cutter = scad.translate_shape(bore_cutter, (0.0, 0.0, -1.0))

    slot_profile = make_rect_profile(
        "service_slot",
        center_x - slot_w / 2.0,
        slot_y - slot_h / 2.0,
        slot_w,
        slot_h,
    )
    slot_cutter = scad.extrude_rsolid(slot_profile, (0.0, 0.0, 1.0), plate_t + 2.0)
    slot_cutter = scad.translate_shape(slot_cutter, (0.0, 0.0, -1.0))

    diamond_profile = make_guided_diamond_profile(
        "guided_diamond_pocket",
        plate_w - 24.0,
        plate_h - 18.0,
        diamond_w,
        diamond_h,
        diamond_guide_gap,
    )
    diamond_cutter = scad.extrude_rsolid(diamond_profile, (0.0, 0.0, 1.0), plate_t + 2.0)
    diamond_cutter = scad.translate_shape(diamond_cutter, (0.0, 0.0, -1.0))

    curve_relief_profile = make_curve_guided_relief_profile(
        "curve_guided_relief",
        plate_w / 3.0,
        plate_h - 12.0,
        relief_r,
        relief_guide_span,
    )
    curve_relief_cutter = scad.extrude_rsolid(curve_relief_profile, (0.0, 0.0, 1.0), plate_t + 2.0)
    curve_relief_cutter = scad.translate_shape(curve_relief_cutter, (0.0, 0.0, -1.0))

    mount_centers = [
        ("mount_sw", margin_x, margin_y),
        ("mount_se", plate_w - margin_x, margin_y),
        ("mount_ne", plate_w - margin_x, plate_h - margin_y),
        ("mount_nw", margin_x, plate_h - margin_y),
    ]
    mount_cutters = []
    for name, x_pos, y_pos in mount_centers:
        mount_profile = make_circle_profile(name, x_pos, y_pos, mount_r, "mount_hole")
        mount_cutter = scad.extrude_rsolid(
            mount_profile,
            (0.0, 0.0, 1.0),
            plate_t + 2.0,
        )
        mount_cutters.append(scad.translate_shape(mount_cutter, (0.0, 0.0, -1.0)))

    part = scad.cut_rsolid(
        body,
        bore_cutter,
        slot_cutter,
        diamond_cutter,
        curve_relief_cutter,
        mount_cutters,
        skip_non_intersecting=False,
    )
    part = scad.apply_tag(part, "demo.constrained_sketch_bracket")

model_json = scad.export_model_json(session)
MODEL_JSON_PATH.write_text(model_json, encoding="utf-8")

rebuilt = scad.replay_model_json(model_json)
scad.export_step(rebuilt, str(STEP_PATH))

freecad_cmd = str(FREECAD_CMD) if FREECAD_CMD.exists() else None
scad.translate_model_json_to_fcstd(
    model_json,
    str(FCSTD_PATH),
    document_name="SimpleCADConstrainedSketchDemo",
    freecad_cmd=freecad_cmd,
)

payload = json.loads(model_json)
ops = [node["op"] for node in payload["graph"]["nodes"]]
promotion_nodes = [
    node
    for node in payload["graph"]["nodes"]
    if node["op"] in {"make_face_from_sketch_rface", "make_wire_from_sketch_rwire"}
]
diamond_promotion = next(
    node
    for node in promotion_nodes
    if node["params"]["sketch"].get("name") == "guided_diamond_pocket"
)
diamond_constraints = diamond_promotion["params"]["sketch"].get("constraints", [])
curve_promotion = next(
    node
    for node in promotion_nodes
    if node["params"]["sketch"].get("name") == "curve_guided_relief"
)
curve_constraints = curve_promotion["params"]["sketch"].get("constraints", [])
sketch_entity_tags = sorted(
    tag
    for edge in scad.ql.select(plate_profile.get_edges()).where(
        scad.ql.tag("sketch_entity.*")
    ).all()
    for tag in scad.list_tags(edge)
    if tag.startswith("sketch_entity.")
)
diamond_entity_tags = sorted(
    tag
    for edge in scad.ql.select(diamond_profile.get_edges()).where(
        scad.ql.tag("sketch_entity.*")
    ).all()
    for tag in scad.list_tags(edge)
    if tag.startswith("sketch_entity.")
)
curve_entity_tags = sorted(
    tag
    for edge in scad.ql.select(curve_relief_profile.get_edges()).where(
        scad.ql.tag("sketch_entity.*")
    ).all()
    for tag in scad.list_tags(edge)
    if tag.startswith("sketch_entity.")
)

print("graph_nodes", len(ops))
print("sketch_ops", sum(1 for op in ops if "sketch" in op))
print("promotion_nodes", len(promotion_nodes))
print(
    "promotion_solve_snapshots",
    sum(1 for node in promotion_nodes if "solve_snapshot" in node.get("params", {})),
)
print("contains_public_solve_node", "make_solve_sketch_rsketchresult" in ops)
print("plate_sketch_entity_tags", sketch_entity_tags)
print("diamond_sketch_entity_tags", diamond_entity_tags)
print("diamond_constraint_count", len(diamond_constraints))
print(
    "diamond_parallel_equal_constraints",
    sum(
        1
        for constraint in diamond_constraints
        if constraint.get("kind") in {"parallel", "equal_length"}
    ),
)
print("curve_sketch_entity_tags", curve_entity_tags)
print("curve_constraint_count", len(curve_constraints))
print(
    "curve_tangent_equal_radius_constraints",
    sum(
        1
        for constraint in curve_constraints
        if constraint.get("kind") in {"tangent", "equal_radius", "concentric", "point_on"}
    ),
)
print("volume", round(part.get_volume(), 3))
print("wrote", MODEL_JSON_PATH)
print("wrote", STEP_PATH)
print("wrote", FCSTD_PATH)
