"""Replayable D1 single-axis guide-block and wear-rail test fixture."""

from __future__ import annotations

from dataclasses import dataclass

import simplecadapi as scad

from .common import connector_ref, ground_assembly
from .guide_parts import make_guide_cartridge_assembly, make_wear_rail_part
from .kinematics import JointAudit, JointContract, audit_joint_contract
from .parameters import MachineParameters, validate_concept_parameters


@dataclass(frozen=True)
class GuideFixtureBuild:
    assembly: scad.Assembly
    joint_contract: JointContract
    joint_audit: JointAudit
    requested_position: float
    solved_position: float


def guide_fixture_joint(parameters: MachineParameters) -> JointContract:
    return JointContract(
        joint_id="guide_slide_y",
        parent_component_id="wear_rail",
        child_component_id="guide_cartridge",
        joint_kind="prismatic",
        axis=(0.0, 1.0, 0.0),
        lower_limit=0.0,
        upper_limit=parameters.guide_slide_travel.value,
        mechanical_zero=0.0,
        safe_hold="pitch lock engaged; pusher unloaded",
    )


def make_guide_fixture_assembly(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
    position: float,
    clamp_position: bool = False,
) -> GuideFixtureBuild:
    validate_concept_parameters(parameters)
    required_materials = {"guide_polymer", "ceramic", "wear_rail"}
    missing = sorted(required_materials - materials.keys())
    if missing:
        raise ValueError("missing guide materials: " + ", ".join(missing))
    contract = guide_fixture_joint(parameters)
    solved_position = contract.resolve_drive(position, clamp=clamp_position)
    guide = make_guide_cartridge_assembly(
        parameters=parameters,
        body_material=materials["guide_polymer"],
        ceramic_material=materials["ceramic"],
    )
    rail = make_wear_rail_part(parameters=parameters, material=materials["wear_rail"])
    assembly = scad.make_assembly_rassembly(
        assembly_id="d1_guide_slide_fixture",
        name="D1 guide-block Y-slide fixture, not functional A40",
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=rail,
        component_id="wear_rail",
        placement=scad.identity_placement_rplacement(),
        name="Fixed replaceable rail",
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=guide,
        component_id="guide_cartridge",
        placement=scad.identity_placement_rplacement(),
        name="Moving guide cartridge",
    )
    assembly = scad.ground_component_rassembly(
        assembly=assembly, component_id="wear_rail"
    )
    assembly = scad.add_prismatic_constraint_rassembly(
        assembly=assembly,
        constraint_id=contract.joint_id,
        connector_a=connector_ref(component_id="wear_rail", connector_id="slide_axis"),
        connector_b=connector_ref(
            component_id="guide_cartridge", connector_id="slide_axis"
        ),
        drive_distance=solved_position,
        distance_limit=scad.make_scalar_limit_rscalarlimit(
            lower_value=contract.lower_limit,
            upper_value=contract.upper_limit,
        ),
        name="One-pitch Y slide",
    )
    assembly = scad.solve_assembly_constraints_rassembly(assembly=assembly, strict=True)
    audit = audit_joint_contract(assembly=assembly, contract=contract)
    if not audit.passed:
        raise ValueError(audit.message)
    ground_assembly(label="d1_guide_slide_fixture", assembly=assembly)
    print(
        f"d1_joint_audit: passed={audit.passed} axis=Y position={solved_position:.3f} "
        "claim=placement_and_contract_only"
    )
    return GuideFixtureBuild(assembly, contract, audit, position, solved_position)
