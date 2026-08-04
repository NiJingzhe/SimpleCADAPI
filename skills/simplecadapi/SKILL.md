---
name: simplecadapi
description: Thin SimpleCAD SDK reference skill focused on the public API surface, core types, and current modeling workflows.
license: AGPL-3.0
compatibility: Documentation/reference bundle for current SimpleCADAPI surfaces.
metadata:
  project: simplecadapi
  version: 2.0.4b1
  package-name: simplecadapi
  package-version: 2.0.4b1
---

# SimpleCAD SDK Skill

## Philosophy
- This is a thin SDK reference skill: docs only.
- SDK source code is not bundled in this skill.

## Working From Repo Root
- Tool calls run from the repo root.
- Use one explicit skill root: `./skills/simplecadapi/` or `./workspace/skills/simplecadapi/`.
- Main doc paths:
  - `<skill_root>/SKILL.md`
  - `<skill_root>/references/docs/api/README.md`
  - `<skill_root>/references/docs/api/<api_name>.md`
  - `<skill_root>/references/docs/stdlib/README.md`
  - `<skill_root>/references/docs/stdlib/<stdlib_api_name>.md`
  - `<skill_root>/references/docs/core/<type_name>.md`
  - `<skill_root>/references/SDK_OVERVIEW.md`
  - `<skill_root>/references/SDK_SURFACES.md`
  - `<skill_root>/references/MODELING_WORKFLOWS.md`
  - `<skill_root>/references/inspect/brep-reverse-engineering.md`

## MUST Requirements
1. Read `SKILL.md`, `references/docs/api/README.md`, and `references/docs/stdlib/README.md` before choosing APIs.
2. Read the exact API Markdown page for every API you use.
3. Read the needed `core/` or exact `api/` docs when an API needs `Edge`, `Face`, `Wire`, `Solid`, `GraphSession`, `Sketch`, or expression types.
4. Prefer the standard parts library for standard parts before hand-modeling with core geometry APIs.
5. Follow the documented API signatures exactly.
6. When calling any SimpleCAD public API or standard-library function, use keyword arguments for every documented parameter; do not use positional arguments.
7. Use one `@model` entry point for replayable tasks, `@requires_session` for child builders, `capture_result(...)` for explicit outputs, and the returned `ModelResult` for model/session JSON and replay.
8. Use geometry APIs for integrated parts: profiles, features, booleans, transforms, tagging, QL inspection, serialization, and exports.
9. Use tags consistently through `apply_tag(shape=..., tag=...)` and `list_tags(shape=...)`; do not call shape member tag mutators.
10. Build and validate incrementally. Each step MUST include a small grounding `print`, and grounding MUST use QL where possible.
11. For inspection/debugging, query geometry with QL and print only the queried facts you need; do not print whole solids or full model objects.
12. Boolean operations return a single `Solid`.
13. Use `union_rsolid(...)` for boolean union.
14. For automated example/test harnesses, prefer the repo-local examples in `examples/` and avoid scratch scripts in `sandbox/`.
15. If union cannot produce exactly one merged solid, it fails explicitly; do not silently pick one piece.
16. If a single merged solid is required and union fails, slightly adjust part placement so intended bodies overlap/embed, then recompute.
17. If a task depends on model replay or interchange, prefer `ModelResult.model_json` or `export_model_json()` output over hand-written payloads.
18. For STEP/BREP inspection or target/candidate comparison, read `references/inspect/brep-reverse-engineering.md` completely.
19. Use `simplecadapi.inspect.brep` only outside `GraphSession` and `@model`; inspection functions are diagnostic tools, not modeling operations.
20. Reverse engineering is case-by-case: the built-in inspection primitives are tools, not a pipeline — write ad hoc inspection code for the specific model when built-ins do not answer the question. Acceptance hierarchy: BREP topology identity is the best endpoint (complete reverse engineering); identical structure with minor float-level parameter drift from export is acceptable; a visually-close but structurally different result is a valid stop only when no better feature operation order/combination exists or the SDK lacks the required operation type.

## Coding Standard (MUST)
This file/parameter standard applies to every modeling task. It is mandatory; deviation requires explicit user approval.

1. One part per file. Each distinct physical part is authored in its own script/module file. Never bundle multiple parts into one file and never split one part across files.
2. One assembly file. The full assembly is composed in exactly one file, which imports the part modules and positions them. A second top-level assembly file is not allowed.
3. Parameters live where they are used. Every parameter is declared in the file that directly consumes it: part parameters in the part file, assembly parameters in the assembly file. No central shared-parameters/dimensions module consumed across files.
4. Exposed tunable parameters MUST be Var declarations. Any parameter intended to be exposed or tunable MUST be declared with a Var in the file that uses it: `from simplecadapi import var` / `Var(name, default, ...)` (optionally with `unit`, `tolerance`). Bare numeric literals and magic numbers are NOT tunable parameters: if a value must be adjustable, declare it with `var()`/`Var`; otherwise keep it a plain constant in the file that uses it.

## Standard Parts Library
- SimpleCAD includes a standard library for parameterized mechanical parts.
- When the user needs a standard part and does not require complex custom geometry changes, use a standard-library function first.
- Current package-level standard-library surfaces include `scad.std.gear` for involute gears, internal ring gears, racks, and cycloidal discs, plus `scad.std.bearing` for ball bearing assemblies.
- Read `references/docs/stdlib/README.md` to discover standard-library functions.
- Read `references/docs/stdlib/<function_name>.md` before calling a standard-library function.
- Standard-library functions return normal SimpleCAD shapes or product assemblies that can be transformed, tagged, assembled, exported, and used with graph/model JSON workflows.

## Boolean result discipline
- `union_rsolid(...)`, `cut_rsolid(...)`, and `intersect_rsolid(...)` accept mixed inputs: standalone `Solid`, lists of `Solid`, and nested sequences.
- They return a single `Solid`.
- `union_rsolid(...)` already applies the package's default glue mode and a conservative internal tolerance.
- If a union cannot produce exactly one merged solid, it fails explicitly instead of returning multiple pieces.
- If a single merged solid is required but union fails, slightly move the parts so they overlap instead of merely touching, then recompute the union.

## Modeling Mental Model
- Start with intent: identify the part, its reference axes, critical profiles, and the features that produce the final solid.
- Build from lower-dimensional geometry to higher-dimensional geometry: `Vertex` / `Edge` / `Wire` / `Face` profiles first, then `Solid` features such as extrude, revolve, loft, and sweep.
- Keep modeling operations functional. Create new values from public functions such as `make_circle_rface(...)`, `extrude_rsolid(...)`, `cut_rsolid(...)`, and `fillet_rsolid(...)`.
- Use keyword arguments for all SimpleCAD function calls, for example `make_box_rsolid(width=10.0, height=20.0, depth=3.0)` instead of positional arguments.
- Use `@model` when the top-level model should be replayable, inspectable, exported as model JSON, or translated to another CAD system. It owns one `GraphSession`; reusable graph-producing builders use `@requires_session`.
- Treat model JSON as the interchange boundary. Prefer `ModelResult.model_json` and `ModelResult.replay()` for top-level models; use `export_model_json(session=...)` for lower-level direct sessions and `replay_model_json(json_str=...)` for standalone payloads.
- Use QL for precise grounding. Query faces, edges, centers, normals, areas, lengths, curve types, and tags; print only the facts needed to validate the current step.
- Use `get_edges(index)`, `get_faces(index)`, `get_wires(index)`, or `get_vertices(index)` when an indexed topology pick is intentional; these picks are preserved as geo select nodes in replayable graph workflows.
- Use tags for semantic intent and selection anchors, such as `role.mounting_surface`, `anchor.datum.primary`, `face.top`, or `group.fasteners`.
- Keep numeric and geometric facts in metadata or graph payloads, not in tags.
- When a QL-selected face or edge is used by a later feature, expect the graph/model workflow to preserve that selection as a stable geo select node.
- For FreeCAD translation, prefer canonical model JSON generated from a `GraphSession`; selected profiles and detail-feature selections should come from the graph rather than ad hoc object lookup.

## Tagging Mental Model
- Public tag attachment is `apply_tag(shape=..., tag=...)`.
- Public tag inspection is `list_tags(shape=...)`, which returns a stable sorted list.
- Tags are normalized lowercase dot-separated semantic tokens, for example `role.mounting_surface`, `anchor.datum.primary`, `group.fasteners`, `face.top`, or `solid.boolean.cut`.
- Do not encode numeric dimensions or descriptive geometry payloads in tags; store them in metadata such as `shape.get_metadata("geo")` or `shape.set_metadata(...)`.
- `apply_tag(...)` does not expose propagation controls. The SDK propagates role/anchor/group-style semantic tags downward and keeps topology-specific tags such as `face.*`, `edge.*`, `wire.*`, `vertex.*`, and `solid.*` local.
- Primitives, face auto-tagging, features, booleans, transforms, and tracking may add normalized topology/operation tags automatically.
- Prefer QL tag predicates (`ql.tag("role.*")`, `ql.select(...).where(...)`) for inspection and grounding.

## SDK Focus
- This skill is intended to describe the public CAD Python SDK surface.
- Prefer the generated API, stdlib, and core docs over environment/bootstrap instructions.
- API docs include an `Import Surface` section that distinguishes top-level exports, submodule APIs, and translator backend APIs under `simplecadapi.translator.<backend>`.
- Stdlib docs include an `Import Surface` section that identifies the package-level `simplecadapi.std.gear` module export.
- Use `references/SDK_OVERVIEW.md` for the package-level map.
- Use `references/SDK_SURFACES.md` for the main public surfaces.
- Use `references/MODELING_WORKFLOWS.md` for graph/model-oriented patterns.
- Use `references/inspect/brep-reverse-engineering.md` for case-specific STEP/BREP evidence gathering and acceptance.

## Example SDK usage

```python
import simplecadapi as scad
from simplecadapi import ModelResult, capture_result, model, requires_session
```

Typical replayable usage in a Python script:

```python
import simplecadapi as scad

@scad.model(graph_id="box")
def build_box():
    shape = scad.make_box_rsolid(width=10.0, height=20.0, depth=30.0)
    scad.capture_result(value=shape)
    return shape

result = build_box()
rebuilt = result.replay()
print(len(rebuilt))
```

Use the graph/model JSON workflow when the task needs reproducibility, interchange, or replayable outputs.

## References
- `references/SDK_OVERVIEW.md`
- `references/SDK_SURFACES.md`
- `references/MODELING_WORKFLOWS.md`
- `references/inspect/brep-reverse-engineering.md`
- `references/SDK_PACKAGE_SUMMARY.md`
- `references/docs/api/`
- `references/docs/stdlib/`
- `references/docs/core/`
