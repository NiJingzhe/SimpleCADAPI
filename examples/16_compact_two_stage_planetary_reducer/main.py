"""Build, validate, and export the compact two-stage planetary reducer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import simplecadapi as scad

from assembly import make_two_stage_planetary_reducer_rassembly
from common import _ground_compound
from dimensions import HOUSING_HEIGHT, HOUSING_OUTER_RADIUS, TOTAL_REDUCTION


# Herringbone gear profile graphs are intentionally deep.
sys.setrecursionlimit(30000)

OUT_DIR = Path("examples/out/compact_two_stage_planetary_reducer")


def _build_compact_two_stage_planetary_reducer():
    """Build the reducer and return assembly, preview compound, and JSON exports."""

    with scad.GraphSession(graph_id="compact_two_stage_planetary_reducer") as session:
        assembly = make_two_stage_planetary_reducer_rassembly()
        preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
        _ground_compound(label="reducer_preview", compound=preview)
        session_json = scad.export_session_json(session=session)
        model_json = scad.export_model_json(session=session)
    return assembly, preview, model_json, session_json


def main() -> None:
    """Generate replayable JSON and STEP output for the reducer example."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "compact_two_stage_planetary_reducer.model.json"
    session_path = OUT_DIR / "compact_two_stage_planetary_reducer.session.json"
    step_path = OUT_DIR / "compact_two_stage_planetary_reducer.step"
    fcstd_path = OUT_DIR / "compact_two_stage_planetary_reducer.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    assembly, preview, model_json, session_json = _build_compact_two_stage_planetary_reducer()
    model_path.write_text(model_json, encoding="utf-8")
    session_path.write_text(session_json, encoding="utf-8")
    scad.export_step(shapes=preview, filename=str(step_path))

    imported = scad.import_model_json(json_str=model_json)
    replayed = scad.replay_model_json(json_str=model_json)
    payload = json.loads(model_json)

    fcstd_status = "not attempted"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            json_str=model_json,
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
