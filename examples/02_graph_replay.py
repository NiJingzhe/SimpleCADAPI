"""Record a replayable model graph, export model JSON, then replay it.

Run from the repository root with:
    uv run python examples/02_graph_replay.py
"""

from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql as Q


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)


with scad.GraphSession() as session:
    body = scad.make_box_rsolid(40.0, 24.0, 10.0, bottom_face_center=(0.0, 0.0, 0.0))
    cutter = scad.make_cylinder_rsolid(4.0, 16.0, bottom_face_center=(0.0, 0.0, -3.0))
    drilled = scad.cut_rsolidlist(body, cutter)

    # Use a serializable QL selector instead of relying on OCC edge iteration order.
    bottom_circle = (
        Q.edges()
        .where(Q.curve_type("circle"))
        .order_by(Q.center_axis("z"))
        .take(1)
        .exactly(1)
    )
    final = scad.chamfer_rsolid(drilled, bottom_circle, 0.6)

model_json = scad.export_model_json(session)
(OUT / "graph_replay.model.json").write_text(model_json, encoding="utf-8")

rebuilt = scad.replay_model_json(model_json)
print("recorded_nodes", session.graph.node_count)
print("replayed_outputs", len(rebuilt))
print("replayed_type", type(rebuilt[0]).__name__ if rebuilt else "none")
print("wrote", OUT / "graph_replay.model.json")
