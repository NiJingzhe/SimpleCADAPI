# SDK Overview

- Project: `simplecadapi`
- Version: `2.0.0b1`
- Package distribution: `simplecadapi==2.0.0b1`

## What this skill bundles

- Skill instructions (`SKILL.md`)
- Documentation references (`references/docs/`)
- High-level SDK summaries (`references/*.md`)

## What this skill does not bundle

- SDK source code (`src/simplecadapi`) is intentionally excluded.
- Environment/bootstrap workflows are intentionally not the focus here.
- Self-evolving or skill-local case packaging is intentionally excluded.

## Main SDK surfaces

- Geometry and modeling operations in `docs/api/`.
- Core shape/type semantics in `docs/core/`.
- v2 graph/model serialization and replay APIs.
- Expression, parameter, and semantic reference types.

## Preferred v2 workflow

- Record modeling steps inside `GraphSession` when you need replayable outputs.
- Export session/model payloads with `export_session_json()` and `export_model_json()`.
- Re-import or replay with `import_model_json()` and `replay_model_json()`.
