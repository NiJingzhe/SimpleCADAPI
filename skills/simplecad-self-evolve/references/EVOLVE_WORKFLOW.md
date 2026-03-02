# Evolve Workflow

This reference describes the expected self-evolution sequence.

1. Extract function implementation into `evolve.py`.
2. Rebuild exports in `__init__.py`.
3. Regenerate API docs from source docstrings.
4. Repack the skill folder from the updated snapshot.

## Commands

```bash
scripts/add_new_case.sh path/to/new_function.py
```

Or run each step separately:

```bash
scripts/rebuild_exports.sh
scripts/refresh_docs.sh
scripts/repack_skill.sh
scripts/validate_skill.sh
```

## Environment

- `PYTHON_BIN` can override the Python interpreter used by scripts.
- `NO_REPACK=1` skips the repack step in `add_new_case.sh`.
