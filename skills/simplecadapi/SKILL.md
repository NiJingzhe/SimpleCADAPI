---
name: simplecadapi
description: Build, assemble, inspect, reconstruct, and export parametric CAD models with the SimpleCADAPI Python SDK. Use for SimpleCAD geometry modeling, constrained sketches, parts and assemblies, standard gears and bearings, STEP/BREP inspection and reconstruction, durable product packages, model JSON replay, and CAD backend translation.
license: AGPL-3.0
metadata:
  project: simplecadapi
  version: 2.0.4b3
  package-name: simplecadapi
  package-version: 2.0.4b3
---

# SimpleCAD SDK Skill

Plan and route CAD tasks with the SimpleCADAPI SDK: classify the
request, load the workflow that owns it, follow its task-domain and
discipline references, and read exact API pages only for the APIs a
step names.

## Task routing

Read exactly one workflow first, per the user's goal:

| User goal | Workflow |
| --- | --- |
| Model one physical part | `references/workflows/single-part-modeling.md` |
| Constraint-driven profile as design intent | `references/workflows/sketch-feature-modeling.md` |
| Multi-part product, connectors, constraints, package | `references/workflows/assembly-product-build.md` |
| Rebuild an editable model from a STEP file | `references/workflows/step-reconstruction.md` |
| Mechanism from stdlib gears/bearings | `references/workflows/standard-part-assembly.md` |
| Export/translate a validated package | `references/workflows/export-and-translation.md` |

Read-only questions about an existing STEP file do not need a
workflow: `references/domains/step-inspection.md` covers them
directly.

## Global rules (every task)

1. Refine the requirement into a brief before modeling
   (`references/domains/requirement-refinement.md`).
2. Use keyword arguments for every documented public API and
   stdlib function, except the canonical durable export call
   `capture(result, path)`, whose two required arguments are
   positional.
3. One part per file; one assembly file per product; parameters
   live in the file that consumes them; exposed tunable parameters
   are `var()`/`Var` declarations (optionally with `unit`,
   `tolerance`).
4. Booleans (`union_rsolid`, `cut_rsolid`, `intersect_rsolid`)
   accept mixed inputs and return exactly one `Solid`; union
   defaults to `glue=False` with a conservative scale-relative
   tolerance and fails explicitly when it cannot produce one
   merged solid.
5. Build and validate incrementally: each major step prints small
   QL-derived facts; grounding uses QL wherever possible; never
   print whole solids or full model objects.
6. Tags: attach with `apply_tag(shape=..., tag=...)` (LOCAL scope —
   it never propagates downward); inspect with
   `list_tags(shape=...)`; keep numeric facts in metadata, never in
   tags.
7. `@scad.part` for one physical single-solid product;
   `@scad.assemble` for assemblies with explicit definitions.
   Neither nests inside an active `GraphSession`. Durable delivery
   is `capture(result, "out/product.scadpkg")` in one call.
8. `simplecadapi.inspect.brep` is diagnostic-only and rejected
   inside `GraphSession`; obtain/export geometry first, inspect
   outside.
9. Standard parts first: before hand-modeling a gear, ring gear,
   rack, cycloidal disc, or bearing, check `scad.std.gear` /
   `scad.std.bearing`.
10. Read `references/docs/guides/cache-build-workflow.md` in full
    before configuring persistent cache, durable builds, or cache
    maintenance; cache mutation requires explicit confirmation.

## Boundaries

- `.scadpkg` is the canonical durable product; STL/OBJ/MJCF are
  point-in-time exports, never editable sources.
- Model JSON is the replay/interchange contract for explicit
  `GraphSession` flows; never hand-author payloads.
- No claims of strength, fatigue, thermal, vibration, tolerance
  compliance, or regulatory fitness without the corresponding
  analysis actually run.

## Reading order

```text
SKILL.md (this router)
-> references/workflows/<scenario>.md
-> the domains/ and discipline/ files the workflow names
-> references/docs/api|stdlib|core/<exact page>.md for each API a step uses
```

Do not read the full API index or stdlib index up front; the
workflow names what to load. Every API used still gets its exact
page read (`references/docs/api/<name>.md`,
`references/docs/stdlib/<name>.md`,
`references/docs/core/<type>.md`).

## Example SDK usage

```python
import simplecadapi as scad
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession(graph_id="box") as session:
    shape = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)
    session.capture_result(value=shape)
    payload = export_model_json(session=session)

rebuilt = replay_model_json(json_str=payload)
print(len(rebuilt))
```

## References

- `references/README.md` — skill layer structure
- `references/workflows/` — six goal-oriented workflows
- `references/domains/` — seven capability domains
- `references/discipline/` — modeling knowledge and invariants
- `references/SDK_OVERVIEW.md` — package-level map
- `references/inspect/brep-reverse-engineering.md`
- `references/docs/guides/reconstruction-agent-test-prompt.md`
- `references/docs/guides/reconstruction-agent-strategy.md`
- `references/docs/guides/cache-build-workflow.md`
- `references/docs/api/`, `references/docs/stdlib/`, `references/docs/core/`
