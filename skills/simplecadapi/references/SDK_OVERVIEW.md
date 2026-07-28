# SDK Overview

- Project: `simplecadapi`
- Version: `2.0.1`
- Package distribution: `simplecadapi==2.0.1`

## What this skill bundles

- Skill instructions (`SKILL.md`)
- Documentation references (`references/docs/`)
- Generated core API docs (`references/docs/api/`) and standard-library docs (`references/docs/stdlib/`)
- High-level SDK summaries (`references/*.md`)

## What this skill does not bundle

- SDK source code (`src/simplecadapi`) is intentionally excluded.
- Environment/bootstrap workflows are intentionally not the focus here.
- Self-evolving or skill-local case packaging is intentionally excluded.

## Main SDK surfaces

- Geometry and modeling operations in `docs/api/`.
- Standard parts library in `docs/stdlib/`, including `scad.std.gear`, `scad.std.bearing`, `scad.std.chain`, and `scad.std.fastener` factories.
- Core shape/type semantics in `docs/core/`.
- Graph/model serialization and replay APIs.
- Expression, parameter, and semantic reference types.
- Source-preserving tagging with `apply_tag(...)`, `apply_tag_rselection(...)`, scoped `list_tags(...)`/`explain_tag(...)`, and scoped QL tag predicates.
- Kernel-proven primitive and feature output roles with strict role-based output tag assignment for box, cylinder, extrude, revolve, fillet, chamfer, shell, loft, sweep, and twisted sweep.
- Serializable QL predicates for `output_role`, projected `source_binding`, and projected `source_topology` evidence.

## Preferred replayable workflow

- Record modeling steps inside `GraphSession` when you need replayable outputs.
- Export session/model payloads with `export_session_json()` and `export_model_json()`.
- Re-import or replay with `import_model_json()` and `replay_model_json()`.
