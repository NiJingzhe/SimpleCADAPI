"""Expression parameters inside the v2 graph/model workflow.

Run from the repository root with:
    uv run python examples/03_expressions.py
"""

import json
from pathlib import Path

import simplecadapi as scad


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)


width = scad.var("width", 24.0, comment="plate width")
height = scad.var("height", 12.0, comment="plate height")
thickness = scad.var("thickness", 4.0, comment="plate thickness")

with scad.GraphSession() as session:
    plate = scad.make_box_rsolid(width, height, thickness)
    rib = scad.make_box_rsolid(width / 4.0, height, thickness * 2.0)
    rib = scad.translate_shape(rib, (0.0, 0.0, 4.0))
    part = scad.union_rsolid(plate, rib)

model_json = scad.export_model_json(session)
payload = json.loads(model_json)
(OUT / "expressions.model.json").write_text(model_json, encoding="utf-8")

print("expression_nodes", len(payload["expression_graph"]["nodes"]))
print("graph_nodes", len(payload["graph"]["nodes"]))
print("volume", round(part.get_volume(), 3))
