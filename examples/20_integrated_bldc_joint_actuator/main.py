"""Build and export the integrated BLDC joint actuator."""

from __future__ import annotations

import sys
from pathlib import Path

import simplecadapi as scad

try:
    from .assembly import build_integrated_bldc_joint_actuator as build_durable_actuator
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
except ImportError:  # Support direct execution from this example directory.
    from assembly import build_integrated_bldc_joint_actuator as build_durable_actuator
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

OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "integrated_bldc_joint_actuator"


def build_integrated_bldc_joint_actuator() -> scad.AssemblyBuildResult:
    """Build the actuator through durable part and assembly boundaries."""

    validate_design_dimensions()
    return build_durable_actuator()


def main() -> None:
    """Generate and verify synchronized package, AP242 STEP, and FCStd output."""

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    package_path = OUT_DIR / "integrated_bldc_joint_actuator.scadpkg"
    step_path = OUT_DIR / "integrated_bldc_joint_actuator.step"
    fcstd_path = OUT_DIR / "integrated_bldc_joint_actuator.FCStd"
    product_result = build_integrated_bldc_joint_actuator()
    assembly = product_result.value
    scad.capture(product_result, package_path)
    packaged_definition = scad.load_product_package(package_path)
    rebuilt = scad.materialize_definition(packaged_definition)
    if not isinstance(rebuilt, scad.Assembly):
        raise RuntimeError("product package root did not materialize as an assembly")
    if rebuilt.assembly_id != assembly.assembly_id:
        raise RuntimeError("product package replay changed the assembly identity")
    preview = scad.make_compound_from_assembly_rcompound(assembly=assembly)
    ground_compound(label="durable_actuator_preview", compound=preview)
    step_report = scad.exporter.export_product_package_to_step(package_path,
    step_path,)
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        package_path,
        str(fcstd_path),
        document_name="IntegratedBLDCJointActuator",
    )

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
    print(f"product_package={package_path}")
    print(f"step={step_report.output_path}")
    print(f"fcstd={fcstd_path}")


if __name__ == "__main__":
    main()
