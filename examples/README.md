# SimpleCADAPI Examples

Run examples from the repository root with `uv run python <path>`.
Generated STEP/STL/JSON files are written to `examples/out/`, which is ignored by git.

## Examples

- `01_basic_modeling.py` — 1.x-style functional shape modeling, booleans, STEP/STL export.
- `02_graph_replay.py` — `GraphSession`, canonical model JSON export, and replay.
- `03_expressions.py` — expression parameters captured in the v2 model graph.
- `04_assembly_constraints.py` — rigid assembly constraints with bbox anchors.
- `05_loft_sweep_revolve.py` — profile operations: revolve, loft, and sweep.
- `06_parametric_gear_model.py` — lightweight involute spur gear model JSON example for replay/export tests.
