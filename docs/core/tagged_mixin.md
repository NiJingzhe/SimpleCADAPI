# TaggedMixin

## Overview

`TaggedMixin` is the internal tag and metadata storage mixin used by `Vertex`, `Edge`, `Wire`, `Face`, and `Solid`. It owns the shared `_tags`, `_metadata`, and `_runtime` stores for topology wrappers.

User code should not call member tag mutators. The public tag API is functional:

- `apply_tag(shape, tag)` attaches one normalized tag.
- `list_tags(shape)` returns tags in deterministic sorted order.
- `select_faces_by_tag(...)`, `select_edges_by_tag(...)`, and QL predicates such as `ql.tag("role.*")` provide selection/query helpers.

## Tagging Mental Model

- Tags are normalized lowercase dot-separated semantic tokens.
- Examples: `role.mounting_surface`, `anchor.datum.primary`, `group.fasteners`, `face.top`, `edge.boundary`, `wire.outer`, `solid.boolean.cut`.
- `apply_tag(shape, tag)` does not expose propagation controls.
- The standard policy propagates `role.*`, `anchor.*`, `group.*`, and a few legacy bare semantic tags downward.
- Topology-specific tags such as `face.*`, `edge.*`, `wire.*`, `vertex.*`, and `solid.*` stay local.
- Numeric dimensions, measurements, and rich descriptive payloads belong in metadata, not tags.
- Geometry builders store structured geometry facts under `metadata["geo"]`.

## Public Tag Usage

```python
import simplecadapi as scad

box = scad.make_box_rsolid(width=5, height=3, depth=2)
scad.apply_tag(box, "role.bracket")
box.auto_tag_faces("box")

print(scad.list_tags(box))
top_faces = [face for face in box.get_faces() if "face.top" in scad.list_tags(face)]
print(len(top_faces))
```

## Propagation Example

```python
import simplecadapi as scad

body = scad.make_box_rsolid(10, 10, 2)
scad.apply_tag(body, "role.mounting_plate")

face_hits = [face for face in body.get_faces() if "role.mounting_plate" in scad.list_tags(face)]
edge_hits = [edge for edge in body.get_edges() if "role.mounting_plate" in scad.list_tags(edge)]

print(len(face_hits), len(edge_hits))
```

## Auto Tags

Primitives and modeling operations may attach normalized tags automatically:

- Primitive tags such as `geom.primitive.box`, `geom.primitive.cylinder`, and `geom.primitive.sphere`.
- Face tags from `auto_tag_faces(...)`, such as `face.top`, `face.bottom`, `face.side`, and `face.surface`.
- Wire tags such as `wire.outer` and `wire.inner`.
- Operation/tracking tags such as `solid.boolean.cut`, `op.cut.modified`, or `op.extrude.generated`.

## Metadata Methods

`set_metadata(key, value)` and `get_metadata(key, default=None)` remain shape member methods for structured data.

```python
import simplecadapi as scad

part = scad.make_box_rsolid(10, 8, 5)
scad.apply_tag(part, "role.housing")
part.set_metadata("material", "6061-T6")
part.set_metadata("part_number", "mp-001-a")

print(part.get_metadata("material"))
print(part.get_metadata("geo"))
```

## QL Queries

```python
import simplecadapi as scad
from simplecadapi import ql as Q

body = scad.make_box_rsolid(10, 10, 2)
scad.apply_tag(body, "role.mounting_plate")
body.auto_tag_faces("box")

top_faces = Q.select(body.get_faces()).where(Q.tag("face.top")).all()
role_faces = Q.select(body.get_faces()).where(Q.tag("role.*")).all()

print(len(top_faces), len(role_faces))
```
