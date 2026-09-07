"""Build, validate, and export the compact two-stage planetary reducer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import simplecadapi as scad

if __package__:
    import importlib

    # The example also supports direct-file execution, so its child modules use
    # sibling imports. Register those siblings before importing the package entry.
    for _module_name in (
        "dimensions",
        "common",
        "materials",
        "bearings",
        "carriers",
        "flanges",
        "gears",
        "housing",
        "shafts",
        "assembly",
    ):
        sys.modules.setdefault(
            _module_name,
            importlib.import_module(f"{__package__}.{_module_name}"),
        )
    from .assembly import (
        build_two_stage_planetary_reducer_product,
        make_two_stage_planetary_reducer_rassembly,
    )
    from .common import _ground_compound
    from .dimensions import HOUSING_HEIGHT, HOUSING_OUTER_RADIUS, TOTAL_REDUCTION
else:
    from assembly import (
        build_two_stage_planetary_reducer_product,
        make_two_stage_planetary_reducer_rassembly,
    )
    from common import _ground_compound
    from dimensions import HOUSING_HEIGHT, HOUSING_OUTER_RADIUS, TOTAL_REDUCTION


# Herringbone gear profile graphs are intentionally deep.
sys.setrecursionlimit(30000)

OUT_DIR = Path(__file__).resolve().parent / "out"


def _build_compact_two_stage_planetary_reducer_body():
    """Build the reducer and return its assembly and preview compound."""

    assembly = make_two_stage_planetary_reducer_rassembly()
    preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    preview = scad.apply_tag(shape=preview, tag="scene.reducer.preview")
    _ground_compound(label="reducer_preview", compound=preview)
    return assembly, preview


def _build_compact_two_stage_planetary_reducer():
    session = scad.GraphSession(graph_id="compact_two_stage_planetary_reducer")
    with session:
        assembly, preview = _build_compact_two_stage_planetary_reducer_body()
        session.capture_result(value=(assembly, preview))
        model_json = scad.export_model_json(session)
        session_json = scad.export_session_json(session)
    return assembly, preview, model_json, session_json


def main() -> None:
    """Generate synchronized package, AP242 STEP, FCStd, and replay JSON."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "compact_two_stage_planetary_reducer.model.json"
    session_path = OUT_DIR / "compact_two_stage_planetary_reducer.session.json"
    step_path = OUT_DIR / "compact_two_stage_planetary_reducer.step"
    fcstd_path = OUT_DIR / "compact_two_stage_planetary_reducer.FCStd"

    product_result = build_two_stage_planetary_reducer_product()
    assembly = product_result.assembly
    preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    preview = scad.apply_tag(shape=preview, tag="scene.reducer.preview")
    _ground_compound(label="reducer_preview", compound=preview)
    session = product_result.feature_graph.restore_session()
    model_json = scad.export_model_json(session)
    session_json = scad.export_session_json(session)
    model_path.write_text(model_json, encoding="utf-8")
    session_path.write_text(session_json, encoding="utf-8")
    package_path = OUT_DIR / "compact_two_stage_planetary_reducer.scadpkg"
    scad.capture(product_result, package_path)
    step_report = scad.exporter.export_product_package_to_step(package_path, step_path)
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        package_path,
        str(fcstd_path.resolve()),
        document_name="CompactTwoStagePlanetaryReducer",
    )

    imported = scad.import_model_json(json_str=model_json)
    replayed = [product_result.replay()]
    payload = json.loads(model_json)

    fcstd_status = f"{fcstd_path} ({fcstd_path.stat().st_size} bytes)"

    solids = scad.ql.solids().resolve(preview)
    print(f"envelope_diameter={HOUSING_OUTER_RADIUS * 2.0:.1f}")
    print(f"envelope_height={HOUSING_HEIGHT:.1f}")
    print(f"total_reduction={TOTAL_REDUCTION:.1f}")
    print(f"assembly={assembly.assembly_id}")
    print("components=" + ",".join(assembly.component_ids()))
    print("constraints=" + ",".join(assembly.constraint_ids()))
    print(f"preview_solids={len(solids)}")
    print(f"preview_volume={preview.get_volume():.3f}")
    print(f"imported_keys={','.join(sorted(imported.keys()))}")
    print(f"replay_outputs={len(replayed)}")
    print("replay_types=" + ",".join(type(item).__name__ for item in replayed))
    print(f"graph_nodes={len(payload['graph']['nodes'])}")
    print(f"model={model_path}")
    print(f"session={session_path}")
    print(f"step={step_report.output_path}")
    print(f"fcstd={fcstd_status}")
    print(f"product_package={package_path}")


if __name__ == "__main__":
    main()
