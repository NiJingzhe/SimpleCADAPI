# SimpleCADAPI

SimpleCADAPI is an OCP-native imperative CAD modeling Python package. It keeps the 1.x-style functional API while adding v2 graph recording, expression parameters, and replayable model JSON workflows.

## README Scope

This README only covers package-level capabilities, installation methods, publishing/packaging workflows, and Skills usage instructions.
Experimental scripts and temporary modeling examples are not included as formal documentation.

## Package Installation (Python Package Managers)

Current package name: `simplecadapi` (see `pyproject.toml` for the version).

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

Build a local wheel/sdist first if you want to install from local artifacts:

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

## How to Package SDK Skills

This project provides the `skill-pack` CLI for generating lightweight SDK reference skills: **No built-in SDK source code**, focused on API and architecture descriptions.

### 1) Packaging Command

Execute in the repository root directory:

```bash
uv run skill-pack --refresh-docs --archive --skill-name simplecadapi
```

Common parameters:

- `--output-root <dir>`: Output directory (default `./skills`)
- `--package-name <pkg>`: Runtime installation package name (default reads from `project.name`)
- `--package-version <ver>`: Runtime installation version (default reads from `project.version`)
- `--no-clean`: Do not clean existing output directory
- `--archive`: Additionally generate `<skill-name>.tar.gz`

### 2) Packaging Result Structure

After packaging, you will get a directory similar to:

- `skills/simplecadapi/SKILL.md`
- `skills/simplecadapi/references/`
- `skills/simplecadapi/references/docs/api/`
- `skills/simplecadapi/references/docs/core/`

### 3) Read the SDK skill

```bash
cd skills/simplecadapi
```

Key entry points:

- `skills/simplecadapi/SKILL.md`
- `skills/simplecadapi/references/SDK_OVERVIEW.md`
- `skills/simplecadapi/references/SDK_SURFACES.md`
- `skills/simplecadapi/references/V2_MODELING_WORKFLOWS.md`
- `skills/simplecadapi/references/SDK_PACKAGE_SUMMARY.md`
- `skills/simplecadapi/references/docs/api/README.md`
- `skills/simplecadapi/references/docs/core/README.md`

### 4) Preferred v2 replay workflow

```python
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession() as session:
    ...

model_json = export_model_json(session)
rebuilt = replay_model_json(model_json)
print(len(rebuilt))
```

## Auto Tools

The project includes 4 main CLIs:

- `auto-docs-gen`: Generate `docs/api/` documentation from the public API source surface
- `make-export`: Update imports/exports in `src/simplecadapi/__init__.py`
- `evolve`: Extract functions from scripts for repository-managed evolve modules
- `skill-pack`: Package thin SDK skill (documentation only)

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
uv run python examples/01_basic_modeling.py
uv run python examples/02_graph_replay.py
uv run python examples/03_expressions.py
uv run python examples/04_assembly_constraints.py
uv run python examples/05_loft_sweep_revolve.py
uv run python examples/06_parametric_gear_model.py
uv run python examples/06_parametric_gear_model.py
```

## Core Design Constraints (Brief)

- API functions uniformly use `snake_case` and reflect return types in function names (e.g., `*_rsolid`, `*_rwire`).
- Core types are OCP-native wrappers and are kept as stable as possible; functionality is extended by adding new functions (Open-Closed Principle).
- Support `SimpleWorkplane` context for local coordinate modeling.
- Export interfaces support single entities, multiple entities, and nested list inputs.

## Documentation Entry Points

- API documentation: `docs/api/`
- Core documentation: `docs/core/`

## License

MIT, see `LICENSE`.
