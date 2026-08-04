# STEP BREP Reverse Engineering

This document is the normative STEP BREP reverse-engineering reference shipped
with the SDK (repo path `docs/guides/step-brep-reverse-engineering.md`).
The inspection tooling lives in:

```text
src/simplecadapi/inspect/brep/
```

All of these functions are diagnostic, tool-grade APIs, not modeling
operations: they do not record graph nodes and must not run inside a
`GraphSession` or `@model` modeling script. Export or obtain the geometry
under test first, then call them outside the modeling script:

```python
from simplecadapi.inspect import brep

report = brep.inspect_step_rbrepinspection(path="part.step")
summary = brep.inspect_step_rsummary(path="part.step")
face = brep.inspect_step_entity_rdescriptor(
    path="part.step",
    entity_id="face:0",
)
neighborhood = brep.inspect_topology_neighborhood_rdescriptor(
    model_or_path="part.step",
    entity_id="face:0",
    depth=2,
)
section = brep.inspect_section_rdescriptor(
    model_or_path="part.step",
    origin=[0, 0, 10],
    normal=[0, 0, 1],
)
comparison = brep.compare_global_properties_rdescriptor(
    target="target.step",
    current="candidate.step",
)
evaluation = brep.evaluate_reconstruction_rdescriptor(
    target="target.step",
    current="candidate.step",
    replay_succeeded=True,
)
```

`inspect_step_rsummary` returns entity counts, bounding box, material
volume/area, centroid, and surface/curve type statistics.
`inspect_step_entity_rdescriptor` uses stable zero-based IDs (`body:0`,
`face:0`, `edge:0`, `vertex:0`) and returns geometry type, analytic
parameters, measurements, and adjacency. To reuse an index across many
queries, load the model first:

```python
model = brep.load_step_rbrepmodel(path="part.step")
summary = model.summary()
face = model.describe_entity("face:0")
neighbors = model.adjacency_details("face:0")
```

These IDs stay deterministic across repeated loads of the same unmodified
BREP, but they do not imply semantic correspondence between two different
models. Degenerate edges are reported uniformly as `DEGENERATE`, with the
underlying carrier type preserved in `underlying_curve_type`.

## Mindset: tools are not a pipeline

The built-in inspect functions are inspection tools, not a fixed workflow, and
they do not guarantee coverage of every question. Reverse engineering has no
"standard toolchain": for a specific case, the agent must write case-by-case
inspection code as needed — load the model and traverse entities directly,
compose multiple queries, and write model-specific
sampling/projection/adjacency analysis — to obtain more detailed information
about that model that the built-in primitives do not cover. Primitives are the
starting point, not the endpoint.

## Acceptance and stopping conditions (descending priority)

1. **BREP topology identity = complete reverse engineering (best endpoint)**:
   the geometric point set matches and the face-edge-vertex adjacency
   structure matches. Reach it when you can.
2. **Identical BREP structure with slightly different parameters:
   acceptable.** Export/serialization introduces floating-point error; minor
   parameter-level deviations (last-digit differences in radii, distances,
   etc.) are not failures and should not trigger further idle optimization.
3. **Structurally different but visually close BREP: a valid stopping
   condition only when "genuinely unable to optimize further".**
   "Genuinely unable to optimize further" is limited to the following two
   reasons, with evidence recorded:
   - no better feature operation order/combination can be found (feature-tree
     hypotheses are exhausted);
   - the required operation type is not yet supported by the SDK.
   Otherwise, "looks close" is not a reason to stop; keep iterating.

## Choosing an inspection strategy per problem

There is no fixed "reverse-engineering toolchain" to apply mechanically. First
clarify the current unknown and the acceptance evidence, then compose the
smallest set of primitives; for details the primitives do not cover, write
case-by-case inspection code for the model:

| Question | Preferred primitives |
|---|---|
| Global size, mass properties, topology scale | `inspect_step_rsummary`, `compare_global_properties_rdescriptor` |
| Single face/edge parameters and adjacency | `inspect_step_entity_rdescriptor`, `inspect_topology_neighborhood_rdescriptor` |
| Section profile, wall thickness, or local cut | `inspect_section_rdescriptor`, `compare_sections_rdescriptor` |
| Assembly tree and interface visualization | `inspect_step_components_rdescriptorlist`, `render_step_components_rpath` |
| Side-by-side multi-part observation | `render_step_components_colored_rpath` (direct `{component name: color name}` mapping, highlights multiple solids at once, with legend) |
| Where the difference is | `compare_material_rdescriptor`, `inspect_difference_regions_rdescriptor` |
| Local geometric error | `compare_boundary_distance_rdescriptor`, `compare_entities_rdescriptor` |
| Final exact-BREP gate | `compare_shapes_rbrepcomparison`, `compare_steps_rbrepcomparison` |

Start from cheap, bounded facts; add boundary sampling, boolean difference,
sections, rendering, or strict topology comparison only when the current
question requires them. The generic schema registry and fixed dispatch have
been removed: pick and call these composable APIs directly per task.

`inspect_step_rbrepinspection()` keeps the full knot, multiplicity, control
point, and rational weight data of B-spline curves/surfaces in its report.
`inspect_step_entity_rdescriptor()` defaults to low-latency local
investigation and returns only degree and count summaries. For a single
B-spline/Bezier edge set `include_curve_definition=True`; for a B-spline/
Bezier face set `include_surface_definition=True` and bound the control net
with `max_surface_control_points`. Surfaces return untrimmed carrier
definitions; trimming is still described by `u_range`, `v_range`, and the
face boundary.

For an initial inventory, call `inspect_step_rsummary(...,
include_parameter_groups=True)` to get carrier groups by analytic radius or
B-spline degree, multi-solid canonical axes, and Face/Edge adjacency
signatures. Each group is bounded by `max_parameter_groups` and
`examples_per_group`. These only describe multiplicities; they do not infer
arrays, symmetry, or repeated features — validate pattern hypotheses with
spatial positions and spacing.

For large outlines prefer `inspect_face_boundaries_rdescriptor(...,
compact=True)`. Compact mode keeps coedge order, orientation, type, length,
endpoints, and key parameters without returning 3D/UV sample arrays; request
detailed mode only when fitting or error measurement actually needs it. For
exact carriers add `include_curve_definitions=True` and optionally
`curve_definition_edge_ids=[...]`.

`inspect_section_rdescriptor(..., compact=True)` still completes contour
connectivity, nesting, and area computation, but returns only endpoints/exact
lengths of each section edge plus a contour summary. Set
`connection_tolerance` explicitly when section endpoints have tiny gaps;
section-local edge indexes are not stable IDs across models.

`compare_material_rdescriptor(..., include_components=False)` does a fast
volume estimate with a single intersection; subtracting a common volume can
lose a small residual on large-scale models and cannot by itself prove strict
material equality. For strict acceptance, difference-region localization, or
STEP difference export set `include_components=True` and
`boolean_tolerance=None`. Fuzzy booleans are diagnostic only.

Rendering and image-section features need the optional dependency:

```bash
uv sync --extra inspect
```

Performance principle: for closed solids, iterative acceptance prefers
validity, global properties, and bidirectional material difference to quickly
rule out large errors; but topology identity is the **best endpoint**, not an
optional extra — when the candidate is close in material and global
properties, check structural identity (see "Acceptance and stopping
conditions") and stop under the degraded conditions only after confirming
topology identity is unreachable.
`evaluate_reconstruction_rdescriptor()` includes global boundary sampling and
is not part of the cheap iteration path.
`compare_boundary_distance_rdescriptor`, `compare_sections_rdescriptor`,
`inspect_difference_regions_rdescriptor`, and local rendering should be called
per suspicious region as needed.

`compare_boundary_distance_rdescriptor` defaults to at most 200 samples and
supports `target_face_ids`/`current_face_ids` local ranges. Set
`include_records=True` explicitly when handing results to
`inspect_difference_regions_rdescriptor`; then pass the result as
`boundary_result` to avoid recomputation. Center slices remain available via
`compare_step_slices_rslicecomparison` but are not a default step.
