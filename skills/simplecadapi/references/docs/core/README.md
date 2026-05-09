# SimpleCAD API Core Classes Documentation

This directory documents the core public object model for SimpleCADAPI.

SimpleCADAPI 2.x is OCP-native at runtime: public geometry objects are thin Python wrappers around OpenCascade/OCP shapes exposed through the `.wrapped` attribute. The package keeps the 1.x-style functional modeling API while adding graph recording, expression parameters, and replayable model JSON.

## Core Classes Overview

### Coordinate and tagging utilities

#### [CoordinateSystem](coordinate_system.md)
A right-handed 3D coordinate system for local modeling contexts and point/vector transformation.

#### [SimpleWorkplane](simple_workplane.md)
A context manager for temporarily modeling in a local coordinate system.

#### [TaggedMixin](tagged_mixin.md)
Shared tag and metadata behavior for geometry wrappers.

### Geometry wrappers

#### [Vertex](vertex.md)
A 0D topology wrapper with coordinate queries.

#### [Edge](edge.md)
A 1D topology wrapper for lines, arcs, circles, splines, and other curve edges.

#### [Wire](wire.md)
A connected path made from edges. Wires may be open or closed.

#### [Face](face.md)
A bounded surface with an outer wire and optional inner wires.

#### [Solid](solid.md)
A closed 3D body with volume, faces, edges, tags, and metadata.

#### [Compound](compound.md)
A collection wrapper for multiple geometry objects.

## Relationship Diagram

```text
TaggedMixin
├── Vertex (0D)
├── Edge (1D)
├── Wire (1D)  ← composed of edges
├── Face (2D)  ← bounded by wires
├── Solid (3D) ← bounded by faces
└── Compound   ← collection of shapes

CoordinateSystem ← independent utility
SimpleWorkplane  ← local modeling context
```

## Design Principles

- **Shape-first API**: users work with `Vertex`, `Edge`, `Wire`, `Face`, and `Solid`, not graph nodes.
- **Functional modeling style**: public operations return new geometry values, e.g. `make_box_rsolid(...)`, `cut_rsolidlist(...)`, `fillet_rsolid(...)`.
- **OCP-native runtime**: geometry construction, topology traversal, properties, booleans, transforms, and export use OCP/OpenCascade helpers.
- **Replayable v2 workflows**: `GraphSession` can record a canonical low-level operation graph and `export_model_json()` can serialize it for `replay_model_json()`.
- **Tags and metadata**: tags are useful for lightweight semantics; structured numeric facts should be stored in metadata such as `metadata["geo"]`.

## Basic Usage

```python
import simplecadapi as scad

with scad.SimpleWorkplane(origin=(0, 0, 0)):
    box = scad.make_box_rsolid(width=5, height=3, depth=2)

box.apply_tag("role.bracket")
box.set_metadata("material", "6061-T6")
box.auto_tag_faces("box")

top_faces = [face for face in box.get_faces() if face.has_tag("face.top")]
print(len(top_faces))
```

## Replayable Model JSON

```python
import simplecadapi as scad

with scad.GraphSession() as session:
    body = scad.make_box_rsolid(10, 10, 4)
    hole = scad.make_cylinder_rsolid(1.5, 8, bottom_face_center=(0, 0, -2))
    part = scad.cut_rsolidlist(body, hole)

payload = scad.export_model_json(session)
rebuilt = scad.replay_model_json(payload)
print(len(rebuilt))
```

## More Resources

- [API Reference Documentation](../api/)
- [Examples](../../examples/)
- [User Guide](../../README.md)
- [JSON Operation Graph Spec](operation_graph_json_spec.md)
- [Declarative Constraint Layout Design Draft](declarative_constraints.md)
- [SimpleCADAPI 2.0 Re-architecture Design](rearchitecture_2_0.md)
- [SimpleCADAPI 2.0 Requirements and Acceptance](rearchitecture_2_0_requirements.md)
