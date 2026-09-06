"""Role 5 export: durable package + STEP + STL from the validated 8-hole model.

    uv run python examples/flange_plate/export.py                     # capture + STEP
    uv run --extra gmsh python examples/flange_plate/export.py        # same + STL (gmsh backend)
    uv run python examples/flange_plate/export.py --validate          # fresh-process re-open gate
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import simplecadapi as scad  # noqa: E402
import flange_plate as fp  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "out" / "flange_plate"
PKG = OUT / "flange_plate.scadpkg"


def capture_and_export() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = fp.build_flange_plate()          # PartBuildResult (cached single-solid part)
    cap = scad.capture(result, PKG)            # canonical durable export (positional contract)
    print(f"capture: {PKG.name} exists={PKG.exists()} "
          f"result_type={type(cap).__name__}")

    step_report = scad.exporter.step.export_product_package_to_step(
        data=PKG, output_path=OUT / "flange_plate.step")
    print(f"step: output={getattr(step_report, 'output_path', OUT / 'flange_plate.step')} "
          f"schema={getattr(step_report, 'schema', '?')} "
          f"definitions={getattr(step_report, 'definition_ids', '?')} "
          f"occurrences={getattr(step_report, 'occurrence_count', '?')}")

    try:
        stl_report = scad.exporter.stl.export_product_package_to_stl(
            data=PKG, output_path=OUT / "flange_plate.stl",
            linear_deflection=0.1, angular_deflection_degrees=20.0)
        print(f"stl: vertices={getattr(stl_report, 'vertex_count', '?')} "
              f"triangles={getattr(stl_report, 'triangle_count', '?')} "
              f"backend={getattr(stl_report, 'backend', '?')}")
    except Exception as exc:  # gmsh extra missing -> report, never silent
        print(f"stl: SKIPPED ({type(exc).__name__}: {str(exc)[:100]}) "
              f"— rerun with: uv run --extra gmsh python {Path(__file__).name}")


def validate_reopen() -> None:
    package = scad.read_product_package(PKG)
    scad.validate_product_package(package)
    definition = scad.load_product_package(PKG)
    print(f"reopen: validate OK, root_definition={package.root_definition} "
          f"root_kind={package.root_kind} definition_id={definition.definition_id} "
          f"definition_kind={definition.definition_kind} revision={definition.revision} "
          f"solid_cache={'present' if definition.solid_cache_ref else 'absent'} "
          f"(single-solid part product)")


if __name__ == "__main__":
    if "--validate" in sys.argv:
        validate_reopen()
    else:
        capture_and_export()
