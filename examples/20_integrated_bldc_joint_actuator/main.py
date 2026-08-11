"""Build and export the integrated BLDC joint actuator."""

from __future__ import annotations

import sys
from pathlib import Path

import simplecadapi as scad

try:
    from .assembly import (
        build_integrated_bldc_joint_actuator as build_durable_actuator,
        make_integrated_bldc_joint_actuator_rassembly,
    )
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
    from assembly import (
        build_integrated_bldc_joint_actuator as build_durable_actuator,
        make_integrated_bldc_joint_actuator_rassembly,
    )
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

OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "integrated_bldc_joint_actuator"


def build_integrated_bldc_joint_actuator() -> scad.AssemblyBuildResult:
    """Build the actuator through durable part and assembly boundaries."""

    validate_design_dimensions()
    return build_durable_actuator()


@scad.model(graph_id="integrated_50mm_bldc_joint_actuator")
def _build_integrated_bldc_joint_actuator_model():
    """Build canonical graph JSON for STEP and FreeCAD translator coverage."""

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


def export_translator_artifacts() -> tuple[Path, Path, Path]:
    """Build the separate canonical graph and run the FreeCAD backend."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "integrated_bldc_joint_actuator.model.json"
    session_path = OUT_DIR / "integrated_bldc_joint_actuator.session.json"
    fcstd_path = OUT_DIR / "integrated_bldc_joint_actuator.FCStd"
    model_result = _build_integrated_bldc_joint_actuator_model()
    model_path.write_text(model_result.model_json, encoding="utf-8")
    session_path.write_text(model_result.session_json, encoding="utf-8")
    scad.translator.freecad_translator.translate_model_json_to_fcstd(
        json_str=model_result.model_json,
        output_path=str(fcstd_path.resolve()),
        document_name="Integrated50mmBLDCJointActuator",
        freecad_cmd=None,
    )
    return model_path, session_path, fcstd_path


def main() -> None:
    """Generate and verify the durable product definition and STEP output."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    definition_path = OUT_DIR / "integrated_bldc_joint_actuator.assembly-definition.zip"
    step_path = OUT_DIR / "integrated_bldc_joint_actuator.step"
    product_result = build_integrated_bldc_joint_actuator()
    assembly = product_result.value
    product_result.export_definition(path=definition_path)
    rebuilt = product_result.replay()
    if rebuilt.assembly_id != assembly.assembly_id:
        raise RuntimeError("durable assembly replay changed the assembly identity")
    preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    ground_compound(label="durable_actuator_preview", compound=preview)
    scad.export_step(shapes=preview, filename=str(step_path))

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
    print(f"definition={definition_path}")
    print(f"step={step_path}")


if __name__ == "__main__":
    main()
