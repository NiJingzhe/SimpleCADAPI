# Workflow: Export and Translation

Take a validated product package and produce the requested downstream
deliverables.

## Goal and scope

Use when geometry and product validation already passed and the remaining
work is format conversion. If the model still needs work, route to the owning
modeling workflow first — exports are deliverables, never validation.

## Task decomposition

```yaml
goal: requested export files from a validated .scadpkg
primary_domain: export-and-translation
required_domains:
  - requirement-refinement   # which formats and why
  - export-and-translation
optional_domains:
  - step-inspection          # roundtrip validation of exports
artifacts:
  - refreshed package (capture re-run if sources changed)
  - export reports per format
validation_gates:
  - package is current (sources unchanged since capture)
  - each export report read and printed
  - roundtrip validation when the consumer re-imports STEP
repair_routes:
  - stale export -> re-capture, re-export
  - coarse mesh -> tighten deflection parameters
  - backend missing -> report; no silent format substitution
```

## Steps

1. **Confirm the package is current**: if any source changed since the last
   `capture`, re-run the owning workflow's capture step. Exports are
   point-in-time deliverables. If this workflow edits any part source while
   making it current, the edit follows
   `discipline/feature-tree-convention.md` block structure.
2. **Select targets by consumer contract**
   (`domains/export-and-translation.md` table): editable FreeCAD document →
   `.FCStd`; neutral exchange → AP242 `.step`; DCC/surface inspection →
   `.obj`; additive manufacturing → `.stl`; MuJoCo simulation → MJCF.
3. **Export from the package path** (`scad.exporter.*` /
   `scad.translator.<backend>.*`), one call per target, keyword arguments.
4. **Read every report**: definition ids, occurrence/solid/triangle counts,
   material items, limitations. Print the facts; never assume success from a
   missing exception.
5. **Validate roundtrip when it matters**: consumers that re-import STEP →
   `validate_step_roundtrip_rdescriptor` on the exported file.
6. **Report**: file paths, per-format report facts, parameters chosen
   (deflection values), and any backend that was unavailable.

## API pages to read

`capture` (when re-capturing), the exporter page(s) for every format
requested, the translator page(s) for every backend requested, and
`validate_step_roundtrip_rdescriptor` when roundtrip validation applies.

## Validation gates

- Export report counts match the model's expectation (solids, occurrences,
  triangles).
- Tessellation accuracy chosen deliberately: `linear_deflection` in product
  units, `angular_deflection_degrees` for curved surfaces; tighter for small
  curved parts, looser for large simple geometry when size matters.
- MJCF: every intended joint present; loop-closing constraints emitted as
  equality/connect; public connectors only expose sites/endpoints.
- `.FCStd`: translation consumed the intended package revision.

## Failure routes

- FreeCAD/FreeCADCmd missing → report the missing backend; offer STEP as the
  neutral fallback and say so explicitly.
- STL/OBJ too coarse or too large → adjust deflection parameters, re-export;
  both formats share one tessellation pass.
- MJCF joints missing → the assembly lacked explicit constraints; return to
  `assembly-product-build.md`, do not hand-edit MJCF.

## Deliverables

Exported file paths, report facts per format, chosen parameters, unavailable
backends, and checks not run.

**Required reading before authoring or editing any part source in this
workflow:** `discipline/feature-tree-convention.md` — the block-structured
sketch → basic body op → bool → modifier convention, its mandatory boundary
comments, and the sketch/geometry/primitive tier rules.
