"""Build and export the integrated BLDC joint actuator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import simplecadapi as scad

try:
    from .assembly import make_integrated_bldc_joint_actuator_rassembly
    from .common import ground_compound
    from .dimensions import (
        MOTOR_AIR_GAP,
        MOTOR_POLE_COUNT,
        MOTOR_SLOT_COUNT,
        PACKAGE_RADIUS,
        PACKAGE_STRUCTURAL_BOTTOM_Z,
        PACKAGE_TOP_Z,
        TOTAL_REDUCTION,
        validate_design_dimensions,
    )
    from .materials import make_actuator_materials_rdict
except ImportError:  # Support direct execution from this example directory.
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
    from materials import make_actuator_materials_rdict


sys.setrecursionlimit(30000)

OUT_DIR = Path("examples/out/integrated_bldc_joint_actuator")


@scad.model(graph_id="integrated_50mm_bldc_joint_actuator")
def build_integrated_bldc_joint_actuator():
    """Build the replayable actuator and return product and interchange outputs."""

    validate_design_dimensions()
    materials = make_actuator_materials_rdict()
    assembly = make_integrated_bldc_joint_actuator_rassembly(materials=materials)
    preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    preview = scad.apply_tag(
        shape=preview,
        tag="scene.integrated.bldc.joint.actuator.preview",
    )
    ground_compound(label="integrated_actuator_preview", compound=preview)
    scad.capture_result(value=(assembly, preview))
    return assembly, preview


def main() -> None:
    """Generate canonical model JSON, STEP, and optional FreeCAD output."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "integrated_bldc_joint_actuator.model.json"
    session_path = OUT_DIR / "integrated_bldc_joint_actuator.session.json"
    step_path = OUT_DIR / "integrated_bldc_joint_actuator.step"
    fcstd_path = OUT_DIR / "integrated_bldc_joint_actuator.FCStd"
    if fcstd_path.exists():
        fcstd_path.unlink()

    result = build_integrated_bldc_joint_actuator()
    assembly, preview = result.value
    model_path.write_text(result.model_json, encoding="utf-8")
    session_path.write_text(result.session_json, encoding="utf-8")
    scad.export_step(shapes=preview, filename=str(step_path))

    payload = json.loads(result.model_json)

    fcstd_status = "not attempted"
    try:
        scad.translator.freecad_translator.translate_model_json_to_fcstd(
            json_str=result.model_json,
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
    print(f"graph_nodes={len(payload['graph']['nodes'])}")
    print(f"model={model_path}")
    print(f"session={session_path}")
    print(f"step={step_path}")
    print(f"fcstd={fcstd_status}")


if __name__ == "__main__":
    main()
