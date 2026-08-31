# Workflow: Sketch-Feature Modeling

Author a constraint-driven profile, promote it to topology, and build the part
from it with 3D features.

## Goal and scope

Use when the design intent is an editable sketch whose constraints carry the
meaning: plates with complex outlines, gasket profiles, brackets defined by
mating geometry, or any profile where dimensions are naturally relational.
Not for non-planar paths, exact freeform transcription, or block-and-feature
parts (use `single-part-modeling.md`).

## Task decomposition

```yaml
goal: part whose controlling profile is a solved, promotable Sketch
primary_domain: sketch-and-features
required_domains:
  - requirement-refinement
  - sketch-and-features
  - part-modeling
  - feature-tree-convention (discipline)
optional_domains:
  - assembly-and-product
  - export-and-translation
artifacts:
  - brief with plane mapping and constraint plan
  - sketch entities and constraints with stable ids
  - promoted Wire/Face
  - feature-built Solid or Part
validation_gates:
  - sketch solve status and remaining DOF recorded before promotion
  - promotion preserved measured geometry (closure/area/bounds compare)
  - post-feature solid gates from part-modeling
repair_routes:
  - solve drift -> sketch-and-features (add constraints or record DOF)
  - promotion changes geometry -> compare Wire vs Sketch from one parameter source
  - downstream feature fails -> part-modeling
```

## Steps

1. **Refine the requirement** (`domains/requirement-refinement.md`): include
   the sketch plane mapping (which model plane the profile lives on), closure
   requirements, and which dimensions are relational vs absolute.
2. **Plan entities and constraints** (`domains/sketch-and-features.md`):
   choose stable entity ids, list evidence-backed constraints, and identify
   the degrees of freedom that will remain free.
3. **Author the sketch functionally**: `make_sketch_rsketch` → `add_*_rsketch`
   → `constrain_*_rsketch`, each returning an updated `Sketch`. Arc endpoint
   order is meaningful (positive local angular sweep).
4. **Check the solve** (`inspect_sketch_rsketchresult`, diagnostic-only):
   backend, status code, remaining DOF. Add constraints or record the free
   DOF in the brief — never promote silently underconstrained geometry that
   matters.
5. **Promote**: `make_face_from_sketch_rface` (or
   `make_wire_from_sketch_rwire`) — promotion runs the solver internally and
   records `solve_snapshot` / `promotion_map` evidence in the graph.
6. **Build features** (`domains/part-modeling.md`): extrude, revolve, sweep,
   or loft the promoted profile; then booleans and detail features per
   `discipline/feature-ordering.md`, structured as Feature Tree Convention
   blocks with boundary comments (`discipline/feature-tree-convention.md`).
   This workflow is the primary sketch-tier authoring route: closed planar
   profiles and planar sweep paths are sketch API only.
7. **Ground and validate** (`discipline/geometric-validation.md`): QL facts
   after promotion and after each feature; verify brief dimensions.
8. **Package and export** as in `single-part-modeling.md` when needed.

## API pages to read

`make_sketch_rsketch`, `add_line_rsketch`, `add_arc_rsketch`,
`add_circle_rsketch`, the `constrain_*_rsketch` family used by the design,
`inspect_sketch_rsketchresult`, `make_face_from_sketch_rface`,
`make_wire_from_sketch_rwire`, then the feature APIs named in
`single-part-modeling.md`.

## Validation gates

- Solve status recorded; no unintended free DOF.
- When promotion could change measured geometry: build Wire and Sketch from
  one parameter source and compare closure, area, bounds, segmentation before
  promoting.
- Inner profiles used only with adjacent-carrier evidence that the loops share
  one generating profile.
- Post-feature: positive-volume closed solid; brief dimensions measured.

## Failure routes

- Sketch solve fails or drifts → missing/contradictory constraints; check
  status code and fix the constraint set, not the coordinates.
- Promotion invalid → profile not closed or self-intersecting; repair in the
  sketch, re-promote.
- Feature on promoted geometry fails → `part-modeling` repair routes.
- A Sketch wrapping a prebuilt Wire is not parametric intent: label the result
  coordinate-locked if that is what happened.

## Deliverables

Same as `single-part-modeling.md`, plus the recorded solve status and
remaining DOF.
