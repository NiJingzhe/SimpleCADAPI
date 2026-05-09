---
name: simplecadapi
description: Thin SimpleCAD SDK reference skill focused on the public API surface, core types, and v2 modeling workflows.
license: MIT
compatibility: Documentation/reference bundle for SimpleCADAPI v2 surfaces.
metadata:
  project: simplecadapi
  version: 2.0.0b1
  package-name: simplecadapi
  package-version: 2.0.0b1
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
  - `<skill_root>/references/docs/core/<type_name>.md`
  - `<skill_root>/references/SDK_OVERVIEW.md`
  - `<skill_root>/references/SDK_SURFACES.md`
  - `<skill_root>/references/V2_MODELING_WORKFLOWS.md`

## MUST Requirements
1. Read `SKILL.md` and `references/docs/api/README.md` before choosing APIs.
2. Read the exact API Markdown page for every API you use.
3. Read the needed `core/` docs when an API needs `Edge`, `Face`, `Wire`, `Solid`, `Assembly`, `GraphSession`, `Sketch`, or expression types.
4. Follow the documented API signatures exactly.
5. Use the graph/model JSON workflow for v2 tasks: `GraphSession`, `export_session_json`, `export_model_json`, `import_model_json`, and `replay_model_json`.
6. Use geometry APIs for integrated parts and declarative constraints for final assemblies.
7. Use tags consistently.
8. Build and validate incrementally. Each step MUST include a small grounding `print`, and grounding MUST use QL where possible.
9. For inspection/debugging, query geometry with QL and print only the queried facts you need; do not print whole solids, assemblies, or full model objects.
10. Boolean operations return a single `Solid`.
11. Use `union_rsolid(...)` for boolean union.
12. For automated example/test harnesses, prefer the repo-local examples in `examples/` and avoid scratch scripts in `sandbox/`.
13. If union cannot produce exactly one merged solid, it fails explicitly; do not silently pick one piece.
14. If a single merged solid is required and union fails, slightly adjust part placement so intended bodies overlap/embed, then recompute.
15. If a task depends on model replay or interchange, prefer `export_model_json()` output over hand-written payloads.

## Boolean result discipline
- `union_rsolid(...)`, `cut_rsolidlist(...)`, and `intersect_rsolidlist(...)` accept mixed inputs: standalone `Solid`, lists of `Solid`, and nested sequences.
- They return a single `Solid`.
- `union_rsolid(...)` already applies the package's default glue mode and a conservative internal tolerance.
- If a union cannot produce exactly one merged solid, it fails explicitly instead of returning multiple pieces.
- If a single merged solid is required but union fails, slightly move the parts so they overlap instead of merely touching, then recompute the union.

## SDK Focus
- This skill is intended to describe the public CAD Python SDK surface.
- Prefer the generated API and core docs over environment/bootstrap instructions.
- Use `references/SDK_OVERVIEW.md` for the package-level map.
- Use `references/SDK_SURFACES.md` for the main public surfaces.
- Use `references/V2_MODELING_WORKFLOWS.md` for graph/model-oriented patterns.

## Example SDK usage

```python
import simplecadapi as scad
from simplecadapi import GraphSession, export_model_json, make_box_rsolid
```

Typical v2 usage in a Python script:

```python
import simplecadapi as scad
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession() as session:
    shape = scad.make_box_rsolid(10.0, 20.0, 30.0)

model_json = export_model_json(session)
rebuilt = replay_model_json(model_json)
print(len(rebuilt))
```

Use the graph/model JSON workflow when the task needs reproducibility, interchange, or replayable v2 outputs.

## References
- `references/SDK_OVERVIEW.md`
- `references/SDK_SURFACES.md`
- `references/V2_MODELING_WORKFLOWS.md`
- `references/SDK_PACKAGE_SUMMARY.md`
- `references/docs/api/`
- `references/docs/core/`
