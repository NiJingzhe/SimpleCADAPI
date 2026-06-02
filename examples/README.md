# SimpleCADAPI Examples

Run examples from the repository root with `uv run python <path>`.
Generated STEP/STL/JSON files are written to `examples/out/`, which is ignored by git.

## Examples

- `01_basic_modeling.py` — functional shape modeling, booleans, and STEP/STL export.
- `02_graph_replay.py` — `GraphSession`, canonical model JSON export, and replay.
- `03_expressions.py` — expression parameters captured in a replayable model graph.
- `05_loft_sweep_revolve.py` — profile operations: revolve, loft, and sweep.
- `06_parametric_gear_model.py` — lightweight involute spur gear model JSON example for replay/export tests.
- `07_serialization_operation_tree.py` — compact serialization demo showing how source calls map to canonical operation-tree nodes, including expressions, primitive lowering, features, booleans, transforms, patterns, and detail operations.
