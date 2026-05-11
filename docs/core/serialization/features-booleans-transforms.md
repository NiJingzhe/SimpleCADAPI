# Features, Booleans, Transforms, Patterns, and Selection Serialization

This guide covers replayable feature operations, boolean operations, transforms, macro pattern lowering, and detail-feature selectors.

## Extrude

Source:

```python
profile = scad.make_rectangle_rface(4.0, 2.0)
solid = scad.extrude_rsolid(profile, (0, 0, 1), 3.0)
```

Serialized node:

```json
{
  "op": "make_extrude_rsolid",
  "params": {
    "direction": [0.0, 0.0, 1.0],
    "distance": 3.0
  },
  "inputs": ["node_for_profile"],
  "output_count": 1
}
```

Replay effect:

1. Replay the input profile node, which must output a `Wire` or `Face`.
2. Call `extrude_rsolid(profile, direction, distance)`.

## Revolve

Source:

```python
profile = scad.make_polyline_rwire(
    [(0.5, 0, 0), (1.2, 0, 0), (1.0, 0, 1.6), (0.5, 0, 1.6)],
    closed=True,
)
solid = scad.revolve_rsolid(
    profile,
    axis=(0, 0, 1),
    angle=360.0,
    origin=(0, 0, 0),
)
```

Serialized node:

```json
{
  "op": "make_revolve_rsolid",
  "params": {
    "axis": [0.0, 0.0, 1.0],
    "angle": 360.0,
    "origin": [0.0, 0.0, 0.0]
  },
  "inputs": ["node_for_profile"],
  "output_count": 1
}
```

Replay effect: replays the profile and calls `revolve_rsolid(profile, axis, angle, origin)`.

## Loft

Source:

```python
a = scad.make_rectangle_rwire(2.0, 1.0, center=(0, 0, 0))
b = scad.make_rectangle_rwire(1.0, 0.5, center=(0, 0, 3))
solid = scad.loft_rsolid([a, b], ruled=True)
```

Serialized node:

```json
{
  "op": "make_loft_rsolid",
  "params": {
    "profile_count": 2,
    "ruled": true
  },
  "inputs": ["node_for_a", "node_for_b"],
  "output_count": 1
}
```

Replay effect:

1. Replay all profile input nodes.
2. Call `loft_rsolid(profiles, ruled=...)`.

Profile geometry is recovered from `inputs`; only count/options are stored in `params`.

## Sweep

Source:

```python
profile = scad.make_circle_rface((0, 0, 0), 0.3, normal=(1, 0, 0))
path = scad.make_polyline_rwire([(0, 0, 0), (2, 0, 1), (4, 1, 1)])
solid = scad.sweep_rsolid(profile, path, is_frenet=False)
```

Serialized node:

```json
{
  "op": "make_sweep_rsolid",
  "params": {"is_frenet": false},
  "inputs": ["node_for_profile_face", "node_for_path_wire"],
  "output_count": 1
}
```

Replay effect:

1. Replay profile face from input 0.
2. Replay path wire from input 1.
3. Call `sweep_rsolid(profile, path, is_frenet=...)`.

## Helical sweep macro lowering

Source:

```python
profile = scad.make_rectangle_rwire(0.25, 0.18)
solid = scad.helical_sweep_rsolid(
    profile,
    pitch=0.7,
    height=2.2,
    radius=0.9,
)
```

Lowered serialized graph:

```text
profile wire
  -> make_face_from_wire_rface
make_helix_redge
  -> make_wire_from_edges_rwire
profile face + helix wire
  -> make_sweep_rsolid(is_frenet=true)
```

There is no canonical `helical_sweep` node. Replay rebuilds the helix and sweeps along it.

## Translate

Source:

```python
moved = scad.translate_shape(shape, (1.0, 2.0, 0.0))
```

Serialized node:

```json
{
  "op": "make_translate_rshape",
  "params": {"vector": [1.0, 2.0, 0.0]},
  "inputs": ["node_for_shape"],
  "output_count": 1
}
```

Replay effect: replays input shape and calls `translate_shape(shape, vector)`.

## Rotate

Source:

```python
rotated = scad.rotate_shape(shape, 90.0, axis=(0, 0, 1), origin=(0, 0, 0))
```

Serialized node:

```json
{
  "op": "make_rotate_rshape",
  "params": {
    "angle": 90.0,
    "axis": [0.0, 0.0, 1.0],
    "origin": [0.0, 0.0, 0.0]
  },
  "inputs": ["node_for_shape"],
  "output_count": 1
}
```

Replay effect: replays input shape and calls `rotate_shape(shape, angle, axis, origin)`.

Note: `rotate_shape(shape, 0.0)` returns the original shape and does not record a node.

## Mirror

Source:

```python
mirrored = scad.mirror_shape(
    shape,
    plane_origin=(0, 0, 0),
    plane_normal=(1, 0, 0),
)
```

Serialized node:

```json
{
  "op": "make_mirror_rshape",
  "params": {
    "plane_origin": [0.0, 0.0, 0.0],
    "plane_normal": [1.0, 0.0, 0.0]
  },
  "inputs": ["node_for_shape"],
  "output_count": 1
}
```

Replay effect: replays input shape and calls `mirror_shape(shape, plane_origin, plane_normal)`.

## Boolean union

Source:

```python
a = scad.make_box_rsolid(3, 2, 1)
b = scad.make_box_rsolid(3, 2, 1, bottom_face_center=(1.5, 0, 0))
result = scad.union_rsolid(a, b)
```

Serialized node:

```json
{
  "op": "make_union_rsolid",
  "params": {
    "input_count": 2,
    "clean": true,
    "glue": true,
    "tol": 1e-7
  },
  "inputs": ["node_for_a", "node_for_b"],
  "output_count": 1
}
```

Replay effect:

1. Replay all input solids.
2. Call `union_rsolid(all_solids)`.

Important: `union_rsolid` expects one connected solid result. If inputs remain disconnected, runtime and replay both raise an error instead of returning a compound.

## Boolean cut

Source:

```python
body = scad.make_box_rsolid(4, 4, 2)
tool = scad.make_cylinder_rsolid(0.8, 4, bottom_face_center=(0, 0, -1))
result = scad.cut_rsolidlist(body, tool)
```

Serialized node:

```json
{
  "op": "make_cut_rsolidlist",
  "params": {
    "tool_count": 1,
    "input_count": 2
  },
  "inputs": ["node_for_body", "node_for_tool"],
  "output_count": 1
}
```

Replay effect:

1. Replay first input as the body.
2. Replay remaining inputs as tools.
3. Call `cut_rsolidlist(body, tools)`.

## Boolean intersection

Source:

```python
a = scad.make_box_rsolid(2, 2, 2)
b = scad.make_box_rsolid(2, 2, 2, bottom_face_center=(1, 0, 0))
result = scad.intersect_rsolidlist(a, b)
```

Serialized node:

```json
{
  "op": "make_intersect_rsolidlist",
  "params": {
    "input_count": 2
  },
  "inputs": ["node_for_a", "node_for_b"],
  "output_count": 1
}
```

Replay effect: replays inputs and calls `intersect_rsolidlist(first, rest)`.

## Fillet

Source with serializable QL selector:

```python
from simplecadapi import ql as Q

selector = Q.edges().where(Q.curve_type("line")).take(4)
result = scad.fillet_rsolid(solid, selector, 0.25)
```

Serialized node:

```json
{
  "op": "make_fillet_rsolid",
  "params": {
    "radius": 0.25,
    "edge_count": 4,
    "selected_edges": [
      {
        "graph_id": "graph_xxx",
        "node_id": "node_xxx",
        "output_slot": 0,
        "kind": "EDGE",
        "topo_id": "edge_...",
        "selector_hint": {...}
      }
    ],
    "selected_edge_indices": [0, 1, 2, 3],
    "selection_query": {...}
  },
  "inputs": ["node_for_solid"],
  "output_count": 1
}
```

Replay edge resolution order:

1. Explicit topo refs in `selected_edges`
2. Stable indices in `selected_edge_indices`
3. Serializable `selection_query`
4. `selector_hint` fallback

Then replay calls `fillet_rsolid(solid, resolved_edges, radius)`.

## Chamfer

Source:

```python
selector = Q.edges().order_by(Q.center_axis("z"), desc=True).take(4)
result = scad.chamfer_rsolid(solid, selector, 0.15)
```

Serialized node shape is the same as fillet, except:

```json
{
  "op": "make_chamfer_rsolid",
  "params": {
    "distance": 0.15,
    "edge_count": 4,
    "selected_edges": [...],
    "selected_edge_indices": [...],
    "selection_query": {...}
  },
  "inputs": ["node_for_solid"]
}
```

Replay resolves edges using the same order and calls `chamfer_rsolid(solid, resolved_edges, distance)`.

## Shell

Source:

```python
selector = Q.faces().order_by(Q.center_axis("z"), desc=True).take(1).exactly(1)
result = scad.shell_rsolid(solid, selector, 0.25)
```

Serialized node:

```json
{
  "op": "make_shell_rsolid",
  "params": {
    "thickness": 0.25,
    "removed_face_count": 1,
    "selected_faces": [...],
    "selected_face_indices": [5],
    "selection_query": {...}
  },
  "inputs": ["node_for_solid"],
  "output_count": 1
}
```

Replay face resolution order:

1. Explicit topo refs in `selected_faces`
2. Stable indices in `selected_face_indices`
3. Serializable `selection_query`
4. `selector_hint` fallback

Then replay calls `shell_rsolid(solid, resolved_faces, thickness)`.

## Linear pattern macro lowering

Source:

```python
copies = scad.linear_pattern_rsolidlist(seed, (1, 0, 0), count=3, spacing=2.0)
```

When recording is active, this does not emit a `linear_pattern` node. It emits one translate node per generated copy:

```text
seed -> make_translate_rshape(vector=[0, 0, 0])
seed -> make_translate_rshape(vector=[2, 0, 0])
seed -> make_translate_rshape(vector=[4, 0, 0])
```

Replay effect: each generated copy is replayed as an ordinary translated shape.

## Radial pattern macro lowering

Source:

```python
copies = scad.radial_pattern_rsolidlist(
    seed,
    center=(0, 0, 0),
    axis=(0, 0, 1),
    count=4,
    total_rotation_angle=360.0,
)
```

When recording is active, this emits explicit rotate nodes for non-zero rotations. The zero-angle first copy is the original shape and does not create a rotate node.

```text
seed retained as first copy
seed -> make_rotate_rshape(angle=90)
seed -> make_rotate_rshape(angle=180)
seed -> make_rotate_rshape(angle=270)
```

Replay effect: copies are ordinary rotate operations, not a pattern macro.
