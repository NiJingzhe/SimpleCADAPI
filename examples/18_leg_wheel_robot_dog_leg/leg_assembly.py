"""Top-level bolt-aligned leg-wheel robot dog leg assembly."""

from __future__ import annotations

import simplecadapi as scad

from actuator import make_joint_actuator_rassembly
from brackets import make_body_mount_plate_rpart
from hardware import (
    make_clamp_bolt_stack_rpart,
    make_knee_bushing_rpart,
    make_knee_shoulder_bolt_stack_rpart,
    make_linkage_pin_stack_rpart,
    make_socket_head_screw_rpart,
)
from leg_common import connector_ref, make_actuator_target_rplacement
from leg_dimensions import (
    ACTUATOR_OUTPUT_CONNECTOR_Z,
    DISTAL_PUSHROD_PIN,
    KNEE_DRIVE_AXIS,
    PROXIMAL_PUSHROD_PIN,
    OUTPUT_FLANGE_SCREW_SHANK_RADIUS,
    ROD_PIN_AXIS_Z,
    ROOT_AXIS,
    WHEEL_AXIS,
)
from links import (
    make_proximal_crank_rpart,
    make_pushrod_rpart,
    make_shank_link_rpart,
    make_upper_link_plate_rpart,
    make_wheel_hub_rpart,
    make_wheel_tire_rpart,
)


def make_leg_wheel_robot_dog_leg_rassembly(
    *,
    actuator_materials: dict[str, scad.Material],
    leg_materials: dict[str, scad.Material],
) -> scad.Assembly:
    """Build the posed planar leg-wheel assembly with explicit bolt interfaces."""

    actuator = make_joint_actuator_rassembly(materials=actuator_materials)
    body_mount = make_body_mount_plate_rpart(material=leg_materials["bracket"])
    upper_link = make_upper_link_plate_rpart(material=leg_materials["link"])
    proximal_crank = make_proximal_crank_rpart(material=leg_materials["linkage"])
    pushrod = make_pushrod_rpart(material=leg_materials["linkage"])
    shank_link = make_shank_link_rpart(material=leg_materials["link"])
    wheel_hub = make_wheel_hub_rpart(material=leg_materials["wheel_hub"])
    wheel_tire = make_wheel_tire_rpart(material=leg_materials["tire"])
    output_screw = make_socket_head_screw_rpart(
        part_id="m3x5_output_socket_head_screw",
        shank_radius=OUTPUT_FLANGE_SCREW_SHANK_RADIUS,
        shank_length=5.0,
        head_radius=2.85,
        head_height=3.0,
        material=leg_materials["fastener"],
    )
    clamp_bolt = make_clamp_bolt_stack_rpart(material=leg_materials["fastener"])
    linkage_pin = make_linkage_pin_stack_rpart(material=leg_materials["fastener"])
    knee_bushing = make_knee_bushing_rpart(material=leg_materials["bushing"])
    knee_axle = make_knee_shoulder_bolt_stack_rpart(material=leg_materials["fastener"])

    leg = scad.make_assembly_rassembly(
        assembly_id="leg_wheel_robot_dog_leg",
        name="Planar leg-wheel module with bolt-aligned actuator, knee, and wheel interfaces",
    )
    for component_id, target, axis, name in (
        ("thigh_actuator", ROOT_AXIS, "z", "Body-fixed thigh reducer actuator"),
        ("knee_drive_actuator", KNEE_DRIVE_AXIS, "z", "Body-fixed knee-drive actuator opposite the crank"),
        ("wheel_hub_actuator", WHEEL_AXIS, "z", "Distal wheel hub reducer actuator"),
    ):
        leg = scad.add_component_rassembly(
            assembly=leg,
            item=actuator,
            component_id=component_id,
            placement=make_actuator_target_rplacement(
                output_axis_origin=target,
                output_axis_local_z=ACTUATOR_OUTPUT_CONNECTOR_Z,
                axis=axis,
            ),
            name=name,
        )

    for component_id, item, name in (
        ("body_mount_plate", body_mount, "Body-fixed hip stack bracket for thigh and knee-drive cases"),
        ("upper_link_plate", upper_link, "Output-bolted upper link plate"),
        ("proximal_output_crank", proximal_crank, "Output-bolted knee-drive crank"),
        ("knee_pushrod", pushrod, "Pinned pushrod between crank and shank"),
        ("shank_link", shank_link, "Lower shank with integral pushrod ear and wheel hub case mount"),
        ("wheel_hub", wheel_hub, "Rigid wheel hub bolted to actuator output"),
        ("wheel_tire", wheel_tire, "Replaceable rubber tire fitted to rigid wheel hub"),
        ("knee_bushing", knee_bushing, "Bronze knee pivot sleeve"),
        ("knee_axle", knee_axle, "Retained knee shoulder axle"),
    ):
        leg = scad.add_component_rassembly(
            assembly=leg,
            item=item,
            component_id=component_id,
            placement=scad.identity_placement_rplacement(),
            name=name,
        )

    for component_id, item, placement, name in (
        (
            "thigh_clamp_bolt",
            clamp_bolt,
            scad.identity_placement_rplacement(),
            "M4 thigh actuator split-clamp bolt",
        ),
        (
            "knee_drive_clamp_bolt",
            clamp_bolt,
            scad.identity_placement_rplacement(),
            "M4 knee-drive actuator split-clamp bolt",
        ),
        (
            "wheel_clamp_bolt",
            clamp_bolt,
            scad.identity_placement_rplacement(),
            "M4 wheel actuator split-clamp bolt",
        ),
        (
            "proximal_linkage_pin",
            linkage_pin,
            scad.make_placement_rplacement(
                origin=(PROXIMAL_PUSHROD_PIN[0], PROXIMAL_PUSHROD_PIN[1], ROD_PIN_AXIS_Z)
            ),
            "Retained proximal linkage shoulder pin",
        ),
        (
            "distal_linkage_pin",
            linkage_pin,
            scad.make_placement_rplacement(
                origin=(DISTAL_PUSHROD_PIN[0], DISTAL_PUSHROD_PIN[1], ROD_PIN_AXIS_Z)
            ),
            "Retained distal linkage shoulder pin",
        ),
    ):
        leg = scad.add_component_rassembly(
            assembly=leg,
            item=item,
            component_id=component_id,
            placement=placement,
            name=name,
        )

    for interface, plate_component in (
        ("thigh", "upper_link_plate"),
        ("knee_drive", "proximal_output_crank"),
        ("wheel", "wheel_hub"),
    ):
        for index in range(1, 7):
            leg = scad.add_component_rassembly(
                assembly=leg,
                item=output_screw,
                component_id=f"{interface}_output_screw_{index}",
                placement=scad.identity_placement_rplacement(),
                name=f"{interface.replace('_', ' ')} output M3 screw {index}",
            )

    leg = _add_leg_constraints_rassembly(assembly=leg)
    leg = scad.solve_assembly_constraints_rassembly(assembly=leg, strict=True)
    _ground_constraint_report(assembly=leg)
    print(
        "leg_components: actuators=3 structural=7 hardware=25 components="
        f"{len(leg.component_ids())} constraints={len(leg.constraint_ids())}"
    )
    return leg


def _add_leg_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="body_mount_plate")

    fixed_pairs = (
        ("hip_stack_to_thigh_case", "body_mount_plate", "case_axis", "thigh_actuator", "case_clamp_axis"),
        ("hip_stack_to_knee_drive_case", "body_mount_plate", "knee_drive_case_axis", "knee_drive_actuator", "case_clamp_axis"),
        ("shank_clamped_to_wheel_case", "shank_link", "wheel_case_axis", "wheel_hub_actuator", "case_clamp_axis"),
        ("thigh_output_bolted_to_link", "thigh_actuator", "output_link_axis", "upper_link_plate", "output_axis"),
        ("knee_output_bolted_to_crank", "knee_drive_actuator", "output_link_axis", "proximal_output_crank", "output_axis"),
        ("wheel_output_bolted_to_hub", "wheel_hub_actuator", "output_link_axis", "wheel_hub", "wheel_axis"),
        ("wheel_tire_bonded_to_hub", "wheel_hub", "tire_axis", "wheel_tire", "hub_axis"),
        ("knee_bushing_pressed_in_upper_link", "upper_link_plate", "knee_axis", "knee_bushing", "knee_axis"),
        ("knee_axle_locked_to_bushing", "knee_bushing", "knee_axis", "knee_axle", "knee_axis"),
        ("thigh_clamp_bolt_seated", "body_mount_plate", "thigh_clamp_bolt_seat", "thigh_clamp_bolt", "seat_axis"),
        ("knee_clamp_bolt_seated", "body_mount_plate", "knee_clamp_bolt_seat", "knee_drive_clamp_bolt", "seat_axis"),
        ("wheel_clamp_bolt_seated", "shank_link", "wheel_clamp_bolt_seat", "wheel_clamp_bolt", "seat_axis"),
        ("proximal_pin_locked_to_crank", "proximal_output_crank", "rod_pin", "proximal_linkage_pin", "pin_axis"),
        ("distal_pin_locked_to_shank", "shank_link", "rod_pin", "distal_linkage_pin", "pin_axis"),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector in fixed_pairs:
        assembly = scad.add_fixed_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=connector_ref(component_id=a_component, connector_id=a_connector),
            connector_b=connector_ref(component_id=b_component, connector_id=b_connector),
            name=constraint_id.replace("_", " "),
        )

    revolutes = (
        ("proximal_pushrod_on_shoulder_pin", "proximal_linkage_pin", "pin_axis", "knee_pushrod", "proximal_pin", None),
        ("distal_pushrod_on_shoulder_pin", "distal_linkage_pin", "pin_axis", "knee_pushrod", "distal_pin", None),
        ("shank_rotates_on_knee_bushing", "knee_bushing", "knee_axis", "shank_link", "knee_axis", None),
    )
    for constraint_id, a_component, a_connector, b_component, b_connector, drive_angle in revolutes:
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id=constraint_id,
            connector_a=connector_ref(component_id=a_component, connector_id=a_connector),
            connector_b=connector_ref(component_id=b_component, connector_id=b_connector),
            drive_angle_degrees=drive_angle,
            angle_limit=None,
            name=constraint_id.replace("_", " "),
        )

    for interface, plate_component in (
        ("thigh", "upper_link_plate"),
        ("knee_drive", "proximal_output_crank"),
        ("wheel", "wheel_hub"),
    ):
        for index in range(1, 7):
            assembly = scad.add_fixed_constraint_rassembly(
                assembly=assembly,
                constraint_id=f"{interface}_output_screw_{index}_seated",
                connector_a=connector_ref(
                    component_id=plate_component,
                    connector_id=f"output_bolt_{index}_head_top",
                ),
                connector_b=connector_ref(
                    component_id=f"{interface}_output_screw_{index}",
                    connector_id="head_top_axis",
                ),
                name=f"{interface.replace('_', ' ')} output screw {index} coaxial",
            )

    print(
        f"leg_constraints_added: fixed={len(fixed_pairs) + 18} "
        f"revolute={len(revolutes)} actuator_output_mounts=fixed bolt_aligned=21"
    )
    return assembly


def _ground_constraint_report(*, assembly: scad.Assembly) -> None:
    report = scad.inspect_assembly_constraints_rconstraintreport(assembly=assembly)
    print(
        f"leg_constraints: solved={report.solved} grounded={len(report.grounded_component_ids)} "
        f"solved_components={len(report.solved_component_ids)} unsolved={len(report.unsolved_component_ids)}"
    )
    for residual in report.residuals:
        print(
            f"leg_constraint_{residual.constraint_id}: translation={residual.translation_error:.6g} "
            f"angle={residual.angular_error_degrees:.6g} ok={residual.within_tolerance}"
        )
