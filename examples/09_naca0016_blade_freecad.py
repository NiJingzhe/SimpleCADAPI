"""NACA 0016 propeller blade with exact BSpline FreeCAD translation.

Run from the repository root with:
    uv run python examples/09_naca0016_blade_freecad.py

Generated files:
    examples/out/naca0016_blade/naca0016_blade.model.json
    examples/out/naca0016_blade/naca0016_blade.step
    examples/out/naca0016_blade/naca0016_blade.fcstd

The NACA section generator starts from sampled airfoil points. The evolve helper
fits those samples into exact cubic B-spline control data before calling
`make_spline_rwire(...)`, so the exported model JSON and FreeCAD document contain
exact B-spline payloads rather than sampled-point spline approximations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import simplecadapi as scad


DEFAULT_OUTPUT_DIR = Path("examples/out/naca0016_blade")
DEFAULT_FREECAD_CMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")


def build_blade(output_dir: Path, *, freecad_cmd: Path | None = DEFAULT_FREECAD_CMD) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_json_path = output_dir / "naca0016_blade.model.json"
    step_path = output_dir / "naca0016_blade.step"
    fcstd_path = output_dir / "naca0016_blade.fcstd"

    with scad.GraphSession() as session:
        blade = scad.make_naca_propeller_blade_rsolid(
            blade_length=4.0,
            root_chord=1.25,
            tip_chord=0.35,
            total_twist_angle=36.0,
            num_sections=6,
        )
        blade = scad.apply_tag(blade, "role.naca0016.blade")

    model_json = scad.export_model_json(session)
    payload = json.loads(model_json)
    model_json_path.write_text(model_json, encoding="utf-8")
    scad.export_step(blade, str(step_path))

    bspline_nodes = [
        node for node in payload["graph"]["nodes"] if node.get("op") == "make_spline_redge"
    ]
    loft_nodes = [node for node in payload["graph"]["nodes"] if node.get("op") == "make_loft_rsolid"]
    control_counts = [len(node["params"].get("control_points", [])) for node in bspline_nodes]
    knot_counts = [len(node["params"].get("knots", [])) for node in bspline_nodes]

    print("graph_nodes", len(payload["graph"]["nodes"]))
    print("leaf_ids", payload["leaf_ids"])
    print("bspline_section_nodes", len(bspline_nodes))
    print("loft_nodes", len(loft_nodes))
    print("bspline_control_counts", control_counts[:6])
    print("bspline_knot_counts", knot_counts[:6])
    print("volume", round(blade.get_volume(), 6))
    print("wrote", model_json_path)
    print("wrote", step_path)

    if freecad_cmd is not None and freecad_cmd.exists():
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            model_json,
            str(fcstd_path),
            document_name="NACA0016Blade",
            freecad_cmd=str(freecad_cmd),
        )
        print("wrote", fcstd_path)
    else:
        print("skipped_fcstd", "FreeCADCmd not found")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--freecad-cmd",
        type=Path,
        default=DEFAULT_FREECAD_CMD,
        help="FreeCADCmd path used to write .fcstd; skipped if the path does not exist.",
    )
    args = parser.parse_args()
    build_blade(args.output_dir, freecad_cmd=args.freecad_cmd)


if __name__ == "__main__":
    main()
