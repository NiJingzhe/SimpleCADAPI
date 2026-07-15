"""A00 representative whole-machine convergence point."""

from __future__ import annotations

from dataclasses import dataclass

import simplecadapi as scad

from .beating import make_open_reed
from .bias_supply import make_bias_supply
from .binder_needles import make_binder_system
from .common import connector_ref, ground_assembly
from .engaging_rods import make_engaging_rods
from .frame import make_main_frame
from .guide_frames import make_guide_frame
from .guide_parts import make_guide_cartridge_assembly
from .index_drive import make_bias_index_drive
from .inventory import Inventory, TOP_LEVEL_COMPONENT_IDS
from .parameters import DetailLevel, MachineParameters, validate_concept_parameters
from .representative_parts import placement
from .skeleton import make_machine_skeleton
from .structural_support import StructuralSupportReport, require_structural_support
from .takeup import make_linear_takeup
from .warp_supply import make_warp_supply
from .weft_insertion import make_filling_system
from .width_control import make_width_control


@dataclass(frozen=True)
class MachineBuild:
    machine: scad.Assembly
    inventory: Inventory
    detail: DetailLevel
    blocked_capabilities: tuple[str, ...]
    structural_support: StructuralSupportReport


def make_representative_machine_assembly(
    *,
    parameters: MachineParameters,
    materials: dict[str, scad.Material],
    inventory: Inventory,
    detail: DetailLevel,
) -> MachineBuild:
    """Build every A-level subsystem in the evidence-limited HOME configuration."""

    validate_concept_parameters(parameters)
    if detail is DetailLevel.FULL:
        raise ValueError("representative assembly cannot silently satisfy FULL")

    guide_cartridge = make_guide_cartridge_assembly(
        parameters=parameters,
        body_material=materials["guide_polymer"],
        ceramic_material=materials["ceramic"],
    )

    products: dict[str, scad.Assembly] = {
        "a00_skeleton": make_machine_skeleton(
            parameters=parameters,
            materials=materials,
        ),
        "a10_main_frame": make_main_frame(
            parameters=parameters,
            materials=materials,
        ),
        "a20_warp_supply": make_warp_supply(
            parameters=parameters,
            materials=materials,
        ),
        "a30_upper_bias_supply": make_bias_supply(
            upper=True,
            parameters=parameters,
            materials=materials,
        ),
        "a31_lower_bias_supply": make_bias_supply(
            upper=False,
            parameters=parameters,
            materials=materials,
        ),
        "a40_upper_guide_frame": make_guide_frame(
            upper=True,
            parameters=parameters,
            materials=materials,
            guide_cartridge=guide_cartridge,
        ),
        "a41_lower_guide_frame": make_guide_frame(
            upper=False,
            parameters=parameters,
            materials=materials,
            guide_cartridge=guide_cartridge,
        ),
        "a42_bias_index_drive": make_bias_index_drive(
            parameters=parameters,
            materials=materials,
        ),
        "a50_binder_system": make_binder_system(
            parameters=parameters,
            materials=materials,
        ),
        "a60_filling_system": make_filling_system(
            parameters=parameters,
            materials=materials,
        ),
        "a61_engaging_rods": make_engaging_rods(
            parameters=parameters,
            materials=materials,
        ),
        "a70_open_reed": make_open_reed(
            parameters=parameters,
            materials=materials,
        ),
        "a80_width_hooks": make_width_control(
            parameters=parameters,
            materials=materials,
        ),
        "a90_linear_takeup": make_linear_takeup(
            parameters=parameters,
            materials=materials,
        ),
    }
    if tuple(products) != TOP_LEVEL_COMPONENT_IDS:
        raise ValueError(
            "whole-machine product tree does not match the authoritative IDs"
        )

    machine = scad.make_assembly_rassembly(
        assembly_id="weaving_machine_a00_representative_home",
        name="A00 representative four-axial multilayer weaving machine, HOME",
    )
    for component_id in TOP_LEVEL_COMPONENT_IDS:
        machine = scad.add_component_rassembly(
            assembly=machine,
            item=products[component_id],
            component_id=component_id,
            placement=placement((0.0, 0.0, 0.0)),
            name=products[component_id].name,
        )
    machine = scad.ground_component_rassembly(
        assembly=machine,
        component_id="a00_skeleton",
    )
    for component_id in TOP_LEVEL_COMPONENT_IDS[1:]:
        machine = scad.add_fixed_constraint_rassembly(
            assembly=machine,
            constraint_id=f"fix_{component_id}_to_skeleton",
            connector_a=connector_ref(
                component_id="a00_skeleton",
                connector_id=f"mount_{component_id}",
            ),
            connector_b=connector_ref(
                component_id=component_id,
                connector_id="machine_mount",
            ),
            name=f"Fix {component_id} to A00 master datums",
        )
    machine = scad.solve_assembly_constraints_rassembly(assembly=machine, strict=True)
    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=machine)
    if not report.solved or report.unsolved_component_ids:
        raise ValueError("representative whole-machine placement solve failed")
    structural_support = require_structural_support(machine=machine)
    ground_assembly(label="weaving_machine_a00_representative_home", assembly=machine)
    blocked = (
        "A40/A41 full guide-block occupancy and circulation topology",
        "A42 continuous conjugate-cam displacement law",
        "manufacturing dimensions, loads, tolerances, and procurement selections",
        "continuous-motion clearance, FEA, fatigue, and physical textile validation",
    )
    print(
        "a00_machine: "
        f"top_level_components={len(machine.component_ids())} "
        f"constraints={len(machine.constraint_ids())} pose=HOME detail={detail.value}"
    )
    return MachineBuild(
        machine=machine,
        inventory=inventory,
        detail=detail,
        blocked_capabilities=blocked,
        structural_support=structural_support,
    )
