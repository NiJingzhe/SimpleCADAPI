# Workflow: Standard-Part Assembly

Build a mechanism composed of standard-library components — gears, ring gears,
racks, cycloidal discs, bearings — mated by explicit constraints.

## Goal and scope

Use for gearboxes, reducers, rack drives, cycloidal drives, and any assembly
whose components come from `scad.std.*` factories. Not for hand-modeled
components (author them via `single-part-modeling.md` first, then return
here) or standard parts requested alone with no assembly context
(`domains/standard-parts.md` suffices).

## Task decomposition

```yaml
goal: solved mechanism built from stdlib components and custom parts
primary_domain: standard-parts
required_domains:
  - requirement-refinement
  - standard-parts
  - part-modeling        # shafts, housings, carriers, spacers
  - assembly-and-product
optional_domains:
  - sketch-and-features
  - export-and-translation  # e.g. MJCF for simulation
artifacts:
  - per-part files including stdlib-based definitions
  - assembly file with kinematic constraints
  - solved package
validation_gates:
  - module/backlash/center-distance consistency per mesh
  - kinematic constraints reference measured axes with correct ratios
  - bearing seats match shaft/housing diameters
  - solve report and residual gates from assembly-product-build
repair_routes:
  - mesh interference or lock -> standard-parts (backlash, center distance)
  - constraint conflict -> assembly-and-product
  - custom interface mismatch -> part-modeling for that part
```

## Steps

1. **Refine the requirement**: stages, ratios, torque-relevant sizes, motion
   requirements, mounting interfaces, materials, and delivery targets.
2. **Select components** (`domains/standard-parts.md`): spur/helical/
   herringbone/bevel gears, ring gears, racks, cycloidal discs from
   `scad.std.gear`; bearings from `scad.std.bearing` — prefer the durable
   `build_ball_bearing` builder inside `@scad.assemble` definitions. Read the
   exact stdlib page for each factory before calling it.
3. **Compute the kinematics explicitly**: center distance from tooth counts
   and module, ratios per stage, backlash (typical starting point
   `0.05–0.1 × module`) — these are named parameters, not afterthoughts.
4. **Author custom parts** (shafts, housings, carriers) via
   `single-part-modeling.md`, with bearing seats and gear seats measured from
   the selected stdlib components (QL queries, not assumed dimensions). Part
   sources follow `discipline/feature-tree-convention.md` block structure;
   a shaft turned from segments is a chain of `build`/`subtract` blocks whose
   planar profiles are sketch tier.
5. **Compose and constrain** (`assembly-product-build.md` steps 4–7):
   `add_gear_constraint_rassembly` per mesh with the measured axes and ratio,
   `add_rack_pinion_constraint_rassembly` for rack drives,
   `add_revolute_constraint_rassembly` / `add_prismatic_constraint_rassembly`
   for motion, `add_belt_constraint_rassembly` for belt relations, one
   grounded root.
6. **Validate**: solve report and residuals; mesh clearances measured (not
   assumed); bearing bores and outer diameters against mated geometry; overall
   bounding box against the brief.
7. **Capture and export**: `capture` the package; export MJCF when simulation
   is requested (kinematics come from the constraint graph; loop-closing
   joints become equality/connect constraints).

## API pages to read

The stdlib pages for every factory used; the assembly pages listed in
`assembly-product-build.md`; `export_product_package_to_mjcf` when exporting
for simulation.

## Validation gates

- Every mesh: consistent module, computed center distance, explicit backlash,
  measured clearance after solving.
- Every kinematic constraint references a measured axis with the intended
  ratio.
- Bearing seats: bore against shaft, outer diameter against housing, measured
  on the solved assembly.
- Assembly gates from `assembly-product-build.md` all pass.

## Failure routes

- Mesh locks or interferes → re-check backlash and center distance before
  touching geometry.
- Bevel-gear orientation wrong → measure output axes with QL; do not assume
  factory orientation.
- Nested subassembly constraint conflict → solve the subassembly internally
  first (`assembly-product-build.md` failure routes).

## Deliverables

Component selection with parameters, per-part and assembly paths, package
path, kinematic verification evidence, solve/residual prints, assumptions.

**Required reading before authoring or editing any part source in this
workflow:** `discipline/feature-tree-convention.md` — the block-structured
sketch → basic body op → bool → modifier convention, its mandatory boundary
comments, and the sketch/geometry/primitive tier rules.
