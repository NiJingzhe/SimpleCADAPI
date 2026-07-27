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
    from .assembly import make_two_stage_planetary_reducer_rassembly
    from .common import _ground_compound
    from .dimensions import HOUSING_HEIGHT, HOUSING_OUTER_RADIUS, TOTAL_REDUCTION
else:
    from assembly import make_two_stage_planetary_reducer_rassembly
    from common import _ground_compound
    from dimensions import HOUSING_HEIGHT, HOUSING_OUTER_RADIUS, TOTAL_REDUCTION


# Herringbone gear profile graphs are intentionally deep.
sys.setrecursionlimit(30000)

OUT_DIR = Path("examples/out/compact_two_stage_planetary_reducer")


@scad.model(graph_id="compact_two_stage_planetary_reducer")
def _build_compact_two_stage_planetary_reducer():
    """Build the reducer and return its assembly and preview compound."""

    assembly = make_two_stage_planetary_reducer_rassembly()
    preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    preview = scad.apply_tag(shape=preview, tag="scene.reducer.preview")
    _ground_compound(label="reducer_preview", compound=preview)
    scad.capture_result(value=(assembly, preview))
    return assembly, preview


def main() -> None:
    """Generate replayable JSON and STEP output for the reducer example."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "compact_two_stage_planetary_reducer.model.json"
    session_path = OUT_DIR / "compact_two_stage_planetary_reducer.session.json"
    step_path = OUT_DIR / "compact_two_stage_planetary_reducer.step"
    fcstd_path = OUT_DIR / "compact_two_stage_planetary_reducer.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    result = _build_compact_two_stage_planetary_reducer()
    assembly, preview = result.value
    model_path.write_text(result.model_json, encoding="utf-8")
    session_path.write_text(result.session_json, encoding="utf-8")
    scad.export_step(shapes=preview, filename=str(step_path))

    imported = scad.import_model_json(json_str=result.model_json)
    replayed = scad.replay_model_json(json_str=result.model_json)
    payload = json.loads(result.model_json)

    fcstd_status = "not attempted"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            json_str=result.model_json,
            output_path=str(fcstd_path.resolve()),
            document_name="CompactTwoStagePlanetaryReducer",
            freecad_cmd=None,
        )
        fcstd_status = f"{fcstd_path} ({fcstd_path.stat().st_size} bytes)"
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__}: {exc})"

    solids = preview.get_solids()
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
    print(f"step={step_path}")
    print(f"fcstd={fcstd_status}")


if __name__ == "__main__":
    main()
