"""Safe reuse boundary for the integrated Example 20 joint actuator."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import simplecadapi as scad


EXAMPLES_DIR = Path(__file__).resolve().parents[1]
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

_assembly = importlib.import_module("20_integrated_bldc_joint_actuator.assembly")
_dimensions = importlib.import_module("20_integrated_bldc_joint_actuator.dimensions")
_materials = importlib.import_module("20_integrated_bldc_joint_actuator.materials")

ACTUATOR_CASE_CLAMP_Z = _dimensions.OUTPUT_CASE_CLAMP_CENTER_Z
ACTUATOR_OUTPUT_FACE_Z = _dimensions.OUTPUT_FLANGE_TOP_Z
ACTUATOR_PACKAGE_RADIUS = _dimensions.PACKAGE_RADIUS
ACTUATOR_PACKAGE_BOTTOM_Z = _dimensions.PACKAGE_STRUCTURAL_BOTTOM_Z
ACTUATOR_PACKAGE_TOP_Z = _dimensions.PACKAGE_TOP_Z
OUTPUT_BOLT_ANGLES_DEGREES = _dimensions.OUTPUT_LINK_BOLT_ANGLES_DEGREES
OUTPUT_BOLT_CIRCLE_RADIUS = _dimensions.OUTPUT_LINK_HOLE_PCD / 2.0
OUTPUT_BOLT_COUNT = _dimensions.OUTPUT_LINK_BOLT_COUNT
OUTPUT_TAP_RADIUS = _dimensions.OUTPUT_LINK_TAP_RADIUS
OUTPUT_REGISTER_HEIGHT = _dimensions.OUTPUT_REGISTER_HEIGHT
OUTPUT_REGISTER_RADIUS = _dimensions.OUTPUT_REGISTER_RADIUS


def make_actuator_materials_rdict() -> dict[str, scad.Material]:
    """Create the externally supplied material set used by Example 20."""

    return _materials.make_actuator_materials_rdict()


def make_joint_actuator_rassembly(
    *, materials: dict[str, scad.Material]
) -> scad.Assembly:
    """Build the complete actuator as a two-body kinematic subassembly."""

    _dimensions.validate_design_dimensions()
    component_specs = _assembly.make_integrated_bldc_joint_actuator_components_rtuple(
        materials=materials
    )
    fixed_body = scad.make_assembly_rassembly(
        assembly_id="integrated_50mm_bldc_joint_actuator_fixed_body",
        name="Rigid actuator housing, motor, electronics, and reducer internals",
    )
    output_carrier = next(
        component for component in component_specs if component[0] == "output_carrier"
    )
    for component_id, item, source_placement, name in component_specs:
        if component_id == "output_carrier":
            continue
        fixed_body = scad.add_component_rassembly(
            assembly=fixed_body,
            item=item,
            component_id=component_id,
            placement=source_placement,
            name=name,
        )

    for connector_id, source_component_id, source_connector_id, name in (
        ("case_clamp_axis", "reducer_housing", "case_clamp_axis", "External split-clamp datum"),
        ("case_mount_axis", "output_bearing_cap", "case_mount_axis", "Fixed actuator case datum"),
        ("output_support_axis", "reducer_housing", "stage2_carrier_axis", "Output carrier bearing axis"),
        ("phase_terminal_access", "controller", "phase_access", "Rear phase-terminal service datum"),
        ("power_can_terminal_access", "controller", "power_can_access", "Rear power/CAN service datum"),
    ):
        fixed_body = scad.forward_connector_rassembly(
            assembly=fixed_body,
            connector_id=connector_id,
            source_component_id=source_component_id,
            source_connector_id=source_connector_id,
            name=name,
        )

    actuator = scad.make_assembly_rassembly(
        assembly_id="leg_joint_actuator",
        name="50 mm integrated BLDC actuator with one external output degree of freedom",
    )
    actuator = scad.add_component_rassembly(
        assembly=actuator,
        item=fixed_body,
        component_id="fixed_body",
        placement=scad.identity_placement_rplacement(),
        name="Rigid actuator body",
    )
    actuator = scad.add_component_rassembly(
        assembly=actuator,
        item=output_carrier[1],
        component_id="output_carrier",
        placement=output_carrier[2],
        name=output_carrier[3],
    )
    actuator = scad.ground_component_rassembly(
        assembly=actuator,
        component_id="fixed_body",
    )
    actuator = scad.add_revolute_constraint_rassembly(
        assembly=actuator,
        constraint_id="output_revolute",
        connector_a=scad.make_connector_ref_rconnectorref(
            component_id="fixed_body",
            connector_id="output_support_axis",
        ),
        connector_b=scad.make_connector_ref_rconnectorref(
            component_id="output_carrier",
            connector_id="carrier_axis",
        ),
        name="Actuator output carrier rotation",
    )
    actuator = scad.solve_assembly_constraints_rassembly(
        assembly=actuator,
        strict=True,
    )
    for connector_id, source_component_id, source_connector_id, name in (
        ("case_clamp_axis", "fixed_body", "case_clamp_axis", "External split-clamp datum"),
        ("case_mount_axis", "fixed_body", "case_mount_axis", "Fixed actuator case datum"),
        ("output_link_axis", "output_carrier", "output_link_axis", "Rotating six-hole output flange"),
        ("phase_terminal_access", "fixed_body", "phase_terminal_access", "Rear phase-terminal service datum"),
        ("power_can_terminal_access", "fixed_body", "power_can_terminal_access", "Rear power/CAN service datum"),
    ):
        actuator = scad.forward_connector_rassembly(
            assembly=actuator,
            connector_id=connector_id,
            source_component_id=source_component_id,
            source_connector_id=source_connector_id,
            name=name,
        )
    print(
        "leg_joint_actuator: "
        f"diameter={ACTUATOR_PACKAGE_RADIUS * 2.0:.1f} "
        f"length={ACTUATOR_PACKAGE_TOP_Z - ACTUATOR_PACKAGE_BOTTOM_Z:.1f} "
        f"output_pcd={OUTPUT_BOLT_CIRCLE_RADIUS * 2.0:.1f} "
        f"components={len(actuator.component_ids())} revolutes=1 "
        f"connectors={','.join(actuator.connector_ids())}"
    )
    return actuator
