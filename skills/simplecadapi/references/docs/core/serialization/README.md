# Serialization and Replay Operation Guides

This directory documents how SimpleCADAPI 2.x serializes replayable modeling operations into the canonical low-level `model.json` operation graph.

The long-form schema reference remains [`../operation_graph_json_spec.md`](../operation_graph_json_spec.md). These files are more practical, operation-by-operation guides intended for people comparing source code with exported JSON.

## Recommended workflow

```python
import json
import simplecadapi as scad

with scad.GraphSession() as session:
    body = scad.make_box_rsolid(10, 6, 2)
    hole = scad.make_cylinder_rsolid(1, 4, bottom_face_center=(0, 0, -1))
    result = scad.cut_rsolidlist(body, hole)

model_json = scad.export_model_json(session)
payload = json.loads(model_json)
rebuilt = scad.replay_model_json(model_json)
```

Inspect these fields:

- `payload["graph"]["nodes"]`: canonical operation nodes in topological order.
- `node["op"]`: stable replay operation name.
- `node["params"]`: numeric / JSON-compatible parameter snapshot.
- `node["param_exprs"]`: optional expression links into `expression_graph`.
- `node["inputs"]`: upstream node ids used by replay.
- `payload["leaf_ids"]`: explicit final result node ids.
- `payload["expression_graph"]`: expression DAG used by expression-backed parameters.

## Important rule: source API is not always graph API

Many user-facing functions are convenience APIs. During an active `GraphSession`, they lower to canonical low-level nodes:

| Source call | Serialized graph result |
| --- | --- |
| `make_box_rsolid(...)` | rectangle profile + `make_extrude_rsolid` |
| `make_cylinder_rsolid(...)` | circle face + `make_extrude_rsolid` |
| `make_sphere_rsolid(...)` | profile + `make_revolve_rsolid` |
| `make_cone_rsolid(...)` | profile + `make_revolve_rsolid` |
| `make_rectangle_rwire(...)` | line edges + `make_wire_from_edges_rwire` |
| `make_circle_rface(...)` | circle edge + wire + face |
| `make_polyline_rwire(...)` | line edges + wire |
| `linear_pattern_rsolidlist(...)` | explicit `make_translate_rshape` nodes |
| `radial_pattern_rsolidlist(...)` | explicit `make_rotate_rshape` nodes |
| `helical_sweep_rsolid(...)` | helix wire + profile face + `make_sweep_rsolid` |

## Guides

- [Primitive and profile operations](primitives-and-profiles.md)
- [Features, booleans, transforms, patterns, and selectors](features-booleans-transforms.md)
- [Scalar field surfaces](scalar-fields.md)
- [Expressions and replay behavior](expressions-and-replay.md)

## Example

See [`../../../examples/07_serialization_operation_tree.py`](../../../examples/07_serialization_operation_tree.py). It intentionally exercises every canonical core operation and writes:

- `examples/out/serialization_operation_tree.model.json`
- `examples/out/serialization_operation_tree.summary.md`
- `examples/out/serialization_operation_tree.step`
