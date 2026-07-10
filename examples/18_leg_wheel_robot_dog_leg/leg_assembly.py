"""Top-level bolt-aligned leg-wheel robot dog leg assembly."""

from __future__ import annotations

import simplecadapi as scad

from actuator import make_joint_actuator_rassembly
from brackets import make_body_mount_plate_rpart
from leg_common import connector_ref, make_actuator_target_rplacement
from leg_dimensions import ACTUATOR_OUTPUT_CONNECTOR_Z, KNEE_DRIVE_AXIS, ROOT_AXIS, WHEEL_AXIS
from leg_materials import make_leg_materials_rdict
from links import (
    make_proximal_crank_rpart,
    make_pushrod_rpart,
    make_shank_link_rpart,
    make_upper_link_plate_rpart,
    make_wheel_tire_rpart,
)


def make_leg_wheel_robot_dog_leg_rassembly() -> scad.Assembly:
    """Build the posed planar leg-wheel assembly with explicit bolt interfaces."""

    materials = make_leg_materials_rdict()
    actuator = make_joint_actuator_rassembly(motor_material=materials["motor"])
    body_mount = make_body_mount_plate_rpart(material=materials["bracket"])
    upper_link = make_upper_link_plate_rpart(material=materials["link"])
    proximal_crank = make_proximal_crank_rpart(material=materials["linkage"])
    pushrod = make_pushrod_rpart(material=materials["linkage"])
    shank_link = make_shank_link_rpart(material=materials["link"])
    wheel_tire = make_wheel_tire_rpart(material=materials["tire"])

    leg = scad.make_assembly_rassembly(
        assembly_id="leg_wheel_robot_dog_leg",
        name="Planar leg-wheel module with bolt-aligned actuator, knee, and wheel interfaces",
    )
    for component_id, target, axis, name in (
        ("thigh_actuator", ROOT_AXIS, "z", "Body-fixed thigh reducer actuator"),
        ("knee_drive_actuator", KNEE_DRIVE_AXIS, "z", "Body-fixed coaxial knee-drive reducer actuator"),
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
        ("wheel_tire", wheel_tire, "Spoked wheel bolted to wheel hub output"),
    ):
        leg = scad.add_component_rassembly(
            assembly=leg,
            item=item,
            component_id=component_id,
            placement=scad.identity_placement_rplacement(),
            name=name,
        )

    leg = _add_leg_constraints_rassembly(assembly=leg)
    leg = scad.solve_assembly_constraints_rassembly(assembly=leg, strict=True)
    _ground_constraint_report(assembly=leg)
    print(
        "leg_components: actuators=3 plates=6 components="
        f"{len(leg.component_ids())} constraints={len(leg.constraint_ids())}"
    )
    return leg


def _add_leg_constraints_rassembly(*, assembly: scad.Assembly) -> scad.Assembly:
    assembly = scad.ground_component_rassembly(assembly=assembly, component_id="body_mount_plate")

    fixed_pairs = (
        ("hip_stack_to_thigh_case", "body_mount_plate", "case_axis", "thigh_actuator", "case_axis"),
        ("hip_stack_to_knee_drive_case", "body_mount_plate", "knee_drive_case_axis", "knee_drive_actuator", "case_axis"),
        ("shank_bolted_to_wheel_case", "shank_link", "wheel_case_axis", "wheel_hub_actuator", "case_axis"),
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
        ("thigh_output_drive_joint", "thigh_actuator", "output_axis", "upper_link_plate", "output_axis", 0.0),
        ("knee_drive_output_joint", "knee_drive_actuator", "output_axis", "proximal_output_crank", "output_axis", 0.0),
        ("proximal_crank_pin_to_pushrod", "proximal_output_crank", "rod_pin", "knee_pushrod", "proximal_pin", None),
        ("pushrod_pin_to_shank_integral_ear", "knee_pushrod", "distal_pin", "shank_link", "rod_pin", None),
        ("upper_plate_to_shank_knee", "upper_link_plate", "knee_axis", "shank_link", "knee_axis", None),
        ("wheel_hub_output_to_tire", "wheel_hub_actuator", "output_axis", "wheel_tire", "wheel_axis", None),
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

    print(f"leg_constraints_added: fixed={len(fixed_pairs)} revolute={len(revolutes)}")
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
