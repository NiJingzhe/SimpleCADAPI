# Project Overview

- Project: `simplecadapi`
- Version: `2.0.0`
- Runtime package: `simplecadapi==2.0.0`
- Skill cases module: `simplecad_self_evolve_cases`

## What this skill bundles

- Skill instructions (`SKILL.md`)
- Helper scripts (`scripts/`)
- Documentation references (`references/docs/`)
- Skill-local evolve package (`cases/simplecad_self_evolve_cases/`)

## What this skill does not bundle

- SDK source code (`src/simplecadapi`) is intentionally excluded.
- Runtime code is always resolved from site-packages.

## Runtime bootstrap strategy

0. Select a virtual environment interpreter (`PYTHON_BIN` if needed).
1. Try `import simplecadapi`.
2. If import fails, run `scripts/install.sh`.
3. Activate skill paths (`eval "$(scripts/with_skill.sh --print-env)"`).
4. Import skill-local cases from `simplecad_self_evolve_cases.evolve`.

## Optional Jupyter dependencies

- `jupyterlab>=4.5.5`
- `ipykernel>=6.29.5`
