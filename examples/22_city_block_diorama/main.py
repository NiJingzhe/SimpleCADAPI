"""Build, replay, export, and render Example 22."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import simplecadapi as scad

from assembly import make_city_block_assembly
from common import ground_assembly, make_colored_preview_solids
from dimensions import validate_dimensions
from materials import make_city_materials


sys.setrecursionlimit(50000)

OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "city_block_diorama"


def build_city_block():
    """Capture one replayable graph session for the complete scene."""

    validate_dimensions()
    materials = make_city_materials()
    print(f"materials: count={len(materials)} keys={','.join(sorted(materials))}")
    with scad.GraphSession(graph_id="city_block_diorama") as session:
        assembly = make_city_block_assembly(materials=materials)
        preview = ground_assembly(
            label="city_preview",
            assembly=assembly,
            record_result=True,
        )
        session_json = scad.export_session_json(session=session, indent=2)
        model_json = scad.export_model_json(session=session, indent=2)
    return assembly, preview, model_json, session_json


def main() -> None:
    """Write interchange files and a color-coded architectural preview."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "city_block_diorama.model.json"
    session_path = OUT_DIR / "city_block_diorama.session.json"
    step_path = OUT_DIR / "city_block_diorama.step"
    stl_path = OUT_DIR / "city_block_diorama.stl"
    fcstd_path = OUT_DIR / "city_block_diorama.FCStd"
    screenshot_path = OUT_DIR / "city_block_diorama.png"

    assembly, preview, model_json, session_json = build_city_block()
    model_path.write_text(model_json, encoding="utf-8")
    session_path.write_text(session_json, encoding="utf-8")
    scad.export_step(shapes=preview, filename=str(step_path))
    scad.export_stl(shapes=preview, filename=str(stl_path))
    if fcstd_path.exists():
        fcstd_path.unlink()
    freecad_cmd = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
    fcstd_status = "not attempted"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            json_str=model_json,
            output_path=str(fcstd_path.resolve()),
            document_name="CityBlockDiorama",
            freecad_cmd=str(freecad_cmd) if freecad_cmd.exists() else None,
        )
        fcstd_status = f"{fcstd_path} ({fcstd_path.stat().st_size} bytes)"
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__}: {exc})"

    preview_solids = make_colored_preview_solids(assembly=assembly, preview=preview)
    scad.render_screenshot_rpath(
        shapes=preview_solids,
        output_path=str(screenshot_path),
        highlight_tags=(
            "role.preview.warm",
            "role.preview.purple",
            "role.preview.yellow",
            "role.preview.blue",
            "role.preview.brick",
            "role.preview.red",
            "role.preview.green",
            "role.preview.earth",
        ),
        tag_labels={
            "role.preview.warm": "wood / warm interior",
            "role.preview.purple": "purple signage",
            "role.preview.yellow": "lighting / markings",
            "role.preview.blue": "glass / water",
            "role.preview.brick": "brickwork",
            "role.preview.red": "red accents",
            "role.preview.green": "landscape",
            "role.preview.earth": "cutaway earth",
        },
        image_size=(1600, 1000),
        view=(28.0, -45.0),
        show_axes=False,
        show_legend=True,
        zoom=4.5,
    )

    imported = scad.import_model_json(json_str=model_json)
    replayed = scad.replay_model_json(json_str=model_json, strict=True)
    payload = json.loads(model_json)
    print(f"assembly={assembly.assembly_id}")
    print(f"top_level_components={len(assembly.component_ids())}")
    print(f"preview_solids={len(preview_solids)}")
    print(f"preview_faces={sum(len(solid.get_faces()) for solid in preview_solids)}")
    print(f"preview_volume={preview.get_volume():.2f}")
    print(f"imported_keys={','.join(sorted(imported.keys()))}")
    print(f"replay_outputs={len(replayed)}")
    print(f"graph_nodes={len(payload['graph']['nodes'])}")
    print(f"model={model_path}")
    print(f"session={session_path}")
    print(f"step={step_path}")
    print(f"stl={stl_path}")
    print(f"fcstd={fcstd_status}")
    print(f"screenshot={screenshot_path}")


if __name__ == "__main__":
    main()
