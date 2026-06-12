"""Constrained sketch-first modeling with isomorphic SimpleCADAPI calls.

Run from the repository root with:
    uv run python examples/08_constrained_sketch.py

Generated files:
    examples/out/constrained_sketch.model.json
    examples/out/constrained_sketch.step

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


def make_plate_profile(width, height):
    sketch = scad.make_sketch_rsketch("plate_profile", plane="XY")

    p0 = scad.make_sketch_point_rsketchref(sketch, "p0", 0.0, 0.0)
    p1 = scad.make_sketch_point_rsketchref(sketch, "p1", width, 0.0)
    p2 = scad.make_sketch_point_rsketchref(sketch, "p2", width, height)
    p3 = scad.make_sketch_point_rsketchref(sketch, "p3", 0.0, height)

    sketch = scad.add_line_rsketch(sketch, "bottom", p0, p1)
    sketch = scad.add_line_rsketch(sketch, "right", p1, p2)
    sketch = scad.add_line_rsketch(sketch, "top", p2, p3)
    sketch = scad.add_line_rsketch(sketch, "left", p3, p0)

    bottom = scad.get_sketch_entity_rsketchref(sketch, "bottom")
    right = scad.get_sketch_entity_rsketchref(sketch, "right")
    top = scad.get_sketch_entity_rsketchref(sketch, "top")
    left = scad.get_sketch_entity_rsketchref(sketch, "left")

    sketch = scad.constrain_horizontal_rsketch(sketch, bottom)
    sketch = scad.constrain_vertical_rsketch(sketch, right)
    sketch = scad.constrain_parallel_rsketch(sketch, bottom, top)
    sketch = scad.constrain_parallel_rsketch(sketch, left, right)
    sketch = scad.constrain_perpendicular_rsketch(sketch, bottom, right)
    sketch = scad.constrain_equal_length_rsketch(sketch, bottom, top)
    sketch = scad.constrain_equal_length_rsketch(sketch, left, right)
    sketch = scad.constrain_distance_rsketch(sketch, p0, p1, width)
    sketch = scad.constrain_distance_rsketch(sketch, p0, p3, height)
    sketch = scad.constrain_fix_rsketch(sketch, p0)

    with scad.suspend_graph_recording():
        result = scad.solve_sketch_rsketchresult(
            sketch,
            require_fully_constrained=True,
        )
    print("plate_sketch", result.status, "dof", result.dof)
    return scad.make_face_from_sketch_rface(sketch)


def make_hole_profile(width, height, radius):
    sketch = scad.make_sketch_rsketch("center_hole", plane="XY")
    center = scad.make_sketch_point_rsketchref(sketch, "center", width / 2.0, height / 2.0)
    sketch = scad.add_circle_rsketch(sketch, "hole", center, radius)

    hole = scad.get_sketch_entity_rsketchref(sketch, "hole")
    sketch = scad.constrain_fix_rsketch(sketch, center)
    sketch = scad.constrain_radius_rsketch(sketch, hole, radius)

    with scad.suspend_graph_recording():
        result = scad.solve_sketch_rsketchresult(
            sketch,
            require_fully_constrained=True,
        )
    print("hole_sketch", result.status, "dof", result.dof)
    return scad.make_face_from_sketch_rface(sketch)


plate_w = scad.var("plate_w", 72.0, comment="plate width")
plate_h = scad.var("plate_h", 36.0, comment="plate height")
plate_t = scad.var("plate_t", 6.0, comment="plate thickness")
hole_r = scad.var("hole_r", 5.0, comment="center hole radius")


with scad.GraphSession() as session:
    plate_profile = make_plate_profile(plate_w, plate_h)
    plate = scad.extrude_rsolid(plate_profile, (0.0, 0.0, 1.0), plate_t)

    hole_profile = make_hole_profile(plate_w, plate_h, hole_r)
    hole_cutter = scad.extrude_rsolid(hole_profile, (0.0, 0.0, 1.0), plate_t + 2.0)
    hole_cutter = scad.translate_shape(hole_cutter, (0.0, 0.0, -1.0))

    part = scad.cut_rsolid(plate, hole_cutter)
    part = scad.apply_tag(part, "demo.constrained_sketch_plate")

model_json = scad.export_model_json(session)
MODEL_JSON_PATH.write_text(model_json, encoding="utf-8")

rebuilt = scad.replay_model_json(model_json)
scad.export_step(rebuilt, str(STEP_PATH))

payload = json.loads(model_json)
ops = [node["op"] for node in payload["graph"]["nodes"]]
print("graph_nodes", len(ops))
print("sketch_ops", sum(1 for op in ops if "sketch" in op))
print("volume", round(part.get_volume(), 3))
print("wrote", MODEL_JSON_PATH)
print("wrote", STEP_PATH)
