# Declarative Constraints Layout Design Draft

## Background and Goals

The current SimpleCADAPI is primarily imperative modeling: developers need to manually provide specific coordinates, rotation angles, and offsets. For assemblies, this approach is costly in the following scenarios:

1. Geometric relationships are stable but dimensions change frequently (repeated position recalculation after parameter changes).
2. Dependencies between multiple parts are complex (one part change cascades to affect multiple parts).
3. Need to express "relationships" rather than "values" (e.g., coaxial, fit, equidistant distribution).

Web layout (such as HTML/CSS Flexbox) has proven an effective direction:

- Users declare constraints (alignment, distribution, spacing).
- Solvers propagate constraints in the layout tree and compute final geometric values.

This proposal aims to migrate this approach to the CAD SDK:

- Retain existing imperative APIs;
- Add an optional declarative assembly layer;
- Let users describe assembly relationships, with the SDK computing each part's final pose.

## Current Implementation Status (feat/declarative-constraints-layout)

The current branch provides a runnable MVP with the following core capabilities:

- New module: `simplecadapi.constraints`
- New objects: `Assembly`, `PartHandle`, `PointAnchor`, `AxisAnchor`, `AssemblyResult`
- Supports mixed paradigm:
  - First imperative pre-positioning (`translate_part` / `rotate_part`)
  - Then declarative constraint solving (`coincident` / `concentric` / `offset` / `distance`)
- Supports 1D container syntax sugar: `stack(...)`
- `stack(...)` adds main axis distribution parameter: `justify=start|center|end|space-between`
- When `justify=center/end/space-between` is needed, use `bounds=(start_anchor, end_anchor)` to specify the container's main axis boundary.

Current layout implementation uses a **BBox-first** strategy:

- Alignment and distribution are primarily based on `bbox.*` anchors (AABB).
- This is consistent with Flexbox's box model thinking, but is approximate in 3D:
  When parts rotate, AABB changes and layout results change accordingly.
- OBB/feature face anchors can be added later to reduce approximation errors from rotation.
- Supports assembly tree parent-child relationships and local/world transform propagation.

Framework-style constraints (functional) have been explicitly categorized into two types of mappings:

1. **Type-1 lifting mappings** (parameter space -> CAD object space)
   - E.g.: `make_*_rsolid`, `make_assembly_rassembly`
2. **Type-2 algebraic transform mappings** (CAD object space -> CAD object space/result space)
   - E.g.: `translate_part_rassembly`, `constrain_offset_rassembly`, `stack_rassembly`
   - Solving uses `solve_assembly_rresult`, ensuring input assembly objects are not modified

Corresponding functional APIs (do not modify input) include:

- `make_assembly_rassembly`
- `clone_assembly_rassembly`
- `add_part_rassembly`
- `translate_part_rassembly` / `rotate_part_rassembly`
- `constrain_coincident_rassembly` / `constrain_concentric_rassembly`
- `constrain_offset_rassembly` / `constrain_distance_rassembly`
- `stack_rassembly`
- `solve_assembly_rresult`

Functional pipeline example:

```python
import simplecadapi as scad

asm0 = scad.make_assembly_rassembly([
    ("sleeve", sleeve_solid),
    ("rod", rod_solid),
])

asm1 = scad.translate_part_rassembly(asm0, "rod", (3.0, -2.0, 4.0))
asm2 = scad.constrain_concentric_rassembly(
    asm1,
    asm1.part("sleeve").axis("z"),
    asm1.part("rod").axis("z"),
)
asm3 = scad.constrain_offset_rassembly(
    asm2,
    asm2.part("sleeve").anchor("bbox.bottom"),
    asm2.part("rod").anchor("bbox.bottom"),
    3.0,
    axis="z",
)

result = scad.solve_assembly_rresult(asm3)
```

Example (mixed usage):

```python
import simplecadapi as scad

asm = scad.Assembly("demo")
sleeve = asm.add_part("sleeve", sleeve_solid)
rod = asm.add_part("rod", rod_solid)

# 命令式预定位
asm.translate_part("rod", (3.0, -2.0, 4.0), frame="world")

# 声明式约束
asm.concentric(sleeve.axis("z"), rod.axis("z"))
asm.offset(sleeve.anchor("bbox.bottom"), rod.anchor("bbox.bottom"), 3.0, axis="z")

result = asm.solve()
scad.export_step(result.solids(), "assembly.step")
```

## Scope

### In Scope (Phase 1)

- Assembly pose solving (rigid body 6DOF, no part topology modification).
- Basic constraint types:
  - `coincident` (point/plane/axis coincidence)
  - `concentric` (coaxial)
  - `parallel` / `perpendicular` (directional relationships)
  - `distance` (spacing)
  - `offset` (offset along normal or axis direction)
- "Flex-like" 1D layout containers:
  - `stack(axis="x|y|z")`
  - `gap`
  - `justify` (start/center/end/space-between)
  - `align` (start/center/end/stretch*)

`stretch` in CAD does not perform geometric stretching; it only means aligning to the alignment baseline.

### Out of Scope (Phase 1)

- Parameter-driven topology rebuilding (e.g., automatic hole diameter changes, chamfer regeneration).
- General nonlinear symbolic solvers (CAS level).
- Complete sketch constraint system (2D sketch solver).

## Core Abstractions

### 1) Assembly Node

Each node contains:

- `name`
- `solid`
- `local frame` (node local coordinate system)
- `current transform` (variables to be solved)
- `anchors` (anchor points that can be referenced by constraints)

### 2) Anchor

Anchors are used to extract constrainable objects from geometry:

- `point`: 3D point
- `axis`: Directed line (point + direction)
- `plane`: Plane (point + normal)
- `frame`: Local coordinate system

Suggested built-in anchor sources:

- Bounding box: `bbox.min/max/center`
- Principal axes: `axis.x/y/z`
- Named faces: `face("top")`, `face("bottom")` (reuse existing tag mechanism)

### 3) Constraint

Constraints consist of:

- `type`
- `lhs anchor` / `rhs anchor`
- `value` (optional, e.g., distance)
- `priority` (hard/soft)
- `weight` (soft constraint weight)

### 4) Layout Container

Containers are constraint syntax sugar, compiled into a set of basic constraints:

- E.g., `stack([A,B,C], axis="z", gap=8)`
  - `B.min_z = A.max_z + 8`
  - `C.min_z = B.max_z + 8`
  - Plus alignment constraints (e.g., XY centering)

## API Draft

```python
import simplecadapi as scad
from simplecadapi.constraints import Assembly, stack

asm = Assembly(name="shock_absorber")

sleeve = asm.add_part("sleeve", sleeve_solid)
rod = asm.add_part("rod", rod_solid)
spring = asm.add_part("spring", spring_solid)

asm.concentric(rod.axis("z"), sleeve.axis("z"))
asm.offset(rod.anchor("bottom"), sleeve.anchor("bottom"), 10.0)
asm.distance(rod.anchor("top"), sleeve.anchor("top"), min_value=5.0)

stack(
    asm,
    parts=[spring],
    axis="z",
    relative_to=sleeve,
    align="center",
    justify="start",
    gap=8.0,
)

result = asm.solve()
solids = result.solids()
scad.export_step(solids, "shock_absorber_assembly.step")
```

## Solving Strategy (Layered)

### Layer A: Parsing and Normalization

- Convert constraints and container rules into residual equations.
- Map anchor references to real-time geometric query functions.

### Layer B: Graph Constraint Propagation (Fast Path)

- First perform topological solving for directly propagatable rigid constraints:
  - Coaxial + offset + alignment can directly derive partial poses.
- Build dependency graph and perform incremental updates (dirty propagation).

### Layer C: Numerical Solving (Fallback)

- Use least squares solving for remaining degrees of freedom (hard constraints have highest priority).
- For over-constrained or contradictory constraints, output diagnostic reports:
  - Conflicting constraint pairs
  - Constraints with highest residuals
  - Recommended relaxation items (downgrade from hard to soft)

## Result Model

`solve()` returns an object that should contain:

- `transforms`: Final pose for each part
- `solids()`: List of solids with poses applied
- `report`: Solving information
  - Whether converged
  - Number of iterations
  - Maximum residual
  - Conflict/over-constraint description

## Compatibility Strategy with Existing API

1. No changes to existing `operations.py` imperative interfaces.
2. New independent module (suggested `simplecadapi.constraints`).
3. Export still reuses `export_step` / `export_stl`, can directly export `result.solids()`.

## Milestone Plan

### M0 - Design and Feasibility Verification (Current Phase)

- Output this design document.
- Define minimum API surface.
- Select first batch of constraint types and diagnostic formats.

### M1 - Minimum Viable Prototype (MVP)

- `Assembly.add_part()`
- Anchors: `bbox` + `axis` + `face tag`
- Constraints: `concentric` + `offset` + `distance`
- Solving: Support single-chain assemblies (no loops)

### M2 - Flex-like Layout Containers

- `stack(axis, gap, align, justify)`
- Compile container rules into constraints
- Support simple incremental updates

### M3 - Diagnostics and Engineering

- Conflict localization and interpretable error messages
- Solving logs and visual output (text reports)
- Unit test coverage for typical assembly scenarios

### M4 - Advanced Capabilities

- Soft constraint weight system
- Complex constraint loops
- Performance optimization (caching, partitioned solving)

## Testing Recommendations

At least cover the following scenarios:

1. **Basic convergence**: Coaxial + offset + alignment, unique result.
2. **Under-constrained**: Clear warning when degrees of freedom are not locked.
3. **Over-constrained**: Conflict diagnostics when constraints are contradictory.
4. **Incremental updates**: Modifying a single parameter triggers only local recalculation.
5. **Export consistency**: `result.solids()` can directly export STEP/STL.

## Risks and Mitigations

- **Risk:** Constraint semantics too abstract, making the API hard to use.
  **Mitigation:** Start with high-frequency assembly scenarios, providing only a few strongly semantic constraints.

- **Risk:** Numerical solving is unstable.
  **Mitigation:** First do graph propagation fast path; numerical solving only handles remaining degrees of freedom.

- **Risk:** Conflict with existing user code.
  **Mitigation:** New module isolation, disabled by default, strictly maintain backward compatibility.

## Conclusion

Migrating the Flexbox-style "declare relationships -> solve geometry" paradigm to the CAD SDK is feasible and can significantly improve assembly modeling efficiency and maintainability. It is recommended to use "assembly pose constraints + 1D container layout" as the Phase 1 entry point, deliver an MVP first, and then gradually enhance solving capabilities and diagnostic experience.