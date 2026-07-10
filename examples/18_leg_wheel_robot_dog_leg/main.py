"""Build, validate, and export the leg-wheel robot dog leg example."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import simplecadapi as scad

from leg_assembly import make_leg_wheel_robot_dog_leg_rassembly
from actuator import make_actuator_materials_rdict
from leg_common import ground_compound
from leg_materials import make_leg_materials_rdict
from leg_dimensions import validate_leg_interface_dimensions


# Example 16's reducer graph is intentionally deep because of herringbone gears.
sys.setrecursionlimit(40000)

OUT_DIR = Path("examples/out/leg_wheel_robot_dog_leg")


def _build_leg_wheel_robot_dog_leg():
    validate_leg_interface_dimensions()
    actuator_materials = make_actuator_materials_rdict()
    leg_materials = make_leg_materials_rdict()
    with scad.GraphSession(graph_id="leg_wheel_robot_dog_leg") as session:
        assembly = make_leg_wheel_robot_dog_leg_rassembly(
            actuator_materials=actuator_materials,
            leg_materials=leg_materials,
        )
        preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
        ground_compound(label="leg_preview", compound=preview)
        leaf_ops = [node.op for node in session.graph.leaf_nodes()]
        print(f"leg_graph_results: leaves={len(leaf_ops)} ops={','.join(leaf_ops)}")
        if leaf_ops != ["make_compound_from_assembly_rcompound"]:
            raise RuntimeError("Leg graph contains detached source results")
        session_json = scad.export_session_json(session=session)
        model_json = scad.export_model_json(session=session)
    return assembly, preview, model_json, session_json


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "leg_wheel_robot_dog_leg.model.json"
    session_path = OUT_DIR / "leg_wheel_robot_dog_leg.session.json"
    step_path = OUT_DIR / "leg_wheel_robot_dog_leg.step"
    fcstd_path = OUT_DIR / "leg_wheel_robot_dog_leg.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    assembly, preview, model_json, session_json = _build_leg_wheel_robot_dog_leg()
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
            document_name="LegWheelRobotDogLeg",
            freecad_cmd=None,
        )
        fcstd_status = f"{fcstd_path} ({fcstd_path.stat().st_size} bytes)"
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__}: {exc})"

    print(f"assembly={assembly.assembly_id}")
    print("components=" + ",".join(assembly.component_ids()))
    print("constraints=" + ",".join(assembly.constraint_ids()))
    print(f"preview_solids={len(preview.get_solids())}")
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
