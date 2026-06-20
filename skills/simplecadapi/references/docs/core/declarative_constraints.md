# Declarative Constraint Status

Sketch constraints are supported through the isomorphic sketch API surface:

- `make_sketch_rsketch(...)`
- `add_point_rsketch(...)`
- `add_line_rsketch(...)`
- `add_circle_rsketch(...)`
- `constrain_*_rsketch(...)`
- `inspect_sketch_rsketchresult(...)` for non-recording diagnostics
- `make_wire_from_sketch_rwire(...)`
- `make_face_from_sketch_rface(...)`

When the modeling intent is a sketch/profile, use these sketch APIs as the only recommended construction path. Concrete geometry APIs such as `make_line_redge(...)` and `make_wire_from_edges_rwire(...)` remain for paths, pure geometry, and internal lowering targets.

Sketch document construction is functional: `add_*_rsketch(...)` and `constrain_*_rsketch(...)` return an updated `Sketch` instead of mutating the input document. Each sketch entity must have a stable explicit id, and constraints may use those ids directly:

```python
sketch = make_sketch_rsketch("plate_profile")
sketch = add_point_rsketch(sketch, "p0", 0.0, 0.0)
sketch = add_point_rsketch(sketch, "p1", 72.0, 0.0)
sketch = add_line_rsketch(sketch, "bottom", "p0", "p1")
sketch = constrain_horizontal_rsketch(sketch, "bottom")
sketch = constrain_distance_rsketch(sketch, "p0", "p1", 72.0)
```

`solve` is not a first-class modeling graph leaf. `make_wire_from_sketch_rwire(...)` and `make_face_from_sketch_rface(...)` run the sketch solver internally during `Sketch -> Wire/Face` promotion. Promotion graph nodes record `solve_snapshot` and `promotion_map` evidence, and promoted geometry receives `source_sketch`, `sketch_solve`, and sketch entity metadata/tags. `inspect_sketch_rsketchresult(...)` is diagnostic-only and does not record graph nodes.

In `.FCStd` translation, sketch promotion is represented by a visible `Sketcher::SketchObject`. `make_face_from_sketch_rface(...)` does not create a separate face bridge object in the graph path; downstream FreeCAD operations such as `Part::Extrusion` use the promoted Sketcher object as their base. FreeCAD Sketcher constraints are validated as they are added: constraints that are unsupported, crash-risky, or rejected as redundant by FreeCAD are recorded in `SimpleCADSketchConstraints.skipped` instead of being emitted in a way that would make the sketch unsolvable or force a synthetic base object.

# Assembly Constraint Status

Assembly containers, explicit part transforms, and declarative assembly constraints are temporarily removed from the public/support surface while the assembly system is redesigned.

Removed public APIs include:

- `Assembly`
- `PartHandle`
- `PointAnchor`
- `AxisAnchor`
- `AssemblyResult`
- `SolveReport`
- `make_assembly_rassembly`
- `clone_assembly_rassembly`
- `add_part_rassembly`
- `translate_part_rassembly`
- `rotate_part_rassembly`
- `solve_assembly_rresult`
- `constrain_coincident_rassembly`
- `constrain_concentric_rassembly`
- `constrain_offset_rassembly`
- `constrain_distance_rassembly`
- `clear_constraints_rassembly`
- `stack_rassembly`
- `stack`

Current supported workflows should model final parts as ordinary geometry:

- Use `translate_shape(...)`, `rotate_shape(...)`, and `mirror_shape(...)` for explicit placement.
- Use Python sequences of `Solid` objects plus `export_step([...], path)` / `export_stl(...)` for multi-body exports.
- Use `union_rsolid(...)`, `cut_rsolid(...)`, and `intersect_rsolid(...)` when a single merged solid is required.

`export_model_json(...)` no longer accepts `assembly=...`, and newly exported model JSON does not include `assembly`, `assembly_registry`, or `constraint_registry` fields.

The next assembly implementation should define a new assembly graph / constraint graph contract before reintroducing public APIs.
