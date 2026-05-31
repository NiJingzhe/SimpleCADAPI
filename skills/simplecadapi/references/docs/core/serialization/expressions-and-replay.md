# Expressions and Replay Behavior

SimpleCADAPI 2.x stores expression-backed parameters in two places:

1. `node.params`: numeric / JSON-compatible snapshot used by simple replay
2. `node.param_exprs`: references into the top-level `expression_graph`

This lets consumers choose between:

- pure geometric replay using only the numeric snapshots
- parameter-aware import using `param_exprs + expression_graph`

## Source example

```python
import simplecadapi as scad

width = scad.var("width", 24.0, comment="plate width")
height = scad.var("height", 12.0, comment="plate height")
thickness = scad.var("thickness", 4.0, comment="plate thickness")

with scad.GraphSession() as session:
    plate = scad.make_box_rsolid(width, height, thickness)
    rib = scad.make_box_rsolid(width / 4.0, height, thickness * 2.0)
    part = scad.union_rsolid(plate, rib)

model_json = scad.export_model_json(session)
```

Because `make_box_rsolid(...)` lowers to profile + extrude nodes, the expressions appear on the lowered line/profile/extrude nodes rather than on a `make_box` node.

## Node-level JSON shape

A node with expression-backed params may look like:

```json
{
  "op": "make_extrude_rsolid",
  "params": {
    "direction": [0.0, 0.0, 1.0],
    "distance": 4.0
  },
  "param_exprs": {
    "distance": {"expr_id": "var_thickness"}
  },
  "inputs": ["node_for_profile"],
  "output_count": 1
}
```

`params.distance` is the evaluated snapshot. `param_exprs.distance` says the value came from expression node `var_thickness`.

For tuple/list params, `param_exprs` mirrors the shape of the parameter and uses `null` where no expression is present:

```json
{
  "params": {
    "start": [-12.0, -6.0, 0.0],
    "end": [12.0, -6.0, 0.0]
  },
  "param_exprs": {
    "start": [{"expr_id": "expr_a"}, {"expr_id": "expr_b"}, null],
    "end": [{"expr_id": "expr_c"}, {"expr_id": "expr_b"}, null]
  }
}
```

## Top-level expression graph

`payload["expression_graph"]` contains expression nodes for variables, constants, and arithmetic operations. The exact ids are stable within one exported payload but should not be treated as human-authored names.

Consumers that want parameterization should:

1. Build an expression table from `expression_graph.nodes`.
2. For each operation node, inspect `param_exprs`.
3. Replace or annotate corresponding numeric `params` entries with expression references.
4. Keep numeric `params` as fallback evaluated values.

Consumers that only want geometry can ignore `param_exprs` and `expression_graph`.

## Replay policy in current implementation

`replay_model_json(model_json)` currently uses the canonical low-level `graph` and the numeric values in `node.params`.

That means replay is deterministic with respect to the exported snapshot. It does not currently re-solve expressions with changed variable values.

In practical terms:

```python
width = scad.var("width", 24.0)
with scad.GraphSession() as session:
    box = scad.make_box_rsolid(width, 10, 2)

payload = scad.export_model_json(session)
rebuilt = scad.replay_model_json(payload)
```

Replay rebuilds using width `24.0`, because that is the value stored in `params`.

## Expression metadata is still important

Even though replay uses snapshots today, `param_exprs` and `expression_graph` are important for external tools:

- FreeCAD or CAD translators can reconstruct spreadsheet bindings.
- UI tools can display which dimensions are driven by variables.
- Future parametric replay can use the same expression references.
- Diffs can distinguish numeric constants from expression-derived values.

## Leaf ids and replayed outputs

The top-level `leaf_ids` field determines which node outputs are returned by replay:

```json
{
  "leaf_ids": ["node_final", "node_auxiliary"]
}
```

Replay behavior:

1. Execute every graph node in topological order.
2. Store each node output by `node_id`.
3. Return outputs for `leaf_ids` in order.

If an example creates many independent showcase shapes, `leaf_ids` may contain many node ids. This is expected: the graph is not required to have a single final part.

## Unsupported / lossy expression cases

- Python callables are not serialized as expressions.
- Scalar-field Python callables are recorded as `opaque_callable` and cannot be replayed.
- Some discrete selector data, topology refs, and counts are intentionally treated as JSON data rather than scalar expressions.

## Practical inspection snippet

```python
import json

payload = json.loads(model_json)
for node in payload["graph"]["nodes"]:
    if node.get("param_exprs"):
        print(node["node_id"], node["op"])
        print("  params:", node["params"])
        print("  param_exprs:", node["param_exprs"])
```

Use this to show the source-to-JSON relationship for expression-backed dimensions.
