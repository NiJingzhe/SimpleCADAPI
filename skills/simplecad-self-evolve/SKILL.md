---
name: simplecad-self-evolve
description: Thin SimpleCAD skill that installs runtime SDK from PyPI into current venv site-packages, then provides deterministic REPL/Jupyter usage and references.
license: MIT
compatibility: Requires Python 3.10+, active virtual environment, and network access for package installation.
metadata:
  project: simplecadapi
  version: 2.0.5
  runtime-package: simplecadapi
  runtime-spec: simplecadapi==2.0.5
  cases-module: simplecad_self_evolve_cases
---

# SimpleCAD Runtime Skill

## Philosophy
- This is a thin skill package: docs + scripts only.
- SDK source code is not bundled in this skill.
- Runtime code is installed from PyPI into active virtual environment site-packages.
- Skill-local evolved cases are stored under `cases/simplecad_self_evolve_cases/`.

## Working From Repo Root
- Tool calls run from the repo root.
- Use one explicit skill root: `./skills/simplecad-self-evolve/` or `./workspace/skills/simplecad-self-evolve/`.
- Main doc paths:
  - `<skill_root>/SKILL.md`
  - `<skill_root>/references/docs/api/README.md`
  - `<skill_root>/references/docs/api/<api_name>.md`
  - `<skill_root>/references/docs/core/<type_name>.md`
- Skill layout also includes `<skill_root>/scripts/` and `<skill_root>/cases/`.

## MUST Requirements
1. Read `SKILL.md` and `references/docs/api/README.md` before choosing APIs.
2. Read the exact API Markdown page for every API you use.
3. Read the needed `core/` and tag/selection docs when an API needs `Edge`, `Face`, `Wire`, `Solid`, `Assembly`, or tags.
4. Follow the documented API signatures exactly.
5. Use geometry APIs for integrated parts and declarative constraints for final assemblies.
6. Use tags consistently.
7. Build and validate incrementally. Each step MUST include a small grounding `print`, and grounding MUST use QL where possible.
8. For inspection/debugging, query geometry with QL and print only the queried facts you need; do not print whole solids, assemblies, or full model objects.
9. After model construction, ask the user whether the result is satisfactory and whether any modifications are needed. Only after explicit user confirmation may you add the script to evolve cases.

## Install behavior
- Preferred: run `scripts/install.sh` once when skill is installed/activated.
- Runtime wrappers auto-install on demand if `simplecadapi` is missing.
- Package installed by default: `simplecadapi==2.0.5`
- Wrappers install only into a virtual environment interpreter (set `PYTHON_BIN` when needed).

## Interpreter selection
Use the interpreter from your active/current venv site-packages. Example:

```bash
PYTHON_BIN=.venv/bin/python scripts/install.sh
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
```

## Skill path activation
To activate this skill path in current shell:

```bash
eval "$(scripts/with_skill.sh --print-env)"
```

This exports `SIMPLECAD_SKILL_ROOT`, `SIMPLECAD_CASES_ROOT`, `SIMPLECAD_CASES_MODULE`, and updates `PYTHONPATH`.

## How to import and use
After runtime install, import normally (no custom `sys.path` needed):

```python
import simplecadapi as scad
from simplecadapi import make_box_rsolid, export_stl
```

Typical usage in a Python script:

```python
import simplecadapi as scad
from simplecadapi import make_box_rsolid, export_stl

shape = make_box_rsolid(10.0, 20.0, 30.0)
export_stl(shape, "example_box.stl")
```

Import skill-local evolved cases:

```python
from simplecad_self_evolve_cases.evolve import my_new_case
```

Run script with wrapper (auto-installs runtime when missing):

```bash
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh -- .venv/bin/python your_script.py
```

Quick import check in current venv:

```bash
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
```

## Self-evolve in skill directory
Add a new case function from a local Python script:

```bash
scripts/add_new_case.sh path/to/new_case.py
```

By default, the first top-level function in that file is appended into:
- `cases/simplecad_self_evolve_cases/evolve.py`

Then import it with:

```python
from simplecad_self_evolve_cases.evolve import your_function_name
```

## Persistent REPL / notebook kernel
In a long-running kernel session, bootstrap once in first cell:

```python
%run ./scripts/repl_bootstrap.py
import simplecadapi as scad
from simplecad_self_evolve_cases.evolve import my_new_case
```

If your kernel also needs notebook tools installed in this environment:

```python
%run ./scripts/repl_bootstrap.py --with-jupyter
```

## Jupyter launch
- `scripts/jupyter_with_skill.sh lab`
- `scripts/jupyter_with_skill.sh notebook`
- This wrapper ensures runtime package and Jupyter deps (`jupyterlab>=4.5.5, ipykernel>=6.29.5`) are available.

## Script quick reference
- `scripts/install.sh`: install runtime package to active venv site-packages.
- `scripts/with_skill.sh`: ensure runtime installed and run any command.
- `scripts/jupyter_with_skill.sh`: launch Jupyter with automatic dependency bootstrapping.
- `scripts/repl_bootstrap.py`: one-time activation helper for persistent Python sessions.
- `scripts/add_new_case.sh`: append new function into skill-local evolve module.
- `scripts/evolve_case.py`: Python extractor used by `add_new_case.sh`.
- `scripts/validate_skill.sh`: validate skill structure.

## References
- `references/PROJECT_OVERVIEW.md`
- `references/RUNTIME_INSTALL.md`
- `references/EVOLVE_WORKFLOW.md`
- `references/docs/api/`
- `references/docs/core/`
- `references/PROJECT_README.md`
