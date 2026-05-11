"""Show how source code maps to the serializable v2 operation tree.

Run from the repository root with:
    uv run python examples/07_serialization_operation_tree.py

This example intentionally keeps the geometry simple.  Its main purpose is to
show that user-facing calls such as `make_box_rsolid()` and
`helical_sweep_rsolid()` are lowered into the canonical, replayable operation
nodes stored in `model.json`.

Generated files:
    examples/out/serialization_operation_tree.model.json
    examples/out/serialization_operation_tree.summary.md
    examples/out/serialization_operation_tree.step
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from textwrap import dedent

import simplecadapi as scad
from simplecadapi import ql as Q


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)
MODEL_JSON_PATH = OUT / "serialization_operation_tree.model.json"
SUMMARY_PATH = OUT / "serialization_operation_tree.summary.md"
STEP_PATH = OUT / "serialization_operation_tree.step"


def source_step(name: str):
    """Print a readable marker while building the recorded model."""
    print(f"SOURCE STEP: {name}")


# ---------------------------------------------------------------------------
# Expression parameters: model JSON stores numeric snapshots in node.params and
# expression references in node.param_exprs / expression_graph.
# ---------------------------------------------------------------------------
plate_w = scad.var("plate_w", 36.0, comment="main plate width")
plate_h = scad.var("plate_h", 18.0, comment="main plate height")
plate_t = scad.var("plate_t", 3.0, comment="main plate thickness")
hole_r = scad.var("hole_r", 2.2, comment="through-hole radius")
rib_t = scad.var("rib_t", 1.6, comment="rib thickness")
fillet_r = scad.var("fillet_r", 0.45, comment="small edge fillet radius")


with scad.GraphSession() as session:
    # Basic construction and primitive lowering:
    # make_box_rsolid -> rectangle face -> four line edges -> wire -> face -> extrude
    source_step("01 make_box_rsolid(expr dimensions) -> lowered profile + extrude")
    plate = scad.make_box_rsolid(plate_w, plate_h, plate_t)
    plate = scad.set_tag(plate, "demo.main_plate")

    # make_cylinder_rsolid is also serializable via lowering:
    # circle edge -> wire -> face -> extrude
    source_step("02 make_cylinder_rsolid(expr radius) -> lowered circle face + extrude")
    hole = scad.make_cylinder_rsolid(
        hole_r,
        plate_t + 2.0,
        bottom_face_center=(0.0, 0.0, -1.0),
    )
    drilled_plate = scad.cut_rsolidlist(plate, hole)

    # Core wire/profile API: point, line, circle, arc, spline, helix, wire assembly,
    # face construction.  These are kept small and placed away from the plate so
    # they are easy to inspect in the graph without making the shape complicated.
    source_step("03 make_point_rvertex")
    marker_point = scad.make_point_rvertex(-18.0, -9.0, 6.0)

    source_step("04 explicit edges + make_wire_from_edges_rwire + make_face_from_wire_rface")
    e1 = scad.make_line_redge((-8.0, 0.0, plate_t), (-6.0, 0.0, plate_t))
    e2 = scad.make_three_point_arc_redge(
        (-6.0, 0.0, plate_t), (-5.0, 1.0, plate_t), (-4.0, 0.0, plate_t)
    )
    e3 = scad.make_angle_arc_redge(
        (-3.0, 0.0, plate_t), 1.0, 3.14159, 0.0, normal=(0.0, 0.0, 1.0)
    )
    e4 = scad.make_spline_redge(
        [(-2.0, 0.0, plate_t), (-1.0, 0.8, plate_t), (0.0, 0.0, plate_t)]
    )
    # The four edges above are intentionally separate leaf examples.  A valid
    # `make_wire_from_edges_rwire` example follows with a closed triangle.

    # A closed profile built explicitly from lines, then converted to a face.
    tri_a = scad.make_line_redge((8.0, -2.0, plate_t), (11.0, -2.0, plate_t))
    tri_b = scad.make_line_redge((11.0, -2.0, plate_t), (9.5, 1.0, plate_t))
    tri_c = scad.make_line_redge((9.5, 1.0, plate_t), (8.0, -2.0, plate_t))
    triangle_wire = scad.make_wire_from_edges_rwire([tri_a, tri_b, tri_c])
    triangle_face = scad.make_face_from_wire_rface(triangle_wire)
    triangle_boss = scad.extrude_rsolid(triangle_face, (0.0, 0.0, 1.0), rib_t)

    # Convenience wire/face builders are included too; inside GraphSession they
    # lower to the same canonical low-level edge/wire/face operations.
    source_step("05 convenience wires/faces -> lowered canonical edge/wire/face nodes")
    rectangle_wire = scad.make_rectangle_rwire(4.0, 2.0, center=(-13.0, 0.0, plate_t))
    rectangle_face = scad.make_rectangle_rface(4.0, 2.0, center=(-13.0, 4.0, plate_t))
    circle_wire = scad.make_circle_rwire((13.0, 4.0, plate_t), 1.0)
    circle_face = scad.make_circle_rface((13.0, 0.0, plate_t), 1.0)
    segment_wire = scad.make_segment_rwire((-13.0, -4.0, plate_t), (-9.0, -4.0, plate_t))
    polyline_wire = scad.make_polyline_rwire(
        [(-3.0, -5.0, plate_t), (-1.0, -4.0, plate_t), (1.0, -5.0, plate_t)]
    )
    arc_wire = scad.make_three_point_arc_rwire(
        (3.0, -5.0, plate_t), (4.0, -4.0, plate_t), (5.0, -5.0, plate_t)
    )
    angle_arc_wire = scad.make_angle_arc_rwire((7.0, -5.0, plate_t), 1.0, 0.0, 1.57)
    spline_wire = scad.make_spline_rwire(
        [(9.0, -5.0, plate_t), (10.0, -4.0, plate_t), (11.0, -5.0, plate_t)]
    )

    # Basic solid constructors that lower to replayable core operations, plus the
    # scalar-field surface op from the canonical replayable op set.
    source_step("06 make_sphere_rsolid, make_cone_rsolid, make_field_surface_rsolid")
    sphere = scad.make_sphere_rsolid(1.0, center=(-7.0, 6.0, plate_t + 1.0))
    cone = scad.make_cone_rsolid(
        1.2,
        2.0,
        top_radius=0.4,
        bottom_face_center=(-3.0, 6.0, plate_t),
    )
    field_shape = scad.make_field_surface_rsolid(
        scad.field.make_sphere_rscalarfield((0.0, 0.0, 0.0), 0.75),
        bounds=((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0)),
        resolution=(8, 8, 8),
    )
    field_shape = scad.translate_shape(field_shape, (-11.0, 6.0, plate_t + 1.0))

    # Feature operations.
    source_step("07 revolve_rsolid, loft_rsolid, sweep_rsolid")
    revolve_profile = scad.make_polyline_rwire(
        [(0.5, 0.0, 0.0), (1.2, 0.0, 0.0), (1.0, 0.0, 1.6), (0.5, 0.0, 1.6)],
        closed=True,
    )
    revolved_pin = scad.revolve_rsolid(
        revolve_profile,
        axis=(0.0, 0.0, 1.0),
        angle=360.0,
        origin=(0.0, 0.0, 0.0),
    )
    revolved_pin = scad.translate_shape(revolved_pin, (4.0, 6.0, plate_t))

    loft_a = scad.make_rectangle_rwire(1.8, 1.2, center=(8.0, 6.0, plate_t))
    loft_b = scad.make_rectangle_rwire(1.0, 0.8, center=(8.0, 6.0, plate_t + 2.0))
    lofted_post = scad.loft_rsolid([loft_a, loft_b], ruled=True)

    sweep_profile = scad.make_circle_rface((12.0, 6.0, plate_t), 0.35, normal=(1.0, 0.0, 0.0))
    sweep_path = scad.make_polyline_rwire(
        [(12.0, 6.0, plate_t), (14.0, 6.0, plate_t + 1.0), (15.5, 7.0, plate_t + 1.5)]
    )
    swept_pipe = scad.sweep_rsolid(sweep_profile, sweep_path, is_frenet=False)

    # Composite operation: helical_sweep_rsolid is serialized as helix + face + sweep,
    # not as a dedicated `helical_sweep` graph node.
    source_step("08 helical_sweep_rsolid macro -> make_helix_redge + wire + face + sweep")
    thread_profile = scad.make_rectangle_rwire(0.25, 0.18, center=(0.0, 0.0, 0.0))
    helical_thread = scad.helical_sweep_rsolid(
        thread_profile,
        pitch=0.7,
        height=2.2,
        radius=0.9,
        center=(13.0, -6.0, plate_t),
    )

    # Transforms and patterns.  Pattern helpers serialize as explicit translate /
    # rotate nodes instead of `linear_pattern` / `radial_pattern` macro nodes.
    source_step("09 translate_shape, rotate_shape, mirror_shape")
    rib = scad.make_box_rsolid(rib_t, plate_h * 0.55, plate_t * 1.4)
    rib = scad.translate_shape(rib, (-plate_w / 4.0, 0.0, plate_t))
    rib = scad.rotate_shape(rib, 0.0)  # zero-angle shortcut, intentionally not recorded
    rib_copy = scad.mirror_shape(rib, plane_origin=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0))

    source_step("10 linear_pattern_rsolidlist and radial_pattern_rsolidlist macro lowering")
    lug_seed = scad.make_box_rsolid(1.2, 1.2, 1.0, bottom_face_center=(-12.0, -7.0, plate_t))
    linear_lugs = scad.linear_pattern_rsolidlist(lug_seed, (1.0, 0.0, 0.0), count=3, spacing=3.0)
    spoke_seed = scad.make_box_rsolid(0.8, 2.0, 0.8, bottom_face_center=(0.0, 5.2, plate_t))
    radial_spokes = scad.radial_pattern_rsolidlist(
        spoke_seed,
        center=(0.0, 0.0, plate_t),
        axis=(0.0, 0.0, 1.0),
        count=4,
        total_rotation_angle=360.0,
    )

    # Boolean operations.  Boolean union must produce one connected solid, so
    # this tiny demo uses overlapping boxes instead of trying to merge every
    # separate showcase solid above.
    source_step("11 union_rsolid, intersect_rsolidlist, cut_rsolidlist")
    union_a = scad.make_box_rsolid(3.0, 2.0, 1.0, bottom_face_center=(-4.0, -7.0, 0.0))
    union_b = scad.make_box_rsolid(3.0, 2.0, 1.0, bottom_face_center=(-2.5, -7.0, 0.0))
    union_demo = scad.union_rsolid(union_a, union_b)

    overlap_a = scad.make_box_rsolid(2.0, 2.0, 2.0, bottom_face_center=(12.0, -2.0, plate_t))
    overlap_b = scad.make_box_rsolid(2.0, 2.0, 2.0, bottom_face_center=(13.0, -2.0, plate_t))
    intersection_demo = scad.intersect_rsolidlist(overlap_a, overlap_b)

    # Detail operations use QL selectors so the graph contains stable, serializable
    # selection hints rather than Python object identity from source code.
    source_step("12 fillet_rsolid, chamfer_rsolid, shell_rsolid with serializable selectors")
    vertical_edges = Q.edges().where(Q.curve_type("line")).take(4)
    final = scad.fillet_rsolid(union_demo, vertical_edges, fillet_r)

    chamfer_box = scad.make_box_rsolid(3.0, 2.0, 1.0, bottom_face_center=(2.0, -7.0, 0.0))
    top_outer_edges = Q.edges().order_by(Q.center_axis("z"), desc=True).take(4)
    chamfer_demo = scad.chamfer_rsolid(chamfer_box, top_outer_edges, 0.15)

    # Keep shell separate so the demo includes shell without making the main part
    # fragile.  It remains a replayable leaf in model.json.
    shell_box = scad.make_box_rsolid(4.0, 3.0, 2.0, bottom_face_center=(18.0, -7.0, 0.0))
    top_face = Q.faces().order_by(Q.center_axis("z"), desc=True).take(1).exactly(1)
    shell_demo = scad.shell_rsolid(shell_box, top_face, 0.25)

# Export the canonical model JSON and inspect how the graph maps back to source.
model_json = scad.export_model_json(session)
payload = json.loads(model_json)
MODEL_JSON_PATH.write_text(model_json, encoding="utf-8")

# Replay from model JSON to prove that the stored operation tree is sufficient.
rebuilt = scad.replay_model_json(model_json)
scad.export_step(rebuilt, str(STEP_PATH))

ops = [node["op"] for node in payload["graph"]["nodes"]]
op_counts = Counter(ops)
expr_nodes = payload["expression_graph"]["nodes"]
nodes_with_exprs = [
    node for node in payload["graph"]["nodes"] if node.get("param_exprs")
]

# Build a compact source-to-graph explanation.  This file is easier to read than
# the full JSON and is meant to be opened side by side with this Python source.
summary = dedent(
    f"""
    # Serialization Operation Tree Example

    Source file: `examples/07_serialization_operation_tree.py`

    Generated model JSON: `{MODEL_JSON_PATH}`
    Generated STEP replay output: `{STEP_PATH}`

    ## What to compare

    1. Read the `SOURCE STEP` comments / print output in the Python source.
    2. Open the JSON and inspect `graph.nodes[*].op`, `params`, `param_exprs`, and `inputs`.
    3. Notice that convenience API calls are lowered to canonical replayable operations.

    ## Basic counts

    - graph nodes: `{len(payload['graph']['nodes'])}`
    - graph edges: `{len(payload['graph']['edges'])}`
    - leaf ids: `{len(payload['leaf_ids'])}` -> `{payload['leaf_ids']}`
    - expression graph nodes: `{len(expr_nodes)}`
    - operation nodes with `param_exprs`: `{len(nodes_with_exprs)}`
    - replayed outputs: `{len(rebuilt)}`

    ## Canonical operation set observed

    """
).lstrip()

for op, count in sorted(op_counts.items()):
    summary += f"- `{op}`: {count}\n"

summary += dedent(
    """

    ## Important source-code to graph mappings

    - `make_box_rsolid(...)` does **not** appear as `make_box` in model JSON.
      It lowers to `make_line_redge` + `make_wire_from_edges_rwire` +
      `make_face_from_wire_rface` + `make_extrude_rsolid`.
    - `make_cylinder_rsolid(...)` lowers to a circle face plus `make_extrude_rsolid`.
    - `make_sphere_rsolid(...)` and `make_cone_rsolid(...)` lower to revolve chains.
- `make_field_surface_rsolid(...)` records a serialized scalar-field tree in a
  `make_field_surface_rsolid` node.
    - `make_rectangle_rwire`, `make_circle_rwire`, `make_polyline_rwire`, and
      single-arc/spline/helix wire helpers lower to edge + wire operations.
    - `linear_pattern_rsolidlist(...)` lowers to explicit `make_translate_rshape`
      nodes.
    - `radial_pattern_rsolidlist(...)` lowers to explicit `make_rotate_rshape`
      nodes.
    - `helical_sweep_rsolid(...)` lowers to helix + face + `make_sweep_rsolid`;
      there is no `helical_sweep` node.
    - Expression values are snapshotted into `params`; the symbolic links live in
      `param_exprs` and the top-level `expression_graph`.

    ## Nodes that reference expressions

    """
)

for node in nodes_with_exprs[:40]:
    summary += f"- `{node['node_id']}` `{node['op']}` param_exprs={json.dumps(node['param_exprs'], sort_keys=True)}\n"

if len(nodes_with_exprs) > 40:
    summary += f"- ... {len(nodes_with_exprs) - 40} more expression-backed nodes\n"

SUMMARY_PATH.write_text(summary, encoding="utf-8")

print("wrote", MODEL_JSON_PATH)
print("wrote", SUMMARY_PATH)
print("wrote", STEP_PATH)
print("graph_nodes", len(payload["graph"]["nodes"]))
print("expression_nodes", len(expr_nodes))
print("leaf_ids", payload["leaf_ids"])
print("replayed_outputs", len(rebuilt))
print("observed_ops", ", ".join(sorted(op_counts)))
