"""Top-level integrated BLDC motor, controller, reducer, and housing assembly."""

from __future__ import annotations

import simplecadapi as scad

try:
    from .bearings import (
        make_coaxial_bearing_rplacement,
        make_main_bearing_rassembly,
        make_planet_bearing_rplacement,
        make_standard_planet_bearing_rassembly,
    )
    from .common import connector_ref, ground_constraint_report
    from .dimensions import (
        FRONT_MOTOR_BEARING,
        FRONT_MOTOR_BEARING_CENTER_Z,
        INTERSTAGE_BEARING,
        INTERSTAGE_BEARING_CENTER_Z,
        OUTPUT_BEARING,
        OUTPUT_BEARING_1_CENTER_Z,
        OUTPUT_BEARING_2_CENTER_Z,
        PLANET_BEARING,
        PLANET_COUNT,
        REAR_BEARING_CENTER_Z,
        REAR_MOTOR_BEARING,
        STAGE_1,
        STAGE_2,
        TOTAL_REDUCTION,
        StageSpec,
    )
    from .electronics import make_integrated_controller_rassembly
    from .gears import (
        make_output_carrier_flange_rpart,
        make_planet_rplacement,
        make_stage1_carrier_sun_rpart,
        make_stage_planet_gear_rpart,
        make_stage_ring_gear_rpart,
    )
    from .housing import (
        make_motor_shell_rpart,
        make_output_bearing_cap_rpart,
        make_rear_bearing_spider_rpart,
        make_rear_electronics_cover_rpart,
        make_reducer_housing_rpart,
    )
    from .motor import make_bldc_rotor_rassembly, make_bldc_stator_rassembly
except ImportError:  # Support direct execution from this example directory.
    from bearings import (
        make_coaxial_bearing_rplacement,
        make_main_bearing_rassembly,
        make_planet_bearing_rplacement,
        make_standard_planet_bearing_rassembly,
    )
    from common import connector_ref, ground_constraint_report
    from dimensions import (
        FRONT_MOTOR_BEARING,
        FRONT_MOTOR_BEARING_CENTER_Z,
        INTERSTAGE_BEARING,
        INTERSTAGE_BEARING_CENTER_Z,
        OUTPUT_BEARING,
        OUTPUT_BEARING_1_CENTER_Z,
        OUTPUT_BEARING_2_CENTER_Z,
        PLANET_BEARING,
        PLANET_COUNT,
        REAR_BEARING_CENTER_Z,
        REAR_MOTOR_BEARING,
        STAGE_1,
        STAGE_2,
        TOTAL_REDUCTION,
        StageSpec,
    )
    from electronics import make_integrated_controller_rassembly
    from gears import (
        make_output_carrier_flange_rpart,
        make_planet_rplacement,
        make_stage1_carrier_sun_rpart,
        make_stage_planet_gear_rpart,
        make_stage_ring_gear_rpart,
    )
    from housing import (
        make_motor_shell_rpart,
        make_output_bearing_cap_rpart,
        make_rear_bearing_spider_rpart,
        make_rear_electronics_cover_rpart,
        make_reducer_housing_rpart,
    )
    from motor import make_bldc_rotor_rassembly, make_bldc_stator_rassembly


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
