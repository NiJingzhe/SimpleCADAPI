"""Build, validate, replay, and export the integrated BLDC joint actuator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import simplecadapi as scad

from assembly import make_integrated_bldc_joint_actuator_rassembly
from common import ground_compound
from dimensions import (
    MOTOR_AIR_GAP,
    MOTOR_POLE_COUNT,
    MOTOR_SLOT_COUNT,
    PACKAGE_RADIUS,
    PACKAGE_STRUCTURAL_BOTTOM_Z,
    PACKAGE_TOP_Z,
    TOTAL_REDUCTION,
    validate_design_dimensions,
)


sys.setrecursionlimit(30000)

OUT_DIR = Path("examples/out/integrated_bldc_joint_actuator")


def build_integrated_bldc_joint_actuator():
    """Build the replayable actuator and return product and interchange outputs."""

    validate_design_dimensions()
    with scad.GraphSession(graph_id="integrated_50mm_bldc_joint_actuator") as session:
        assembly = make_integrated_bldc_joint_actuator_rassembly()
        preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
        ground_compound(label="integrated_actuator_preview", compound=preview)
        session_json = scad.export_session_json(session=session, indent=2)
        model_json = scad.export_model_json(session=session, indent=2)
    return assembly, preview, model_json, session_json


def main() -> None:
    """Generate canonical model JSON, STEP, and optional FreeCAD output."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "integrated_bldc_joint_actuator.model.json"
    session_path = OUT_DIR / "integrated_bldc_joint_actuator.session.json"
    step_path = OUT_DIR / "integrated_bldc_joint_actuator.step"
    fcstd_path = OUT_DIR / "integrated_bldc_joint_actuator.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    assembly, preview, model_json, session_json = build_integrated_bldc_joint_actuator()
    model_path.write_text(model_json, encoding="utf-8")
    session_path.write_text(session_json, encoding="utf-8")
    scad.export_step(shapes=preview, filename=str(step_path))

    imported = scad.import_model_json(json_str=model_json)
    replayed = scad.replay_model_json(json_str=model_json, strict=True)
    payload = json.loads(model_json)

    fcstd_status = "not attempted"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            json_str=model_json,
            output_path=str(fcstd_path.resolve()),
            document_name="Integrated50mmBLDCJointActuator",
            freecad_cmd=None,
        )
        fcstd_status = f"{fcstd_path} ({fcstd_path.stat().st_size} bytes)"
    except Exception as exc:  # pragma: no cover - depends on local FreeCAD install
        fcstd_status = f"skipped ({exc.__class__.__name__}: {exc})"

    print(f"envelope_diameter={PACKAGE_RADIUS * 2.0:.1f}")
    print(f"structural_length={PACKAGE_TOP_Z - PACKAGE_STRUCTURAL_BOTTOM_Z:.1f}")
    print(f"motor_topology={MOTOR_SLOT_COUNT}_slot_{MOTOR_POLE_COUNT}_pole")
    print(f"motor_air_gap={MOTOR_AIR_GAP:.2f}")
    print(f"total_reduction={TOTAL_REDUCTION:.1f}")
    print(f"assembly={assembly.assembly_id}")
    print(f"components={len(assembly.component_ids())}")
    print(f"constraints={len(assembly.constraint_ids())}")
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
