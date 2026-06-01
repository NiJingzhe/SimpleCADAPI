# Primitive and Profile Operation Serialization

This guide covers replayable primitive/profile operations in the canonical operation graph.

All examples assume:

```python
import json
import simplecadapi as scad

with scad.GraphSession() as session:
    ...

payload = json.loads(scad.export_model_json(session))
```

In exported JSON, each operation appears in `payload["graph"]["nodes"]` as:

```json
{
  "node_id": "node_xxxxxxxx",
  "op": "make_line_redge",
  "params": {...},
  "inputs": [],
  "output_count": 1,
  "tags": [...],
  "display": {...},
  "param_exprs": {...},
  "context": {...}
}
```

`display`, `tags`, `context`, `semantic_delta`, and `topo_delta` are useful metadata. Replay primarily depends on `op`, `params`, and `inputs`.

## Point

Source:

```python
p = scad.make_point_rvertex(1.0, 2.0, 3.0)
```

Serialized node:

```json
{
  "op": "make_point_rvertex",
  "params": {"x": 1.0, "y": 2.0, "z": 3.0},
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_point_rvertex(x, y, z)` and returns a `Vertex`.

## Line edge

Source:

```python
edge = scad.make_line_redge((0, 0, 0), (5, 0, 0))
```

Serialized node:

```json
{
  "op": "make_line_redge",
  "params": {"start": [0.0, 0.0, 0.0], "end": [5.0, 0.0, 0.0]},
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_line_redge(start, end)` and returns an `Edge`.

### Segment aliases

`make_segment_redge(start, end)` is an alias of `make_line_redge(...)` and records the same `make_line_redge` node.

`make_segment_rwire(start, end)` lowers to:

1. `make_line_redge`
2. `make_wire_from_edges_rwire`

There is no canonical `make_segment_wire` node in model JSON.

## Circle edge, wire, and face

Source edge:

```python
edge = scad.make_circle_redge((0, 0, 0), 2.0, normal=(0, 0, 1))
```

Serialized node:

```json
{
  "op": "make_circle_redge",
  "params": {
    "center": [0.0, 0.0, 0.0],
    "radius": 2.0,
    "normal": [0.0, 0.0, 1.0]
  },
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_circle_redge(center, radius, normal)`.

Source wire:

```python
wire = scad.make_circle_rwire((0, 0, 0), 2.0)
```

Lowered serialized graph:

```text
make_circle_redge -> make_wire_from_edges_rwire
```

Source face:

```python
face = scad.make_circle_rface((0, 0, 0), 2.0)
```

Lowered serialized graph:

```text
make_circle_redge -> make_wire_from_edges_rwire -> make_face_from_wire_rface
```

There is no canonical `make_circle_wire` or `make_circle_face` node.

## Three-point arc edge and wire

Source edge:

```python
arc = scad.make_three_point_arc_redge(
    (0, 0, 0),
    (1, 1, 0),
    (2, 0, 0),
)
```

Serialized node:

```json
{
  "op": "make_three_point_arc_redge",
  "params": {
    "start": [0.0, 0.0, 0.0],
    "middle": [1.0, 1.0, 0.0],
    "end": [2.0, 0.0, 0.0]
  },
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_three_point_arc_redge(start, middle, end)`.

`make_three_point_arc_rwire(...)` lowers to:

```text
make_three_point_arc_redge -> make_wire_from_edges_rwire
```

## Angle arc edge and wire

Source edge:

```python
arc = scad.make_angle_arc_redge(
    center=(0, 0, 0),
    radius=1.0,
    start_angle=0.0,
    end_angle=1.57,
    normal=(0, 0, 1),
)
```

Serialized node:

```json
{
  "op": "make_angle_arc_redge",
  "params": {
    "center": [0.0, 0.0, 0.0],
    "radius": 1.0,
    "start_angle": 0.0,
    "end_angle": 1.57,
    "normal": [0.0, 0.0, 1.0]
  },
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_angle_arc_redge(center, radius, start_angle, end_angle, normal)`.

`make_angle_arc_rwire(...)` lowers to:

```text
make_angle_arc_redge -> make_wire_from_edges_rwire
```

## Spline edge and wire

Source edge:

```python
spline = scad.make_spline_redge([
    (0, 0, 0),
    (1, 1, 0),
    (2, 0, 0),
])
```

Serialized node:

```json
{
  "op": "make_spline_redge",
  "params": {
    "points": [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]],
    "tangents": null
  },
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_spline_redge(points, tangents=...)`.

`make_spline_rwire(points, closed=False)` lowers to:

```text
make_spline_redge -> make_wire_from_edges_rwire
```

For canonical replay, prefer open spline wires. Closed convenience forms may use fallback construction outside the low-level edge chain.

## Helix edge and wire

Source edge:

```python
helix = scad.make_helix_redge(
    pitch=0.7,
    height=2.2,
    radius=0.9,
    center=(0, 0, 0),
    dir=(0, 0, 1),
)
```

Serialized node:

```json
{
  "op": "make_helix_redge",
  "params": {
    "pitch": 0.7,
    "height": 2.2,
    "radius": 0.9,
    "center": [0.0, 0.0, 0.0],
    "dir": [0.0, 0.0, 1.0]
  },
  "inputs": [],
  "output_count": 1
}
```

Replay effect: calls `make_helix_redge(pitch, height, radius, center, dir)`.

`make_helix_rwire(...)` lowers to:

```text
make_helix_redge -> make_wire_from_edges_rwire
```

## Wire from edges

Source:

```python
a = scad.make_line_redge((0, 0, 0), (1, 0, 0))
b = scad.make_line_redge((1, 0, 0), (1, 1, 0))
wire = scad.make_wire_from_edges_rwire([a, b])
```

Serialized node:

```json
{
  "op": "make_wire_from_edges_rwire",
  "params": {"edge_count": 2},
  "inputs": ["node_for_a", "node_for_b"],
  "output_count": 1
}
```

Replay effect:

1. Replay each input edge node.
2. Collect input edge outputs in input order.
3. Call `make_wire_from_edges_rwire(edges)`.

The actual edge geometry is not duplicated inside this node; it is recovered through `inputs`.

## Face from wire

Source:

```python
face = scad.make_face_from_wire_rface(wire, normal=(0, 0, 1))
```

Serialized node:

```json
{
  "op": "make_face_from_wire_rface",
  "params": {"normal": [0.0, 0.0, 1.0]},
  "inputs": ["node_for_wire"],
  "output_count": 1
}
```

Replay effect:

1. Replay the input wire node.
2. Call `make_face_from_wire_rface(wire, normal=...)`.

## Rectangle wire and face lowering

Source:

```python
wire = scad.make_rectangle_rwire(4.0, 2.0, center=(0, 0, 0))
face = scad.make_rectangle_rface(4.0, 2.0, center=(0, 0, 0))
```

Lowered serialized graph:

```text
make_rectangle_rwire:
  make_line_redge x4 -> make_wire_from_edges_rwire

make_rectangle_rface:
  make_line_redge x4 -> make_wire_from_edges_rwire -> make_face_from_wire_rface
```

There is no canonical `make_rectangle_wire` or `make_rectangle_face` node.

## Polyline wire lowering

Source:

```python
wire = scad.make_polyline_rwire(
    [(0, 0, 0), (1, 0, 0), (1, 1, 0)],
    closed=False,
)
```

Lowered serialized graph:

```text
make_line_redge x(number_of_segments) -> make_wire_from_edges_rwire
```

If `closed=True`, one additional closing line edge is emitted.

There is no canonical `make_polyline_wire` node.

## Box, cylinder, sphere, and cone lowering

These user-facing primitive solids are intentionally lowered to canonical profile/feature operations.

### Box

Source:

```python
box = scad.make_box_rsolid(4.0, 2.0, 1.0)
```

Lowered serialized graph:

```text
make_line_redge x4
  -> make_wire_from_edges_rwire
  -> make_face_from_wire_rface
  -> make_extrude_rsolid
```

Replay effect: rebuilds the rectangular face, then extrudes it.

There is no canonical `make_box` node.

### Cylinder

Source:

```python
cyl = scad.make_cylinder_rsolid(1.0, 3.0)
```

Lowered serialized graph:

```text
make_circle_redge
  -> make_wire_from_edges_rwire
  -> make_face_from_wire_rface
  -> make_extrude_rsolid
```

There is no canonical `make_cylinder` node.

### Sphere

Source:

```python
sphere = scad.make_sphere_rsolid(1.5, center=(0, 0, 0))
```

Lowered serialized graph:

```text
profile edges/wire/face -> make_revolve_rsolid
```

There is no canonical `make_sphere` node.

### Cone / truncated cone

Source:

```python
cone = scad.make_cone_rsolid(1.2, 2.0, top_radius=0.4)
```

Lowered serialized graph:

```text
profile edges/wire/face -> make_revolve_rsolid
```

There is no canonical `make_cone` node.
