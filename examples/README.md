# SimpleCADAPI Examples

Run examples from the repository root with `uv run python <path>`.
Generated artifacts are written to `examples/out/`, which is ignored by git.

Every formal single-script example emits three synchronized artifacts under `examples/out/`:
the canonical self-contained `.scadpkg`, an AP242 `.step`, and an editable
FreeCAD `.FCStd`. Single-solid products use `@scad.part`; assemblies use
`@scad.assemble` with explicit immutable definitions for every physical part or
nested assembly. Both downstream CAD files are translated from the same product
package, so they retain the same definition closure, evaluated geometry,
assembly instances, names, solved placements, materials, and available semantic
metadata.

`tools/run_examples.py` requires every formal single-script example to rewrite
and validate all three CAD artifacts. The split AP242/Gmsh workflow below is
run directly, one script per stage.

## Examples

- `04_dimension_tolerance_chain.py` — `out/dimension_tolerance_chain/dimension_tolerance_chain.scadpkg`
- `08_constrained_sketch.py` — `out/constrained_sketch/constrained_sketch.scadpkg`
- `10_part_assembly.py` — `out/hydraulic_rod_assembly/hydraulic_rod_assembly.scadpkg`
- `11_external_reference_gear_train.py` — `out/external_reference_gear_train/nested_external_reference_gear_trains.scadpkg`
- `12_ap242_gmsh_volume_mesh/model.py` — `out/ap242_gmsh_volume_mesh/ap242_gmsh_bracket.scadpkg`
- `7ep_caplcd_enclosure.py` — `out/7ep_caplcd_enclosure/caplcd_enclosure_7ep.scadpkg`
- `16_compact_two_stage_planetary_reducer/` — `out/compact_two_stage_planetary_reducer/compact_two_stage_planetary_reducer.scadpkg`
- `20_integrated_bldc_joint_actuator/` — `out/integrated_bldc_joint_actuator/integrated_bldc_joint_actuator.scadpkg`

## Product Package Exporter And Translator Matrix

Build the canonical package once:

```bash
uv run python examples/12_ap242_gmsh_volume_mesh/model.py
```

Then run any downstream exporter or translator directly:

```bash
uv run python examples/12_ap242_gmsh_volume_mesh/export_fcstd.py
uv run python examples/12_ap242_gmsh_volume_mesh/export_step.py
uv run --extra gmsh python examples/12_ap242_gmsh_volume_mesh/export_stl.py
uv run --extra gmsh python examples/12_ap242_gmsh_volume_mesh/export_obj.py
uv run python examples/12_ap242_gmsh_volume_mesh/translate_freecad_script.py
uv run python examples/12_ap242_gmsh_volume_mesh/translate_fusion360_script.py
uv run python examples/12_ap242_gmsh_volume_mesh/translate_solidworks_script.py
```

The outputs are editable FreeCAD `.FCStd`, AP242 `.step`, triangulated `.stl`,
quad-preserving `.obj`, and standalone Python scripts for FreeCAD, Fusion 360,
and SolidWorks. Every command above reads the same `.scadpkg` directly.

FEM meshing consumes the STEP produced by `export_step.py`:

```bash
uv run --extra gmsh python examples/12_ap242_gmsh_volume_mesh/export_fem_mesh.py
```

It imports AP242 through Gmsh's OpenCASCADE kernel and writes a 3D `.msh`.
