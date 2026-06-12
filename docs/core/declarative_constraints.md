# Declarative Constraint Status

Sketch constraints are supported through the isomorphic sketch API surface:

- `make_sketch_rsketch(...)`
- `make_sketch_point_rsketchref(...)`
- `add_line_rsketch(...)`
- `add_circle_rsketch(...)`
- `constrain_*_rsketch(...)`
- `solve_sketch_rsketchresult(...)`
- `make_wire_from_sketch_rwire(...)`
- `make_face_from_sketch_rface(...)`

When the modeling intent is a sketch/profile, use these sketch APIs as the only recommended construction path. Concrete geometry APIs such as `make_line_redge(...)` and `make_wire_from_edges_rwire(...)` remain for paths, pure geometry, and internal lowering targets.

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
