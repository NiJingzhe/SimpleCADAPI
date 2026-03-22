# Runtime Install Reference

## Base install

```bash
PYTHON_BIN=.venv/bin/python scripts/install.sh
```

This installs `simplecadapi==2.0.6` to the active Python environment.
If `PYTHON_BIN` is not set, wrappers default to `python3` (fallback `python`).
Installation is intentionally blocked for non-venv/system interpreters.

## Install with Jupyter support

```bash
PYTHON_BIN=.venv/bin/python scripts/install.sh --with-jupyter
```

## Upgrade package

```bash
PYTHON_BIN=.venv/bin/python scripts/install.sh -- --upgrade
```

Everything after `--` is forwarded to `uv pip install` (or `python -m pip install` fallback).

## Validate runtime

```bash
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
.venv/bin/python scripts/repl_bootstrap.py --check
```

## Activate skill paths in current shell

```bash
eval "$(scripts/with_skill.sh --print-env)"
```

## Add and import skill-local evolved case

```bash
scripts/add_new_case.sh path/to/new_case.py
```

```python
from simplecad_self_evolve_cases.evolve import your_function_name
```
