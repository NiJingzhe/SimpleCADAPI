# Skill-Local Evolve Workflow

This thin skill does not modify `site-packages/simplecadapi` directly.
New evolve cases are stored in skill-local module:

- `cases/simplecad_self_evolve_cases/evolve.py`

## 1) Add a new case from a Python file

```bash
scripts/add_new_case.sh path/to/new_case.py
```

By default, the first top-level function in `new_case.py` is extracted.

## 2) Activate skill paths

```bash
eval "$(scripts/with_skill.sh --print-env)"
```

## 3) Import and use in Python

```python
import simplecadapi as scad
from simplecad_self_evolve_cases.evolve import your_function_name
```

## 4) Persistent kernel usage

```python
%run ./scripts/repl_bootstrap.py
from simplecad_self_evolve_cases.evolve import your_function_name
```
