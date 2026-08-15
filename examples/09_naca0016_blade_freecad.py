"""NACA 0016 propeller blade with exact BSpline FreeCAD translation.

Run from the repository root with:
    uv run python examples/09_naca0016_blade_freecad.py

Generated files:
    examples/out/naca0016_blade/naca0016_blade.model.json
    examples/out/naca0016_blade/naca0016_blade.session.json
    examples/out/naca0016_blade/naca0016_blade.step
    examples/out/naca0016_blade/naca0016_blade.FCStd

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
DEFAULT_FREECAD_CMD = Path(
    "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"
)


@scad.part(
    id="naca0016_blade",
    revision="1.0.0",
    cache="off",
    project_root=Path(__file__).resolve().parents[1],
)
def build_naca0016_blade_part() -> scad.Part:
    blade = scad.make_naca_propeller_blade_rsolid(
        blade_length=4.0,
        root_chord=1.25,
        tip_chord=0.35,
        total_twist_angle=36.0,
        num_sections=6,
    )
    blade = scad.apply_tag(shape=blade, tag="role.naca0016.blade")
    blade = scad.apply_tag(shape=blade, tag="part.naca0016.blade")
    return scad.make_part_rpart(
        part_id="naca0016_blade",
        body=blade,
        name="NACA 0016 propeller blade",
    )


def build_blade() -> tuple[scad.PartBuildResult, str, str]:
    result = build_naca0016_blade_part()
    session = result.feature_graph.restore_session()
    return result, scad.export_model_json(session), scad.export_session_json(session)


def write_blade_artifacts(
    output_dir: Path,
    *,
    freecad_cmd: Path | None = DEFAULT_FREECAD_CMD,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_json_path = output_dir / "naca0016_blade.model.json"
    session_json_path = output_dir / "naca0016_blade.session.json"
    step_path = output_dir / "naca0016_blade.step"
    fcstd_path = output_dir / "naca0016_blade.FCStd"

    result, model_json, session_json = build_blade()
    payload = json.loads(model_json)
    model_json_path.write_text(model_json, encoding="utf-8")
    session_json_path.write_text(session_json, encoding="utf-8")

    bspline_nodes = [
        node
        for node in payload["graph"]["nodes"]
        if node.get("op") == "make_spline_redge"
    ]
    loft_nodes = [
        node
        for node in payload["graph"]["nodes"]
        if node.get("op") == "make_loft_rsolid"
    ]
    control_counts = [
        len(node["params"].get("control_points", [])) for node in bspline_nodes
    ]
    knot_counts = [len(node["params"].get("knots", [])) for node in bspline_nodes]

    print("graph_nodes", len(payload["graph"]["nodes"]))
    print("leaf_ids", payload["leaf_ids"])
    print("bspline_section_nodes", len(bspline_nodes))
    print("loft_nodes", len(loft_nodes))
    print("bspline_control_counts", control_counts[:6])
    print("bspline_knot_counts", knot_counts[:6])
    package_path = output_dir / "naca0016_blade.scadpkg"
    scad.capture(result, package_path)
    step_report = scad.exporter.export_product_package_to_step(package_path, step_path)
    print("wrote", model_json_path)
    print("wrote", session_json_path)

    resolved_freecad_cmd = (
        str(freecad_cmd) if freecad_cmd is not None and freecad_cmd.exists() else None
    )
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        package_path,
        str(fcstd_path),
        document_name="NACA0016Blade",
        freecad_cmd=resolved_freecad_cmd,
    )
    print("wrote", step_report.output_path)
    print("wrote", fcstd_path)
    print("product_package", package_path)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--freecad-cmd",
        type=Path,
        default=DEFAULT_FREECAD_CMD,
        help="Optional FreeCAD executable override; auto-discovered when unavailable.",
    )
    args = parser.parse_args()
    write_blade_artifacts(args.output_dir, freecad_cmd=args.freecad_cmd)


if __name__ == "__main__":
    main()
