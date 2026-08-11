"""Top-level integrated BLDC motor, controller, reducer, and housing assembly."""

from __future__ import annotations

import math

import simplecadapi as scad

try:
    from .bearings import (
        build_bearing_ring_definitions,
        coaxial_bearing_placement,
        make_coaxial_bearing_rplacement,
        make_main_bearing_rassembly,
        make_planet_bearing_rplacement,
        make_standard_planet_bearing_rassembly,
        planet_bearing_placement,
    )
    from .common import (
        CACHE,
        connector_ref,
        ground_constraint_report,
        z_rotation_placement,
    )
    from .dimensions import (
        FRONT_MOTOR_BEARING,
        FRONT_MOTOR_BEARING_CENTER_Z,
        INTERSTAGE_BEARING,
        INTERSTAGE_BEARING_CENTER_Z,
        MOTOR_POLE_COUNT,
        MOTOR_SLOT_COUNT,
        OUTPUT_BEARING,
        OUTPUT_BEARING_1_CENTER_Z,
        OUTPUT_BEARING_2_CENTER_Z,
        PCB_BOTTOM_Z,
        PCB_THICKNESS,
        PLANET_BEARING,
        PLANET_COUNT,
        REAR_BEARING_CENTER_Z,
        REAR_MOTOR_BEARING,
        STAGE_1,
        STAGE_2,
        TOTAL_REDUCTION,
        BearingSpec,
        StageSpec,
    )
    from .electronics import (
        MOSFET_ANGLES,
        PHASE_TERMINAL_CENTER,
        POWER_CAN_TERMINAL_CENTER,
        build_controller_pcb_part,
        build_mosfet_part,
        build_phase_terminal_part,
        build_power_can_terminal_part,
        make_integrated_controller_rassembly,
    )
    from .gears import (
        build_stage1_carrier_part,
        build_stage1_fixed_ring_part,
        build_stage1_reusable_planet_part,
        build_stage2_fixed_ring_part,
        build_stage2_output_carrier_part,
        build_stage2_reusable_planet_part,
        make_output_carrier_flange_rpart,
        make_planet_rplacement,
        make_stage1_carrier_sun_rpart,
        make_stage_planet_gear_rpart,
        make_stage_ring_gear_rpart,
        planet_center_xy,
    )
    from .housing import (
        build_motor_shell_part,
        build_output_bearing_cap_part,
        build_rear_bearing_spider_part,
        build_rear_electronics_cover_part,
        build_reducer_housing_part,
        make_motor_shell_rpart,
        make_output_bearing_cap_rpart,
        make_rear_bearing_spider_rpart,
        make_rear_electronics_cover_rpart,
        make_reducer_housing_rpart,
    )
    from .motor import (
        build_rotor_core_part,
        build_rotor_magnet_part,
        build_slot_winding_part,
        build_stator_core_part,
        make_bldc_rotor_rassembly,
        make_bldc_stator_rassembly,
    )
except ImportError:  # Support direct execution from this example directory.
    from bearings import (
        build_bearing_ring_definitions,
        coaxial_bearing_placement,
        make_coaxial_bearing_rplacement,
        make_main_bearing_rassembly,
        make_planet_bearing_rplacement,
        make_standard_planet_bearing_rassembly,
        planet_bearing_placement,
    )
    from common import CACHE, connector_ref, ground_constraint_report, z_rotation_placement
    from dimensions import (
        FRONT_MOTOR_BEARING,
        FRONT_MOTOR_BEARING_CENTER_Z,
        INTERSTAGE_BEARING,
        INTERSTAGE_BEARING_CENTER_Z,
        MOTOR_POLE_COUNT,
        MOTOR_SLOT_COUNT,
        OUTPUT_BEARING,
        OUTPUT_BEARING_1_CENTER_Z,
        OUTPUT_BEARING_2_CENTER_Z,
        PCB_BOTTOM_Z,
        PCB_THICKNESS,
        PLANET_BEARING,
        PLANET_COUNT,
        REAR_BEARING_CENTER_Z,
        REAR_MOTOR_BEARING,
        STAGE_1,
        STAGE_2,
        TOTAL_REDUCTION,
        BearingSpec,
        StageSpec,
    )
    from electronics import (
        MOSFET_ANGLES,
        PHASE_TERMINAL_CENTER,
        POWER_CAN_TERMINAL_CENTER,
        build_controller_pcb_part,
        build_mosfet_part,
        build_phase_terminal_part,
        build_power_can_terminal_part,
        make_integrated_controller_rassembly,
    )
    from gears import (
        build_stage1_carrier_part,
        build_stage1_fixed_ring_part,
        build_stage1_reusable_planet_part,
        build_stage2_fixed_ring_part,
        build_stage2_output_carrier_part,
        build_stage2_reusable_planet_part,
        make_output_carrier_flange_rpart,
        make_planet_rplacement,
        make_stage1_carrier_sun_rpart,
        make_stage_planet_gear_rpart,
        make_stage_ring_gear_rpart,
        planet_center_xy,
    )
    from housing import (
        build_motor_shell_part,
        build_output_bearing_cap_part,
        build_rear_bearing_spider_part,
        build_rear_electronics_cover_part,
        build_reducer_housing_part,
        make_motor_shell_rpart,
        make_output_bearing_cap_rpart,
        make_rear_bearing_spider_rpart,
        make_rear_electronics_cover_rpart,
        make_reducer_housing_rpart,
    )
    from motor import (
        build_rotor_core_part,
        build_rotor_magnet_part,
        build_slot_winding_part,
        build_stator_core_part,
        make_bldc_rotor_rassembly,
        make_bldc_stator_rassembly,
    )


@scad.requires_session
def make_integrated_bldc_joint_actuator_rassembly(
    *, materials: dict[str, scad.Material]
) -> scad.Assembly:
    """Build and solve the complete compact 50 mm joint actuator."""

    component_specs = make_integrated_bldc_joint_actuator_components_rtuple(
        materials=materials
    )
    actuator = scad.make_assembly_rassembly(
        assembly_id="integrated_50mm_bldc_joint_actuator",
        name="50 mm 12-slot/14-pole BLDC joint actuator with 20:1 reducer and circular ESC",
    )
    for component_id, item, placement, name in component_specs:
        actuator = scad.add_component_rassembly(
            assembly=actuator,
            item=item,
            component_id=component_id,
            placement=placement,
            name=name,
        )

    actuator = _add_public_connectors_rassembly(assembly=actuator)
    actuator = _add_constraints_rassembly(assembly=actuator)
    actuator = scad.solve_assembly_constraints_rassembly(assembly=actuator, strict=True)
    ground_constraint_report(label="actuator", assembly=actuator)
    return actuator


@scad.requires_session
def make_integrated_bldc_joint_actuator_components_rtuple(
    *, materials: dict[str, scad.Material]
) -> tuple[tuple[str, scad.Part | scad.Assembly, scad.Placement, str], ...]:
    """Build the actuator component inventory without creating a parent assembly."""

    print(
        f"ratio_plan: stage1={STAGE_1.fixed_ring_ratio:.1f}:1 "
        f"stage2={STAGE_2.fixed_ring_ratio:.1f}:1 total={TOTAL_REDUCTION:.1f}:1"
    )
    reducer_housing = make_reducer_housing_rpart(material=materials["housing"])
    motor_shell = make_motor_shell_rpart(material=materials["housing"])
    rear_spider = make_rear_bearing_spider_rpart(material=materials["carrier"])
    rear_cover = make_rear_electronics_cover_rpart(material=materials["housing"])
    output_cap = make_output_bearing_cap_rpart(material=materials["carrier"])
    stator = make_bldc_stator_rassembly(
        steel_material=materials["electrical_steel"],
        copper_material=materials["copper"],
    )
    rotor = make_bldc_rotor_rassembly(
        steel_material=materials["gear"],
        magnet_material=materials["magnet"],
    )
    controller = make_integrated_controller_rassembly(
        pcb_material=materials["pcb"],
        terminal_material=materials["terminal"],
    )

    stage1_ring = make_stage_ring_gear_rpart(stage=STAGE_1, material=materials["gear"])
    stage1_planet = make_stage_planet_gear_rpart(stage=STAGE_1, material=materials["gear"])
    stage1_carrier = make_stage1_carrier_sun_rpart(material=materials["gear"])
    stage2_ring = make_stage_ring_gear_rpart(stage=STAGE_2, material=materials["gear"])
    stage2_planet = make_stage_planet_gear_rpart(stage=STAGE_2, material=materials["gear"])
    output_carrier = make_output_carrier_flange_rpart(stage=STAGE_2, material=materials["carrier"])

    rear_motor_bearing = make_main_bearing_rassembly(
        bearing_id="rear_motor_8x16x5",
        spec=REAR_MOTOR_BEARING,
        material=materials["gear"],
    )
    front_motor_bearing = make_main_bearing_rassembly(
        bearing_id="front_motor_8x19x6",
        spec=FRONT_MOTOR_BEARING,
        material=materials["gear"],
    )
    interstage_bearing = make_main_bearing_rassembly(
        bearing_id="interstage_5x10x3",
        spec=INTERSTAGE_BEARING,
        material=materials["gear"],
    )
    planet_bearing = make_standard_planet_bearing_rassembly(
        bearing_id="planet_3x6x3",
        spec=PLANET_BEARING,
        material=materials["gear"],
    )
    output_bearing = make_main_bearing_rassembly(
        bearing_id="output_16x24x5",
        spec=OUTPUT_BEARING,
        material=materials["gear"],
    )

    fixed_components = (
        ("reducer_housing", reducer_housing, scad.identity_placement_rplacement(), "Fixed reducer housing"),
        ("motor_shell", motor_shell, scad.identity_placement_rplacement(), "Fixed BLDC shell"),
        ("rear_bearing_spider", rear_spider, scad.identity_placement_rplacement(), "Rear motor-bearing spider"),
        ("rear_electronics_cover", rear_cover, scad.identity_placement_rplacement(), "Rear controller cover"),
        ("output_bearing_cap", output_cap, scad.identity_placement_rplacement(), "Output bearing cap"),
        ("stator", stator, scad.identity_placement_rplacement(), "12-slot fixed stator"),
        ("rotor", rotor, scad.identity_placement_rplacement(), "14-pole rotor and direct sun shaft"),
        ("controller", controller, scad.identity_placement_rplacement(), "Circular integrated controller"),
        ("stage1_carrier", stage1_carrier, scad.identity_placement_rplacement(), "Stage 1 carrier and stage 2 sun"),
        ("output_carrier", output_carrier, scad.identity_placement_rplacement(), "Stage 2 carrier and output flange"),
        ("stage1_ring", stage1_ring, _stage_rplacement(stage=STAGE_1), "Stage 1 fixed ring insert"),
        ("stage2_ring", stage2_ring, _stage_rplacement(stage=STAGE_2), "Stage 2 fixed ring insert"),
    )
    print(f"actuator_base_components: count={len(fixed_components)}")

    planet_components = []
    for stage, planet in ((STAGE_1, stage1_planet), (STAGE_2, stage2_planet)):
        for index in range(PLANET_COUNT):
            planet_components.append(
                (
                    f"{stage.stage_id}_planet_{index + 1}",
                    planet,
                    make_planet_rplacement(stage=stage, index=index),
                    f"{stage.label} planet {index + 1}",
                )
            )

    bearing_components = (
        (
            "rear_motor_bearing",
            rear_motor_bearing,
            make_coaxial_bearing_rplacement(center_z=REAR_BEARING_CENTER_Z),
            "Rear rotor bearing",
        ),
        (
            "front_motor_bearing",
            front_motor_bearing,
            make_coaxial_bearing_rplacement(center_z=FRONT_MOTOR_BEARING_CENTER_Z),
            "Front rotor bearing",
        ),
        (
            "interstage_bearing",
            interstage_bearing,
            make_coaxial_bearing_rplacement(center_z=INTERSTAGE_BEARING_CENTER_Z),
            "Stage 1 carrier support bearing",
        ),
        (
            "output_bearing_1",
            output_bearing,
            make_coaxial_bearing_rplacement(center_z=OUTPUT_BEARING_1_CENTER_Z),
            "Rear output bearing",
        ),
        (
            "output_bearing_2",
            output_bearing,
            make_coaxial_bearing_rplacement(center_z=OUTPUT_BEARING_2_CENTER_Z),
            "Front output bearing",
        ),
    )
    planet_bearing_components = []
    for stage in (STAGE_1, STAGE_2):
        for index in range(PLANET_COUNT):
            planet_bearing_components.append(
                (
                    f"{stage.stage_id}_planet_bearing_{index + 1}",
                    planet_bearing,
                    make_planet_bearing_rplacement(stage=stage, index=index),
                    f"{stage.label} planet bearing {index + 1}",
                )
            )
    print(f"bearing_components: motor=2 interstage=1 output=2 planet={PLANET_COUNT * 2}")
    return tuple(
        [
            *fixed_components,
            *planet_components,
            *bearing_components,
            *planet_bearing_components,
        ]
    )


def _add_public_connectors_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    forwarded = (
        ("case_clamp_axis", "reducer_housing", "case_clamp_axis", "External split-clamp datum"),
        ("case_mount_axis", "output_bearing_cap", "case_mount_axis", "Fixed actuator case datum"),
        ("output_link_axis", "output_carrier", "output_link_axis", "Rotating six-hole output flange"),
        ("phase_terminal_access", "controller", "phase_access", "Rear phase-terminal service datum"),
        ("power_can_terminal_access", "controller", "power_can_access", "Rear power/CAN service datum"),
    )
    for connector_id, source_component_id, source_connector_id, name in forwarded:
        assembly = scad.forward_connector_rassembly(
            assembly=assembly,
            connector_id=connector_id,
            source_component_id=source_component_id,
            source_connector_id=source_connector_id,
            name=name,
            offset=None,
        )
    print("actuator_public_connectors: " + ",".join(item[0] for item in forwarded))
    return assembly


def _add_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="reducer_housing")
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="stage1_ring")
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="stage2_ring")
    fixed_pairs = (
        ("motor_shell_to_reducer_housing", "reducer_housing", "motor_mount_axis", "motor_shell", "reducer_mount_axis"),
        ("rear_spider_to_motor_shell", "motor_shell", "rear_spider_axis", "rear_bearing_spider", "shell_axis"),
        ("rear_cover_to_motor_shell", "motor_shell", "rear_cover_axis", "rear_electronics_cover", "shell_axis"),
        ("stator_to_motor_shell", "motor_shell", "stator_axis", "stator", "shell_axis"),
        ("controller_to_rear_cover", "rear_electronics_cover", "pcb_axis", "controller", "cover_axis"),
        ("stage1_ring_fixed", "reducer_housing", "stage1_ring_axis", "stage1_ring", "axis"),
        ("stage2_ring_fixed", "reducer_housing", "stage2_ring_axis", "stage2_ring", "axis"),
        ("output_cap_to_reducer_housing", "reducer_housing", "output_cap_axis", "output_bearing_cap", "housing_axis"),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector in fixed_pairs:
        assembly = scad.add_fixed_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=connector_ref(component_id=a_component, connector_id=a_connector),
            connector_b=connector_ref(component_id=b_component, connector_id=b_connector),
            name=constraint_id.replace("_", " "),
        )

    primary_revolutes = (
        ("rotor_revolute", "reducer_housing", "front_motor_bearing_axis", "rotor", "front_bearing_axis"),
        ("stage1_carrier_revolute", "reducer_housing", "stage1_carrier_axis", "stage1_carrier", "carrier_axis"),
        ("output_carrier_revolute", "reducer_housing", "stage2_carrier_axis", "output_carrier", "carrier_axis"),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector in primary_revolutes:
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=connector_ref(component_id=a_component, connector_id=a_connector),
            connector_b=connector_ref(component_id=b_component, connector_id=b_connector),
            drive_angle_degrees=0.0,
            angle_limit=None,
            name=constraint_id.replace("_", " "),
        )

    assembly = _add_stage_constraints_rassembly(
        assembly=assembly,
        stage=STAGE_1,
        sun_component="rotor",
        sun_connector="front_bearing_axis",
        ring_component="stage1_ring",
        carrier_component="stage1_carrier",
    )
    assembly = _add_stage_constraints_rassembly(
        assembly=assembly,
        stage=STAGE_2,
        sun_component="stage1_carrier",
        sun_connector="carrier_axis",
        ring_component="stage2_ring",
        carrier_component="output_carrier",
    )
    assembly = _add_bearing_constraints_rassembly(assembly=assembly)
    print("actuator_constraints: fixed=8 primary_revolute=3 planet_revolute=6 gear=6 internal=6 bearing_interfaces=22")
    return assembly


def _add_stage_constraints_rassembly(
    *,
    assembly: scad.Assembly,
    stage: StageSpec,
    sun_component: str,
    sun_connector: str,
    ring_component: str,
    carrier_component: str,
) -> scad.Assembly:
    for index in range(PLANET_COUNT):
        planet_component = f"{stage.stage_id}_planet_{index + 1}"
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"{planet_component}_revolute",
            connector_a=connector_ref(component_id=carrier_component, connector_id=f"planet_{index + 1}_axis"),
            connector_b=connector_ref(component_id=planet_component, connector_id="axis"),
            drive_angle_degrees=None,
            angle_limit=None,
            name=f"{stage.label} planet {index + 1} bearing axis",
        )
        assembly = scad.add_gear_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"{stage.stage_id}_sun_planet_{index + 1}_mesh",
            connector_a=connector_ref(component_id=sun_component, connector_id=sun_connector),
            connector_b=connector_ref(component_id=planet_component, connector_id="axis"),
            pitch_radius_a=stage.sun_pitch_radius,
            pitch_radius_b=stage.planet_pitch_radius,
            phase_offset=None,
            name=f"{stage.label} sun to planet {index + 1} external mesh",
        )
        assembly = scad.add_belt_constraint_rassembly(
            assembly=assembly,
            constraint_id=f"{stage.stage_id}_ring_planet_{index + 1}_internal_mesh",
            connector_a=connector_ref(component_id=ring_component, connector_id="axis"),
            connector_b=connector_ref(component_id=planet_component, connector_id="axis"),
            pulley_radius_a=stage.ring_pitch_radius,
            pulley_radius_b=stage.planet_pitch_radius,
            phase_offset=None,
            name=f"{stage.label} fixed-ring to planet {index + 1} internal mesh",
        )
    print(
        f"{stage.stage_id}_mesh: sun_r={stage.sun_pitch_radius:.3f} "
        f"planet_r={stage.planet_pitch_radius:.3f} center={stage.planet_center_radius:.3f}"
    )
    return assembly


def _add_bearing_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    interfaces = (
        ("rear_bearing_outer_to_spider", "rear_bearing_spider", "bearing_axis", "rear_motor_bearing", "outer_axis"),
        ("rear_bearing_inner_to_rotor", "rotor", "rear_bearing_axis", "rear_motor_bearing", "inner_axis"),
        ("front_bearing_outer_to_housing", "reducer_housing", "front_motor_bearing_axis", "front_motor_bearing", "outer_axis"),
        ("front_bearing_inner_to_rotor", "rotor", "front_bearing_axis", "front_motor_bearing", "inner_axis"),
        ("interstage_bearing_outer_to_housing", "reducer_housing", "interstage_bearing_axis", "interstage_bearing", "outer_axis"),
        ("interstage_bearing_inner_to_carrier", "stage1_carrier", "interstage_bearing_axis", "interstage_bearing", "inner_axis"),
        ("output_bearing_1_outer_to_cap", "output_bearing_cap", "bearing_1_axis", "output_bearing_1", "outer_axis"),
        ("output_bearing_1_inner_to_carrier", "output_carrier", "bearing_1_axis", "output_bearing_1", "inner_axis"),
        ("output_bearing_2_outer_to_cap", "output_bearing_cap", "bearing_2_axis", "output_bearing_2", "outer_axis"),
        ("output_bearing_2_inner_to_carrier", "output_carrier", "bearing_2_axis", "output_bearing_2", "inner_axis"),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector in interfaces:
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=connector_ref(component_id=a_component, connector_id=a_connector),
            connector_b=connector_ref(component_id=b_component, connector_id=b_connector),
            drive_angle_degrees=None,
            angle_limit=None,
            name=constraint_id.replace("_", " "),
        )
    for stage, carrier_component in ((STAGE_1, "stage1_carrier"), (STAGE_2, "output_carrier")):
        for index in range(PLANET_COUNT):
            planet = f"{stage.stage_id}_planet_{index + 1}"
            bearing = f"{stage.stage_id}_planet_bearing_{index + 1}"
            assembly = scad.add_revolute_constraint_rassembly(
                assembly=assembly,
                constraint_id=f"{bearing}_outer_to_planet",
                connector_a=connector_ref(component_id=planet, connector_id="bearing_axis"),
                connector_b=connector_ref(component_id=bearing, connector_id="outer_axis"),
                drive_angle_degrees=None,
                angle_limit=None,
                name=f"{stage.label} planet {index + 1} bearing outer-ring fit",
            )
            assembly = scad.add_revolute_constraint_rassembly(
                assembly=assembly,
                constraint_id=f"{bearing}_inner_to_pin",
                connector_a=connector_ref(
                    component_id=carrier_component,
                    connector_id=f"planet_{index + 1}_bearing_axis",
                ),
                connector_b=connector_ref(component_id=bearing, connector_id="inner_axis"),
                drive_angle_degrees=None,
                angle_limit=None,
                name=f"{stage.label} planet {index + 1} bearing inner-ring pin fit",
            )
    return assembly


def _stage_rplacement(*, stage: StageSpec) -> scad.Placement:
    return scad.make_placement_rplacement(origin=(0.0, 0.0, stage.bottom_z))


def _build_bearing_definition(
    *,
    bearing_id: str,
    spec: BearingSpec,
) -> scad.AssemblyBuildResult:
    outer, inner = build_bearing_ring_definitions(
        bearing_id=bearing_id,
        spec=spec,
    )

    @scad.assemble(
        id=bearing_id,
        definitions=(outer, inner),
        cache=CACHE,
    )
    def build() -> scad.Assembly:
        bearing = scad.make_assembly_rassembly(
            assembly_id=bearing_id,
            name=f"{bearing_id} fused rolling-element bearing",
        )
        identity = scad.identity_placement_rplacement()
        bearing = scad.add_component_rassembly(
            assembly=bearing,
            item=outer.value,
            component_id="outer_ring",
            placement=identity,
            name="Outer bearing ring with fused balls",
        )
        bearing = scad.add_component_rassembly(
            assembly=bearing,
            item=inner.value,
            component_id="inner_ring",
            placement=identity,
            name="Inner bearing ring",
        )
        bearing = scad.ground_component_rassembly(
            assembly=bearing,
            component_id="outer_ring",
        )
        bearing = scad.add_revolute_constraint_rassembly(
            assembly=bearing,
            constraint_id="inner_outer_revolute",
            connector_a=connector_ref(
                component_id="outer_ring",
                connector_id="axis",
            ),
            connector_b=connector_ref(
                component_id="inner_ring",
                connector_id="axis",
            ),
            drive_angle_degrees=None,
            angle_limit=None,
            name="Inner ring spins in outer ring",
        )
        offset = scad.make_placement_rplacement(
            origin=(0.0, 0.0, -spec.width / 2.0),
        )
        bearing = scad.forward_connector_rassembly(
            assembly=bearing,
            connector_id="outer_axis",
            source_component_id="outer_ring",
            source_connector_id="axis",
            name="Outer ring housing axis",
            offset=offset,
        )
        bearing = scad.forward_connector_rassembly(
            assembly=bearing,
            connector_id="inner_axis",
            source_component_id="inner_ring",
            source_connector_id="axis",
            name="Inner ring shaft axis",
            offset=offset,
        )
        return scad.solve_assembly_constraints_rassembly(
            assembly=bearing,
            strict=True,
        )

    return build()


def _build_stator_definition() -> scad.AssemblyBuildResult:
    core = build_stator_core_part()
    winding = build_slot_winding_part()

    @scad.assemble(
        id="bldc_12_slot_stator",
        definitions=(core, winding),
        cache=CACHE,
    )
    def build() -> scad.Assembly:
        stator = scad.make_assembly_rassembly(
            assembly_id="bldc_12_slot_stator",
            name="12-slot laminated stator with discrete copper slot packs",
        )
        stator = scad.add_component_rassembly(
            assembly=stator,
            item=core.value,
            component_id="stator_core",
            placement=scad.identity_placement_rplacement(),
            name="Laminated stator core",
        )
        stator = scad.ground_component_rassembly(
            assembly=stator,
            component_id="stator_core",
        )
        for index in range(MOTOR_SLOT_COUNT):
            angle = 360.0 * index / MOTOR_SLOT_COUNT
            component_id = f"winding_{index + 1:02d}"
            stator = scad.add_component_rassembly(
                assembly=stator,
                item=winding.value,
                component_id=component_id,
                placement=z_rotation_placement(
                    origin=(0.0, 0.0, 0.0),
                    angle_degrees=angle,
                ),
                name=f"Slot winding pack {index + 1}",
            )
            stator = scad.add_fixed_constraint_rassembly(
                assembly=stator,
                constraint_id=f"{component_id}_potted_to_core",
                connector_a=connector_ref(
                    component_id="stator_core",
                    connector_id=component_id,
                ),
                connector_b=connector_ref(
                    component_id=component_id,
                    connector_id="mount_axis",
                ),
                name=f"Winding {index + 1} varnish and potting retention",
            )
        stator = scad.forward_connector_rassembly(
            assembly=stator,
            connector_id="shell_axis",
            source_component_id="stator_core",
            source_connector_id="shell_axis",
            name="Stator press-fit axis",
            offset=None,
        )
        stator = scad.solve_assembly_constraints_rassembly(
            assembly=stator,
            strict=True,
        )
        ground_constraint_report(label="stator", assembly=stator)
        return stator

    return build()


def _build_rotor_definition() -> scad.AssemblyBuildResult:
    core = build_rotor_core_part()
    magnet = build_rotor_magnet_part()

    @scad.assemble(
        id="direct_coupled_bldc_rotor",
        definitions=(core, magnet),
        cache=CACHE,
    )
    def build() -> scad.Assembly:
        rotor = scad.make_assembly_rassembly(
            assembly_id="direct_coupled_bldc_rotor",
            name="14-pole BLDC rotor with integrated stage-1 sun shaft",
        )
        rotor = scad.add_component_rassembly(
            assembly=rotor,
            item=core.value,
            component_id="rotor_core_shaft_sun",
            placement=scad.identity_placement_rplacement(),
            name="Rotor back iron, shaft, and stage-1 sun",
        )
        rotor = scad.ground_component_rassembly(
            assembly=rotor,
            component_id="rotor_core_shaft_sun",
        )
        for index in range(MOTOR_POLE_COUNT):
            angle = 360.0 * index / MOTOR_POLE_COUNT
            component_id = f"magnet_{index + 1:02d}"
            rotor = scad.add_component_rassembly(
                assembly=rotor,
                item=magnet.value,
                component_id=component_id,
                placement=z_rotation_placement(
                    origin=(0.0, 0.0, 0.0),
                    angle_degrees=angle,
                ),
                name=f"Bonded rotor magnet {index + 1}",
            )
            rotor = scad.add_fixed_constraint_rassembly(
                assembly=rotor,
                constraint_id=f"{component_id}_bonded_to_rotor",
                connector_a=connector_ref(
                    component_id="rotor_core_shaft_sun",
                    connector_id=component_id,
                ),
                connector_b=connector_ref(
                    component_id=component_id,
                    connector_id="bond_axis",
                ),
                name=f"Magnet {index + 1} adhesive and sleeve retention",
            )
        for connector_id in (
            "rotor_axis",
            "rear_bearing_axis",
            "front_bearing_axis",
            "stage1_sun_axis",
        ):
            rotor = scad.forward_connector_rassembly(
                assembly=rotor,
                connector_id=connector_id,
                source_component_id="rotor_core_shaft_sun",
                source_connector_id=connector_id,
                name=connector_id.replace("_", " "),
                offset=None,
            )
        rotor = scad.solve_assembly_constraints_rassembly(
            assembly=rotor,
            strict=True,
        )
        ground_constraint_report(label="rotor", assembly=rotor)
        return rotor

    return build()


def _build_controller_definition() -> scad.AssemblyBuildResult:
    pcb = build_controller_pcb_part()
    mosfet = build_mosfet_part()
    phase_terminal = build_phase_terminal_part()
    power_terminal = build_power_can_terminal_part()

    @scad.assemble(
        id="integrated_circular_motor_controller",
        definitions=(pcb, mosfet, phase_terminal, power_terminal),
        cache=CACHE,
    )
    def build() -> scad.Assembly:
        controller = scad.make_assembly_rassembly(
            assembly_id="integrated_circular_motor_controller",
            name="44.4 mm circular integrated BLDC controller",
        )
        controller = scad.add_component_rassembly(
            assembly=controller,
            item=pcb.value,
            component_id="pcb",
            placement=scad.identity_placement_rplacement(),
            name="Circular controller PCB",
        )
        controller = scad.ground_component_rassembly(
            assembly=controller,
            component_id="pcb",
        )
        for index, angle in enumerate(MOSFET_ANGLES):
            radians = math.radians(angle)
            center = (13.2 * math.cos(radians), 13.2 * math.sin(radians))
            component_id = f"mosfet_{index + 1}"
            controller = scad.add_component_rassembly(
                assembly=controller,
                item=mosfet.value,
                component_id=component_id,
                placement=scad.make_placement_rplacement(
                    origin=(center[0], center[1], PCB_BOTTOM_Z + PCB_THICKNESS),
                ),
                name=f"Power MOSFET package {index + 1}",
            )
            controller = scad.add_fixed_constraint_rassembly(
                assembly=controller,
                constraint_id=f"{component_id}_soldered",
                connector_a=connector_ref(
                    component_id="pcb",
                    connector_id=component_id,
                ),
                connector_b=connector_ref(
                    component_id=component_id,
                    connector_id="solder_axis",
                ),
                name=f"MOSFET {index + 1} solder attachment",
            )
        for component_id, part, center, connector_id in (
            (
                "phase_terminal",
                phase_terminal,
                PHASE_TERMINAL_CENTER,
                "phase_terminal",
            ),
            (
                "power_can_terminal",
                power_terminal,
                POWER_CAN_TERMINAL_CENTER,
                "power_can_terminal",
            ),
        ):
            controller = scad.add_component_rassembly(
                assembly=controller,
                item=part.value,
                component_id=component_id,
                placement=scad.make_placement_rplacement(
                    origin=(center[0], center[1], -38.5),
                ),
                name=part.value.name,
            )
            controller = scad.add_fixed_constraint_rassembly(
                assembly=controller,
                constraint_id=f"{component_id}_soldered",
                connector_a=connector_ref(
                    component_id="pcb",
                    connector_id=connector_id,
                ),
                connector_b=connector_ref(
                    component_id=component_id,
                    connector_id="solder_axis",
                ),
                name=f"{component_id.replace('_', ' ')} solder and screw retention",
            )
        for connector_id in ("cover_axis", "phase_access", "power_can_access"):
            controller = scad.forward_connector_rassembly(
                assembly=controller,
                connector_id=connector_id,
                source_component_id="pcb",
                source_connector_id=connector_id,
                name=connector_id.replace("_", " "),
                offset=None,
            )
        controller = scad.solve_assembly_constraints_rassembly(
            assembly=controller,
            strict=True,
        )
        ground_constraint_report(label="controller", assembly=controller)
        return controller

    return build()


def _planet_placement(*, stage: StageSpec, index: int) -> scad.Placement:
    center = planet_center_xy(stage=stage, index=index)
    carrier_angle = 360.0 * index / PLANET_COUNT
    spin = carrier_angle + 180.0 - 180.0 / stage.planet_teeth
    return z_rotation_placement(
        origin=(center[0], center[1], stage.bottom_z),
        angle_degrees=spin,
    )


def build_integrated_bldc_joint_actuator() -> scad.AssemblyBuildResult:
    """Build the complete actuator as a durable nested product definition."""

    reducer_housing = build_reducer_housing_part()
    motor_shell = build_motor_shell_part()
    rear_spider = build_rear_bearing_spider_part()
    rear_cover = build_rear_electronics_cover_part()
    output_cap = build_output_bearing_cap_part()
    stator = _build_stator_definition()
    rotor = _build_rotor_definition()
    controller = _build_controller_definition()
    stage1_ring = build_stage1_fixed_ring_part()
    stage1_planet = build_stage1_reusable_planet_part()
    stage1_carrier = build_stage1_carrier_part()
    stage2_ring = build_stage2_fixed_ring_part()
    stage2_planet = build_stage2_reusable_planet_part()
    output_carrier = build_stage2_output_carrier_part()
    rear_motor_bearing = _build_bearing_definition(
        bearing_id="rear_motor_8x16x5",
        spec=REAR_MOTOR_BEARING,
    )
    front_motor_bearing = _build_bearing_definition(
        bearing_id="front_motor_8x19x6",
        spec=FRONT_MOTOR_BEARING,
    )
    interstage_bearing = _build_bearing_definition(
        bearing_id="interstage_5x10x3",
        spec=INTERSTAGE_BEARING,
    )
    planet_bearing = _build_bearing_definition(
        bearing_id="planet_3x6x3",
        spec=PLANET_BEARING,
    )
    output_bearing = _build_bearing_definition(
        bearing_id="output_16x24x5",
        spec=OUTPUT_BEARING,
    )
    definitions = (
        reducer_housing,
        motor_shell,
        rear_spider,
        rear_cover,
        output_cap,
        stator,
        rotor,
        controller,
        stage1_ring,
        stage1_planet,
        stage1_carrier,
        stage2_ring,
        stage2_planet,
        output_carrier,
        rear_motor_bearing,
        front_motor_bearing,
        interstage_bearing,
        planet_bearing,
        output_bearing,
    )

    @scad.assemble(
        id="integrated_50mm_bldc_joint_actuator",
        definitions=definitions,
        cache=CACHE,
    )
    def build() -> scad.Assembly:
        actuator = scad.make_assembly_rassembly(
            assembly_id="integrated_50mm_bldc_joint_actuator",
            name="50 mm 12-slot/14-pole BLDC joint actuator with 20:1 reducer and circular ESC",
        )
        identity = scad.identity_placement_rplacement()
        fixed_components = (
            ("reducer_housing", reducer_housing.value, identity, "Fixed reducer housing"),
            ("motor_shell", motor_shell.value, identity, "Fixed BLDC shell"),
            ("rear_bearing_spider", rear_spider.value, identity, "Rear motor-bearing spider"),
            ("rear_electronics_cover", rear_cover.value, identity, "Rear controller cover"),
            ("output_bearing_cap", output_cap.value, identity, "Output bearing cap"),
            ("stator", stator.value, identity, "12-slot fixed stator"),
            ("rotor", rotor.value, identity, "14-pole rotor and direct sun shaft"),
            ("controller", controller.value, identity, "Circular integrated controller"),
            ("stage1_carrier", stage1_carrier.value, identity, "Stage 1 carrier and stage 2 sun"),
            ("output_carrier", output_carrier.value, identity, "Stage 2 carrier and output flange"),
            (
                "stage1_ring",
                stage1_ring.value,
                scad.make_placement_rplacement(origin=(0.0, 0.0, STAGE_1.bottom_z)),
                "Stage 1 fixed ring insert",
            ),
            (
                "stage2_ring",
                stage2_ring.value,
                scad.make_placement_rplacement(origin=(0.0, 0.0, STAGE_2.bottom_z)),
                "Stage 2 fixed ring insert",
            ),
        )
        for component_id, item, placement, name in fixed_components:
            actuator = scad.add_component_rassembly(
                assembly=actuator,
                item=item,
                component_id=component_id,
                placement=placement,
                name=name,
            )
        for stage, planet in (
            (STAGE_1, stage1_planet),
            (STAGE_2, stage2_planet),
        ):
            for index in range(PLANET_COUNT):
                actuator = scad.add_component_rassembly(
                    assembly=actuator,
                    item=planet.value,
                    component_id=f"{stage.stage_id}_planet_{index + 1}",
                    placement=_planet_placement(stage=stage, index=index),
                    name=f"{stage.label} planet {index + 1}",
                )
        bearing_components = (
            (
                "rear_motor_bearing",
                rear_motor_bearing.value,
                coaxial_bearing_placement(center_z=REAR_BEARING_CENTER_Z),
                "Rear rotor bearing",
            ),
            (
                "front_motor_bearing",
                front_motor_bearing.value,
                coaxial_bearing_placement(center_z=FRONT_MOTOR_BEARING_CENTER_Z),
                "Front rotor bearing",
            ),
            (
                "interstage_bearing",
                interstage_bearing.value,
                coaxial_bearing_placement(center_z=INTERSTAGE_BEARING_CENTER_Z),
                "Stage 1 carrier support bearing",
            ),
            (
                "output_bearing_1",
                output_bearing.value,
                coaxial_bearing_placement(center_z=OUTPUT_BEARING_1_CENTER_Z),
                "Rear output bearing",
            ),
            (
                "output_bearing_2",
                output_bearing.value,
                coaxial_bearing_placement(center_z=OUTPUT_BEARING_2_CENTER_Z),
                "Front output bearing",
            ),
        )
        for component_id, item, placement, name in bearing_components:
            actuator = scad.add_component_rassembly(
                assembly=actuator,
                item=item,
                component_id=component_id,
                placement=placement,
                name=name,
            )
        for stage in (STAGE_1, STAGE_2):
            for index in range(PLANET_COUNT):
                actuator = scad.add_component_rassembly(
                    assembly=actuator,
                    item=planet_bearing.value,
                    component_id=f"{stage.stage_id}_planet_bearing_{index + 1}",
                    placement=planet_bearing_placement(stage=stage, index=index),
                    name=f"{stage.label} planet bearing {index + 1}",
                )
        actuator = _add_public_connectors_rassembly(assembly=actuator)
        actuator = _add_constraints_rassembly(assembly=actuator)
        actuator = scad.solve_assembly_constraints_rassembly(
            assembly=actuator,
            strict=True,
        )
        ground_constraint_report(label="actuator", assembly=actuator)
        print(
            f"durable_actuator: components={len(actuator.component_ids())} "
            f"definitions={len(definitions)} reduction={TOTAL_REDUCTION:.1f}"
        )
        return actuator

    return build()
