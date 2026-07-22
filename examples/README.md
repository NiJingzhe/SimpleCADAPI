# SimpleCADAPI Examples

Run examples from the repository root with `uv run python <path>`.
Generated artifacts are written to `examples/out/`, which is ignored by git.

Replayable examples use one top-level `@scad.model` entry. That entry owns the
single `GraphSession` and returns a `ModelResult`; reusable graph-producing
builders use `@scad.requires_session`. Final outputs are selected with
`scad.capture_result(...)`; `@scad.model(export_dir=...)` can automatically
write one self-contained Scene ZIP after execution. It embeds the replayable
model, mapped Python source files, render GLBs, and entity sidecars. Examples
that call explicit export or translator APIs may also write STEP, JSON, or
FreeCAD files.

## Examples

- `04_dimension_tolerance_chain.py` — expression-driven dimension tolerance analysis and validation.
- `08_constrained_sketch.py` — fully constrained sketch profiles, feature promotion, replay, and FreeCAD export.
- `09_naca0016_blade_freecad.py` — NACA 0016 B-spline blade model JSON, STEP, and FreeCAD translation.
- `10_part_assembly.py` — hydraulic rod assembly with sleeve/piston parts, prismatic motion, and automatic self-contained Scene ZIP export.
- `16_compact_two_stage_planetary_reducer/` — modular 58.8 mm diameter, 30 mm tall, 20:1 two-stage herringbone planetary reducer with graph/model JSON replay, STEP export, solved constraints, and a static collision probe.
- `20_integrated_bldc_joint_actuator/` — compact 50 mm OD joint actuator with a 12-slot/14-pole inner-rotor BLDC motor, two-stage planetary reducer, split housing, output bearings, and controller electronics.
