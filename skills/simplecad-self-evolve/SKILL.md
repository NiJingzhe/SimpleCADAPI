---
name: simplecad-self-evolve
description: Package SimpleCAD API as a portable Agent Skill and provide a clear add-new-case workflow that keeps source, exports, docs, and skill bundle in sync. Use when you need a self-maintained CAD SDK skill.
license: MIT
compatibility: Requires bash and Python 3.10+. Optional: skills-ref CLI for full spec validation.
metadata:
  project: simplecadapi
  version: 2.0.0
  snapshot: assets/project_snapshot
---

# SimpleCAD Self Evolve Skill

## When to use this skill
- You need a portable snapshot of SimpleCAD SDK code and docs.
- You need one repeatable command flow to add a new SDK case/function.
- You want source updates, exports, and docs to stay synchronized.

## SDK core philosophy
- **Open/Closed design**: keep core wrapper types stable and extend capability by adding new top-level functions.
- **Function-first API**: use explicit snake_case operation functions instead of hidden class mutation.
- **Return-type explicit naming**: function names encode return type, for example `make_circle_rwire` or `extrude_rsolid`.
- **Evolve by composition**: new advanced cases are added in `evolve.py` by combining existing primitives.
- **Docs as contract**: every public function should keep signature, docstring, and generated docs aligned.

## Directory map
The skill root layout:

- `SKILL.md`: this instruction file.
- `scripts/`: runnable automation scripts for add/update/validate workflows.
- `references/`: readable navigation and workflow documents.
- `assets/project_snapshot/`: portable SDK snapshot used by scripts.

Snapshot scope in `assets/project_snapshot/`:

- `src/simplecadapi/core.py`: core geometric wrapper types and coordinate system utilities.
- `src/simplecadapi/operations.py`: stable public operation functions.
- `src/simplecadapi/evolve.py`: advanced or newly extracted case functions.
- `src/simplecadapi/__init__.py`: aggregated exports and aliases.
- `src/simplecadapi/auto_tools/`: automation tools (`evolution.py`, `make_export.py`, `auto_docs_gen.py`, `skill_pack.py`).
- `docs/api/`: generated per-function API docs.
- `docs/core/`: core type documentation.
- `README.md`: SDK design and workflow explanation.
- `pyproject.toml`: package metadata and script entry points.
- `LICENSE`: project license.

## How to import SDK functions
Import targets by module role:

- Public SDK APIs: `simplecadapi` (recommended) or `simplecadapi.operations`.
- Evolved case functions: `simplecadapi.evolve`.
- Core wrapper types: `simplecadapi.core`.

If you already installed the package, import directly:

```python
import simplecadapi as scad
from simplecadapi import make_box_rsolid, export_stl
from simplecadapi.evolve import make_n_hole_flange_rsolid
```

If you are running against this skill snapshot without installation, set `PYTHONPATH` first:

```bash
export PYTHONPATH="${PWD}/assets/project_snapshot/src:${PYTHONPATH:-}"
python3 your_script.py
```

Example usage after import:

```python
import simplecadapi as scad

box = scad.make_box_rsolid(width=10, height=6, depth=4)
scad.export_stl(box, "box.stl")
```

## Single-skill simplified mode
If your project uses only this one skill, you can skip registry and multi-skill lock management.
Use `scripts/with_skill.sh` as the single activation entry.

```bash
scripts/with_skill.sh -- python3 your_script.py
scripts/jupyter_with_skill.sh lab
# or export into current shell
eval "$(scripts/with_skill.sh --print-env)"
```

- `with_skill.sh` sets `SIMPLECAD_SKILL_ROOT` and `SIMPLECAD_SKILL_SRC`.
- `with_skill.sh` prepends this skill's `assets/project_snapshot/src` to `PYTHONPATH`.
- `jupyter_with_skill.sh` launches Jupyter with this skill path pre-activated.
- This keeps imports deterministic while remaining lightweight.

## Persistent REPL and notebook kernel mode
If an LLM writes code directly in a persistent REPL (IPython/Jupyter kernel), use one-time bootstrap in the session.

```python
# in a notebook cell or persistent Python REPL
%run ./skills/simplecad-self-evolve/scripts/repl_bootstrap.py
import simplecadapi as scad
```

Notes:
- `repl_bootstrap.py` injects this skill's source path into current process `sys.path`.
- It also sets `SIMPLECAD_SKILL_ROOT` and `SIMPLECAD_SKILL_SRC` in `os.environ`.
- Use `--check` when running from shell to verify imports: `python scripts/repl_bootstrap.py --check`.

## Scripts and exact usage
`scripts/with_skill.sh`

```bash
scripts/with_skill.sh -- python3 your_script.py
scripts/with_skill.sh --print-env
scripts/with_skill.sh --check
```

- Purpose: activate this single skill import path in a deterministic way.
- `-- <command>` runs a command with skill-aware `PYTHONPATH`.
- `--print-env` prints `export` commands that can be `eval` in current shell.
- `--check` verifies runtime dependencies and `import simplecadapi` availability.

`scripts/jupyter_with_skill.sh`

```bash
scripts/jupyter_with_skill.sh lab
scripts/jupyter_with_skill.sh notebook
scripts/jupyter_with_skill.sh lab -- --no-browser
```

- Purpose: start Jupyter Lab/Notebook with skill import path already injected.
- Uses `with_skill.sh` internally so notebook kernels inherit deterministic `PYTHONPATH`.

`scripts/repl_bootstrap.py`

```bash
python scripts/repl_bootstrap.py
python scripts/repl_bootstrap.py --check
```

- Purpose: activate skill import path in an already-running Python process.
- Typical use: first cell in a notebook kernel managed by LLM.

`scripts/add_new_case.sh`

```bash
scripts/add_new_case.sh <path-to-python-script>
# optional: NO_REPACK=1 scripts/add_new_case.sh <path>
```

- Purpose: end-to-end add-new-case pipeline.
- Input: a Python file that contains a function implementation to extract.
- Actions: validate skill -> extract function into `evolve.py` -> rebuild `__init__.py` exports -> regenerate `docs/api` -> repack skill.
- Output: updated snapshot files (and repacked skill unless `NO_REPACK=1`).

`scripts/rebuild_exports.sh`

```bash
scripts/rebuild_exports.sh [extra make_export args]
```

- Purpose: regenerate `assets/project_snapshot/src/simplecadapi/__init__.py` from current APIs.

`scripts/refresh_docs.sh`

```bash
scripts/refresh_docs.sh
```

- Purpose: regenerate `assets/project_snapshot/docs/api/*.md` and the API index from function docstrings.

`scripts/repack_skill.sh`

```bash
scripts/repack_skill.sh [extra skill_pack args]
```

- Purpose: rebuild this skill folder from `assets/project_snapshot` using `skill_pack.py`.

`scripts/validate_skill.sh`

```bash
scripts/validate_skill.sh
```

- Purpose: verify required files and run `skills-ref validate` when available.

## Recommended add-new-case procedure
1. Prepare a Python script with one well-documented new case function.
2. Run `scripts/add_new_case.sh <script.py>`.
3. Review changes under `assets/project_snapshot/src/simplecadapi/` and `assets/project_snapshot/docs/api/`.
4. Run `scripts/validate_skill.sh` and then publish/share this skill.

## Additional references
- `references/PROJECT_OVERVIEW.md`
- `references/API_INDEX.md`
- `references/CORE_INDEX.md`
- `references/EVOLVE_WORKFLOW.md`
