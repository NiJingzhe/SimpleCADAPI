# SimpleCADAPI

SimpleCADAPI is an imperative CAD modeling Python package based on CADQuery. Its goal is to encapsulate common modeling operations into a clear, composable, testable functional API, and to support distributing "documentation + scripts + runtime installation" workflows via Skills.

## README Scope

This README only covers package-level capabilities, installation methods, publishing/packaging workflows, and Skills usage instructions.
Experimental scripts and temporary modeling examples are not included as formal documentation.

## Package Installation (Python Package Managers)

Current package name: `simplecadapi`, version: `2.0.7` (see `pyproject.toml`).

### Method A: Install from package repository with pip

```bash
pip install simplecadapi
```

Optional development dependencies:

```bash
pip install "simplecadapi[dev]"
```

### Method B: Install with uv

Install in the current virtual environment:

```bash
uv pip install simplecadapi
```

Add as a project dependency in `pyproject.toml`:

```bash
uv add simplecadapi
```

### Method C: Install from local build artifacts

The repository already contains example build artifacts (`dist/`):

```bash
pip install dist/simplecadapi-2.0.7-py3-none-any.whl
```

If you need to rebuild:

```bash
uv build
```

## Quick Verification of Installation

```python
import simplecadapi as scad

box = scad.make_box_rsolid(10.0, 20.0, 30.0)
scad.export_stl(box, "example_box.stl")
scad.export_step(box, "example_box.step")
```

## How to Package and Use Skills

This project provides the `skill-pack` CLI for generating lightweight skill packages (thin mode): **No built-in SDK source code**, runtime installs `simplecadapi` from the package repository.

### 1) Packaging Command

Execute in the repository root directory:

```bash
uv run skill-pack --refresh-docs --archive --skill-name simplecad-self-evolve
```

Common parameters:

- `--output-root <dir>`: Output directory (default `./skills`)
- `--package-name <pkg>`: Runtime installation package name (default reads from `project.name`)
- `--package-version <ver>`: Runtime installation version (default reads from `project.version`)
- `--no-clean`: Do not clean existing output directory
- `--archive`: Additionally generate `<skill-name>.tar.gz`

### 2) Packaging Result Structure

After packaging, you will get a directory similar to:

- `skills/simplecad-self-evolve/SKILL.md`
- `skills/simplecad-self-evolve/scripts/`
- `skills/simplecad-self-evolve/references/`
- `skills/simplecad-self-evolve/cases/simplecad_self_evolve_cases/`

### 3) Install and Verify Runtime in the Skill Directory

```bash
cd skills/simplecad-self-evolve
PYTHON_BIN=.venv/bin/python scripts/install.sh
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
```

### 4) Run Your Program with the Wrapper Script

```bash
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh -- .venv/bin/python your_script.py
```

### 5) Activate skill-local Case Module Path

```bash
eval "$(scripts/with_skill.sh --print-env)"
```

After activation, you can directly import:

```python
from simplecad_self_evolve_cases.evolve import make_involute_spur_gear_rsolid
```

### 6) Add New Functions to the Skill-local evolve Module

```bash
scripts/add_new_case.sh path/to/new_case.py
```

### 7) Jupyter and Structure Validation

```bash
scripts/jupyter_with_skill.sh lab
scripts/validate_skill.sh
```

## Auto Tools

The project includes 4 main CLIs:

- `auto-docs-gen`: Generate `docs/api/` documentation from API source code
- `make-export`: Update imports/exports in `src/simplecadapi/__init__.py`
- `evolve`: Extract functions from scripts and append to the evolve module
- `skill-pack`: Package thin skill (documentation + scripts + cases)

Examples:

```bash
uv run make-export --dry-run
uv run auto-docs-gen
uv run evolve path/to/your_case.py
uv run skill-pack --refresh-docs --archive
```

## RAGFlow Documentation Sync

`scripts/sync_ragflow_docs.py` is used to incrementally sync Markdown files under `docs/` to the specified RAGFlow dataset, chunked by H2 headings; the document's `chunk_method` is set to `manual`.

Prepare the environment:

```bash
.venv/bin/python -m pip install ragflow-sdk
```

It is recommended to use `.env` (already added to `.gitignore`):

```bash
RAGFLOW_API_KEY=your_key_here
RAGFLOW_BASE_URL=http://localhost
RAGFLOW_DATASET_NAME=SimpleCADAPI
```

Run the sync:

```bash
set -a && source .env && set +a
.venv/bin/python scripts/sync_ragflow_docs.py --create-dataset
```

Common parameters:

- `--dataset-id` / `RAGFLOW_DATASET_ID`: Directly specify the dataset ID (avoid name conflicts)
- `--delete-removed`: Delete documents that have been removed locally
- `--dry-run`: Only preview changes without executing writes
- `--progress-interval N`: Print progress every N documents

## Development and Testing

Local development installation (editable):

```bash
uv pip install -e ".[dev]"
```

Run unit tests:

```bash
uv run python -m unittest test/test_all_features.py
```

Run examples:

```bash
uv run python examples.py
```

## Core Design Constraints (Brief)

- API functions uniformly use `snake_case` and reflect return types in function names (e.g., `*_rsolid`, `*_rwire`).
- Core types are kept as stable as possible; functionality is extended by adding new functions (Open-Closed Principle).
- Support `SimpleWorkplane` context for local coordinate modeling.
- Export interfaces support single entities, multiple entities, and nested list inputs.

## Documentation Entry Points

- API documentation: `docs/api/`
- Core documentation: `docs/core/`

## License

MIT, see `LICENSE`.
