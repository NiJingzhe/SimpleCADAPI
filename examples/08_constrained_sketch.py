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
MODEL_JSON_PATH = OUT / "constrained_sketch.model.json"
STEP_PATH = OUT / "constrained_sketch.step"
FCSTD_PATH = OUT / "constrained_sketch.fcstd"
FREECAD_CMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")


def _solve_and_report(name: str, sketch: scad.Sketch) -> None:
    result = scad.inspect_sketch_rsketchresult(
        sketch=sketch,
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


@scad.requires_session
def _promote_face(name: str, sketch: scad.Sketch):
    _solve_and_report(name=name, sketch=sketch)
    return scad.make_face_from_sketch_rface(
        sketch=sketch,
        require_fully_constrained=True,
    )


@scad.requires_session
def make_rect_profile(name, x0, y0, width, height):
    sketch = scad.make_sketch_rsketch(name=name, plane="XY")

    sketch = scad.add_point_rsketch(sketch=sketch, point_id="p0", x=x0, y=y0)
    sketch = scad.add_point_rsketch(
        sketch=sketch,
        point_id="p1",
        x=x0 + width,
        y=y0,
    )
    sketch = scad.add_point_rsketch(
        sketch=sketch,
        point_id="p2",
        x=x0 + width,
        y=y0 + height,
    )
    sketch = scad.add_point_rsketch(
        sketch=sketch,
        point_id="p3",
        x=x0,
        y=y0 + height,
    )

    sketch = scad.add_line_rsketch(
        sketch=sketch,
        entity_id="bottom",
        start="p0",
        end="p1",
    )
    sketch = scad.add_line_rsketch(
        sketch=sketch,
        entity_id="right",
        start="p1",
        end="p2",
    )
    sketch = scad.add_line_rsketch(
        sketch=sketch,
        entity_id="top",
        start="p2",
        end="p3",
    )
    sketch = scad.add_line_rsketch(
        sketch=sketch,
        entity_id="left",
        start="p3",
        end="p0",
    )

    sketch = scad.constrain_horizontal_rsketch(sketch=sketch, line="bottom")
    sketch = scad.constrain_vertical_rsketch(sketch=sketch, line="right")
    sketch = scad.constrain_parallel_rsketch(
        sketch=sketch,
        a="bottom",
        b="top",
    )
    sketch = scad.constrain_parallel_rsketch(
        sketch=sketch,
        a="left",
        b="right",
    )
    sketch = scad.constrain_perpendicular_rsketch(
        sketch=sketch,
        a="bottom",
        b="right",
    )
    sketch = scad.constrain_equal_length_rsketch(
        sketch=sketch,
        a="bottom",
        b="top",
    )
    sketch = scad.constrain_equal_length_rsketch(
        sketch=sketch,
        a="left",
        b="right",
    )
    sketch = scad.constrain_distance_rsketch(
        sketch=sketch,
        a="p0",
        b="p1",
        value=width,
    )
    sketch = scad.constrain_distance_rsketch(
        sketch=sketch,
        a="p0",
        b="p3",
        value=height,
    )
    sketch = scad.constrain_fix_rsketch(sketch=sketch, target="p0")
    return _promote_face(name=name, sketch=sketch)


@scad.requires_session
def make_circle_profile(name, center_x, center_y, radius, circle_id):
    sketch = scad.make_sketch_rsketch(name=name, plane="XY")
    sketch = scad.add_point_rsketch(
        sketch=sketch,
        point_id="center",
        x=center_x,
        y=center_y,
    )
    sketch = scad.add_circle_rsketch(
        sketch=sketch,
        entity_id=circle_id,
        center="center",
        radius=radius,
    )
    sketch = scad.constrain_fix_rsketch(sketch=sketch, target="center")
    sketch = scad.constrain_radius_rsketch(
        sketch=sketch,
        circle=circle_id,
        value=radius,
    )
    return _promote_face(name=name, sketch=sketch)


@scad.requires_session
def make_guided_diamond_profile(name, center_x, center_y, width, height, guide_gap):
    half_w = width / 2.0
    half_h = height / 2.0
    sketch = scad.make_sketch_rsketch(name=name, plane="XY")

    for point_id, x, y in (
        ("center", center_x, center_y),
        ("left", center_x - half_w, center_y),
        ("top", center_x, center_y + half_h),
        ("right", center_x + half_w, center_y),
        ("bottom", center_x, center_y - half_h),
        ("guide_upper_start", center_x - half_w, center_y + guide_gap),
        ("guide_upper_end", center_x, center_y + half_h + guide_gap),
        ("guide_lower_start", center_x + half_w, center_y - guide_gap),
        ("guide_lower_end", center_x, center_y - half_h - guide_gap),
    ):
        sketch = scad.add_point_rsketch(
            sketch=sketch,
            point_id=point_id,
            x=x,
            y=y,
        )

    for entity_id, start, end, construction in (
        ("bottom_left", "left", "bottom", False),
        ("right_bottom", "bottom", "right", False),
        ("top_right", "right", "top", False),
        ("left_top", "top", "left", False),
        ("guide_upper", "guide_upper_start", "guide_upper_end", True),
        ("guide_lower", "guide_lower_start", "guide_lower_end", True),
    ):
        sketch = scad.add_line_rsketch(
            sketch=sketch,
            entity_id=entity_id,
            start=start,
            end=end,
            construction=construction,
        )

    sketch = scad.constrain_fix_rsketch(sketch=sketch, target="center")
    for function, a, b, value in (
        (scad.constrain_distance_x_rsketch, "left", "center", half_w),
        (scad.constrain_distance_y_rsketch, "left", "center", 0.0),
        (scad.constrain_distance_x_rsketch, "center", "right", half_w),
        (scad.constrain_distance_y_rsketch, "center", "right", 0.0),
        (scad.constrain_distance_x_rsketch, "center", "top", 0.0),
        (scad.constrain_distance_y_rsketch, "center", "top", half_h),
        (scad.constrain_distance_x_rsketch, "bottom", "center", 0.0),
        (scad.constrain_distance_y_rsketch, "bottom", "center", half_h),
    ):
        sketch = function(sketch=sketch, a=a, b=b, value=value)

    for function, a, b in (
        (scad.constrain_parallel_rsketch, "left_top", "right_bottom"),
        (scad.constrain_parallel_rsketch, "top_right", "bottom_left"),
        (scad.constrain_equal_length_rsketch, "left_top", "top_right"),
        (scad.constrain_equal_length_rsketch, "top_right", "right_bottom"),
        (scad.constrain_equal_length_rsketch, "right_bottom", "bottom_left"),
    ):
        sketch = function(sketch=sketch, a=a, b=b)

    for function, a, b, value in (
        (scad.constrain_distance_x_rsketch, "left", "guide_upper_start", 0.0),
        (scad.constrain_distance_y_rsketch, "left", "guide_upper_start", guide_gap),
        (scad.constrain_distance_x_rsketch, "top", "guide_upper_end", 0.0),
        (scad.constrain_distance_y_rsketch, "top", "guide_upper_end", guide_gap),
        (scad.constrain_distance_x_rsketch, "guide_lower_start", "right", 0.0),
        (scad.constrain_distance_y_rsketch, "guide_lower_start", "right", guide_gap),
        (scad.constrain_distance_x_rsketch, "guide_lower_end", "bottom", 0.0),
        (scad.constrain_distance_y_rsketch, "guide_lower_end", "bottom", guide_gap),
    ):
        sketch = function(sketch=sketch, a=a, b=b, value=value)

    for function, a, b in (
        (scad.constrain_parallel_rsketch, "guide_upper", "guide_lower"),
        (scad.constrain_parallel_rsketch, "guide_upper", "right_bottom"),
        (scad.constrain_parallel_rsketch, "guide_lower", "left_top"),
        (scad.constrain_equal_length_rsketch, "guide_upper", "right_bottom"),
        (scad.constrain_equal_length_rsketch, "guide_lower", "left_top"),
    ):
        sketch = function(sketch=sketch, a=a, b=b)
    return _promote_face(name=name, sketch=sketch)


@scad.requires_session
def make_curve_guided_relief_profile(name, center_x, center_y, radius, guide_span):
    sketch = scad.make_sketch_rsketch(name=name, plane="XY")

    for point_id, x, y in (
        ("center", center_x, center_y),
        ("rim", center_x + radius, center_y),
        ("clearance_center", center_x, center_y),
        ("upper_left", center_x - guide_span, center_y + radius),
        ("upper_right", center_x + guide_span, center_y + radius),
        ("lower_left", center_x - guide_span, center_y - radius),
        ("lower_right", center_x + guide_span, center_y - radius),
    ):
        sketch = scad.add_point_rsketch(
            sketch=sketch,
            point_id=point_id,
            x=x,
            y=y,
        )

    sketch = scad.add_circle_rsketch(
        sketch=sketch,
        entity_id="relief",
        center="center",
        radius=radius,
    )
    sketch = scad.add_circle_rsketch(
        sketch=sketch,
        entity_id="clearance",
        center="clearance_center",
        radius=radius,
        construction=True,
    )
    for entity_id, start, end in (
        ("radius_probe", "center", "rim"),
        ("upper_rail", "upper_left", "upper_right"),
        ("lower_rail", "lower_left", "lower_right"),
    ):
        sketch = scad.add_line_rsketch(
            sketch=sketch,
            entity_id=entity_id,
            start=start,
            end=end,
            construction=True,
        )

    sketch = scad.constrain_fix_rsketch(sketch=sketch, target="center")
    sketch = scad.constrain_radius_rsketch(
        sketch=sketch,
        circle="relief",
        value=radius,
    )
    sketch = scad.constrain_point_on_rsketch(
        sketch=sketch,
        point="rim",
        entity="relief",
    )
    sketch = scad.constrain_horizontal_rsketch(
        sketch=sketch,
        line="radius_probe",
    )
    sketch = scad.constrain_length_rsketch(
        sketch=sketch,
        line="radius_probe",
        value=radius,
    )

    sketch = scad.constrain_concentric_rsketch(
        sketch=sketch,
        a="relief",
        b="clearance",
    )
    sketch = scad.constrain_equal_radius_rsketch(
        sketch=sketch,
        a="relief",
        b="clearance",
    )
    sketch = scad.constrain_horizontal_rsketch(
        sketch=sketch,
        line="upper_rail",
    )
    sketch = scad.constrain_horizontal_rsketch(
        sketch=sketch,
        line="lower_rail",
    )
    sketch = scad.constrain_tangent_rsketch(
        sketch=sketch,
        a="upper_rail",
        b="relief",
    )
    sketch = scad.constrain_tangent_rsketch(
        sketch=sketch,
        a="lower_rail",
        b="relief",
    )

    for a, b, value in (
        ("center", "upper_left", -guide_span),
        ("center", "upper_right", guide_span),
        ("center", "lower_left", -guide_span),
        ("center", "lower_right", guide_span),
    ):
        sketch = scad.constrain_distance_x_rsketch(
            sketch=sketch,
            a=a,
            b=b,
            value=value,
        )
    return _promote_face(name=name, sketch=sketch)


@scad.model(graph_id="constrained_sketch")
def build_model():
    plate_w = scad.var(name="plate_w", default=96.0, comment="plate width")
    plate_h = scad.var(name="plate_h", default=54.0, comment="plate height")
    plate_t = scad.var(name="plate_t", default=6.0, comment="plate thickness")
    boss_r = scad.var(
        name="boss_r",
        default=14.0,
        comment="raised center boss radius",
    )
    boss_h = scad.var(
        name="boss_h",
        default=5.0,
        comment="raised center boss height",
    )
    bore_r = scad.var(name="bore_r", default=5.0, comment="through bore radius")
    mount_r = scad.var(
        name="mount_r",
        default=3.0,
        comment="mounting hole radius",
    )
    margin_x = scad.var(
        name="mount_margin_x",
        default=12.0,
        comment="mounting hole x margin",
    )
    margin_y = scad.var(
        name="mount_margin_y",
        default=9.0,
        comment="mounting hole y margin",
    )
    slot_w = scad.var(name="slot_w", default=34.0, comment="service slot width")
    slot_h = scad.var(name="slot_h", default=8.0, comment="service slot height")
    slot_y = scad.var(
        name="slot_center_y",
        default=16.0,
        comment="service slot center y",
    )
    diamond_w = scad.var(
        name="guided_diamond_w",
        default=14.0,
        comment="guided diamond pocket width",
    )
    diamond_h = scad.var(
        name="guided_diamond_h",
        default=8.0,
        comment="guided diamond pocket height",
    )
    diamond_guide_gap = scad.var(
        name="guided_diamond_guide_gap",
        default=5.0,
        comment="parallel guide rail offset",
    )
    relief_r = scad.var(
        name="curve_relief_r",
        default=4.0,
        comment="curve-guided relief radius",
    )
    relief_guide_span = scad.var(
        name="curve_relief_guide_span",
        default=9.0,
        comment="curve relief construction rail half span",
    )

    center_x = plate_w / 2.0
    center_y = plate_h / 2.0

    plate_profile = make_rect_profile(
        name="plate_outline",
        x0=0.0,
        y0=0.0,
        width=plate_w,
        height=plate_h,
    )
    plate_profile = scad.apply_tag(
        shape=plate_profile,
        tag="demo.profile.plate",
    )
    plate = scad.extrude_rsolid(
        profile=plate_profile,
        direction=(0.0, 0.0, 1.0),
        distance=plate_t,
        tag_prefix="constrained_sketch.plate",
        result_tag="part.constrained_sketch.base_plate",
    )
    plate = scad.apply_tag(shape=plate, tag="demo.body.base_plate")

    boss_profile = make_circle_profile(
        name="center_boss",
        center_x=center_x,
        center_y=center_y,
        radius=boss_r,
        circle_id="boss_outer",
    )
    boss_overlap = 1.0
    boss = scad.extrude_rsolid(
        profile=boss_profile,
        direction=(0.0, 0.0, 1.0),
        distance=boss_h + boss_overlap,
        tag_prefix="constrained_sketch.boss",
        result_tag="part.constrained_sketch.raised_boss",
    )
    boss = scad.translate_shape(
        shape=boss,
        vector=(0.0, 0.0, plate_t - boss_overlap),
    )
    boss = scad.apply_tag(shape=boss, tag="demo.body.raised_boss")

    body = scad.union_rsolid(plate, boss, glue=False)

    bore_profile = make_circle_profile(
        name="center_bore",
        center_x=center_x,
        center_y=center_y,
        radius=bore_r,
        circle_id="bore",
    )
    bore_cutter = scad.extrude_rsolid(
        profile=bore_profile,
        direction=(0.0, 0.0, 1.0),
        distance=plate_t + boss_h + 2.0,
        tag_prefix="constrained_sketch.bore.cutter",
        result_tag="tool.constrained_sketch.center_bore",
    )
    bore_cutter = scad.translate_shape(
        shape=bore_cutter,
        vector=(0.0, 0.0, -1.0),
    )

    slot_profile = make_rect_profile(
        name="service_slot",
        x0=center_x - slot_w / 2.0,
        y0=slot_y - slot_h / 2.0,
        width=slot_w,
        height=slot_h,
    )
    slot_cutter = scad.extrude_rsolid(
        profile=slot_profile,
        direction=(0.0, 0.0, 1.0),
        distance=plate_t + 2.0,
        tag_prefix="constrained_sketch.slot.cutter",
        result_tag="tool.constrained_sketch.service_slot",
    )
    slot_cutter = scad.translate_shape(
        shape=slot_cutter,
        vector=(0.0, 0.0, -1.0),
    )

    diamond_profile = make_guided_diamond_profile(
        name="guided_diamond_pocket",
        center_x=plate_w - 24.0,
        center_y=plate_h - 18.0,
        width=diamond_w,
        height=diamond_h,
        guide_gap=diamond_guide_gap,
    )
    diamond_cutter = scad.extrude_rsolid(
        profile=diamond_profile,
        direction=(0.0, 0.0, 1.0),
        distance=plate_t + 2.0,
        tag_prefix="constrained_sketch.diamond.cutter",
        result_tag="tool.constrained_sketch.diamond_pocket",
    )
    diamond_cutter = scad.translate_shape(
        shape=diamond_cutter,
        vector=(0.0, 0.0, -1.0),
    )

    curve_relief_profile = make_curve_guided_relief_profile(
        name="curve_guided_relief",
        center_x=plate_w / 3.0,
        center_y=plate_h - 12.0,
        radius=relief_r,
        guide_span=relief_guide_span,
    )
    curve_relief_cutter = scad.extrude_rsolid(
        profile=curve_relief_profile,
        direction=(0.0, 0.0, 1.0),
        distance=plate_t + 2.0,
        tag_prefix="constrained_sketch.curve_relief.cutter",
        result_tag="tool.constrained_sketch.curve_relief",
    )
    curve_relief_cutter = scad.translate_shape(
        shape=curve_relief_cutter,
        vector=(0.0, 0.0, -1.0),
    )

    mount_centers = [
        ("mount_sw", margin_x, margin_y),
        ("mount_se", plate_w - margin_x, margin_y),
        ("mount_ne", plate_w - margin_x, plate_h - margin_y),
        ("mount_nw", margin_x, plate_h - margin_y),
    ]
    mount_cutters = []
    for name, x_pos, y_pos in mount_centers:
        mount_tag = name.replace("_", ".")
        mount_profile = make_circle_profile(
            name=name,
            center_x=x_pos,
            center_y=y_pos,
            radius=mount_r,
            circle_id="mount_hole",
        )
        mount_cutter = scad.extrude_rsolid(
            profile=mount_profile,
            direction=(0.0, 0.0, 1.0),
            distance=plate_t + 2.0,
            tag_prefix=f"constrained_sketch.{mount_tag}.cutter",
            result_tag=f"tool.constrained_sketch.{mount_tag}",
        )
        mount_cutters.append(
            scad.translate_shape(
                shape=mount_cutter,
                vector=(0.0, 0.0, -1.0),
            )
        )

    part = scad.cut_rsolid(
        body,
        bore_cutter,
        slot_cutter,
        diamond_cutter,
        curve_relief_cutter,
        mount_cutters,
        skip_non_intersecting=False,
    )
    part = scad.apply_tag(
        shape=part,
        tag="demo.constrained_sketch_bracket",
    )
    scad.capture_result(value=part)
    return {
        "part": part,
        "plate_profile": plate_profile,
        "diamond_profile": diamond_profile,
        "curve_relief_profile": curve_relief_profile,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = build_model()
    data = result.value
    MODEL_JSON_PATH.write_text(result.model_json, encoding="utf-8")

    rebuilt = result.replay()
    scad.export_step(shapes=rebuilt, filename=str(STEP_PATH))

    freecad_cmd = str(FREECAD_CMD) if FREECAD_CMD.exists() else None
    scad.translator.freecad_translator.translate_model_json_to_fcstd(
        json_str=result.model_json,
        output_path=str(FCSTD_PATH),
        document_name="SimpleCADConstrainedSketchDemo",
        freecad_cmd=freecad_cmd,
    )

    payload = json.loads(result.model_json)
    ops = [node["op"] for node in payload["graph"]["nodes"]]
    promotion_nodes = [
        node
        for node in payload["graph"]["nodes"]
        if node["op"]
        in {"make_face_from_sketch_rface", "make_wire_from_sketch_rwire"}
    ]
    diamond_promotion = next(
        node
        for node in promotion_nodes
        if node["params"]["sketch"].get("name") == "guided_diamond_pocket"
    )
    diamond_constraints = diamond_promotion["params"]["sketch"].get(
        "constraints",
        [],
    )
    curve_promotion = next(
        node
        for node in promotion_nodes
        if node["params"]["sketch"].get("name") == "curve_guided_relief"
    )
    curve_constraints = curve_promotion["params"]["sketch"].get(
        "constraints",
        [],
    )
    sketch_entity_tags = sorted(
        tag
        for edge in scad.ql.select(items=data["plate_profile"].get_edges())
        .where(scad.ql.tag(pattern="sketch_entity.*"))
        .all()
        for tag in scad.list_tags(shape=edge)
        if tag.startswith("sketch_entity.")
    )
    diamond_entity_tags = sorted(
        tag
        for edge in scad.ql.select(items=data["diamond_profile"].get_edges())
        .where(scad.ql.tag(pattern="sketch_entity.*"))
        .all()
        for tag in scad.list_tags(shape=edge)
        if tag.startswith("sketch_entity.")
    )
    curve_entity_tags = sorted(
        tag
        for edge in scad.ql.select(items=data["curve_relief_profile"].get_edges())
        .where(scad.ql.tag(pattern="sketch_entity.*"))
        .all()
        for tag in scad.list_tags(shape=edge)
        if tag.startswith("sketch_entity.")
    )

    print("graph_nodes", len(ops))
    print("sketch_ops", sum(1 for op in ops if "sketch" in op))
    print("promotion_nodes", len(promotion_nodes))
    print(
        "promotion_solve_snapshots",
        sum(
            1
            for node in promotion_nodes
            if "solve_snapshot" in node.get("params", {})
        ),
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
            if constraint.get("kind")
            in {"tangent", "equal_radius", "concentric", "point_on"}
        ),
    )
    print("volume", round(data["part"].get_volume(), 3))
    print("wrote", MODEL_JSON_PATH)
    print("wrote", STEP_PATH)
    print("wrote", FCSTD_PATH)


if __name__ == "__main__":
    main()
