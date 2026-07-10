"""Reusable actuator module for the leg-wheel example."""

from __future__ import annotations

import sys
from pathlib import Path

import simplecadapi as scad

from leg_common import add_datum_connector_rpart, connector_ref
from leg_dimensions import MOTOR_CAN_HEIGHT, MOTOR_CAN_INPUT_FACE_CLEARANCE, MOTOR_CAN_RADIUS


EXAMPLE16_DIR = Path(__file__).resolve().parents[1] / "16_compact_two_stage_planetary_reducer"
if str(EXAMPLE16_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE16_DIR))

from assembly import make_two_stage_planetary_reducer_rassembly  # noqa: E402


def make_motor_can_rpart(*, material: scad.Material) -> scad.Part:
    """Create the exportable cylindrical motor shell fixed to a reducer input."""

    can = scad.make_cylinder_rsolid(
        radius=MOTOR_CAN_RADIUS,
        height=MOTOR_CAN_HEIGHT,
        bottom_face_center=(0.0, 0.0, -MOTOR_CAN_HEIGHT - MOTOR_CAN_INPUT_FACE_CLEARANCE),
        axis=(0.0, 0.0, 1.0),
    )
    can = scad.apply_tag(shape=can, tag="role.motor_can")
    part = scad.make_part_rpart(
        part_id="leg_motor_can",
        body=can,
        name="25 mm radius cylindrical motor can",
    )
    part = scad.assign_material_rpart(part=part, material=material)
    part = add_datum_connector_rpart(
        part=part,
        connector_id="front_axis",
        origin=(0.0, 0.0, 0.0),
        axis="z",
        name="Reducer-facing motor can datum",
    )
    part = add_datum_connector_rpart(
        part=part,
        connector_id="rear_axis",
        origin=(0.0, 0.0, -MOTOR_CAN_HEIGHT - MOTOR_CAN_INPUT_FACE_CLEARANCE),
        axis="z",
        name="Rear motor datum",
    )
    print(
        f"motor_can: radius={MOTOR_CAN_RADIUS:.1f} height={MOTOR_CAN_HEIGHT:.1f} "
        f"connectors={len(part.connectors)} volume={can.get_volume():.3f}"
    )
    return part


def make_joint_actuator_rassembly(*, motor_material: scad.Material) -> scad.Assembly:
    """Build one reducer plus motor-can actuator module for reuse by the leg."""

    reducer = make_two_stage_planetary_reducer_rassembly()
    motor_can = make_motor_can_rpart(material=motor_material)
    actuator = scad.make_assembly_rassembly(
        assembly_id="leg_joint_actuator_module",
        name="Reducer actuator with 25 mm radius input motor can",
    )
    actuator = scad.add_component_rassembly(
        assembly=actuator,
        item=reducer,
        component_id="reducer",
        placement=scad.identity_placement_rplacement(),
        name="20:1 compact reducer core",
    )
    actuator = scad.add_component_rassembly(
        assembly=actuator,
        item=motor_can,
        component_id="motor_can",
        placement=scad.identity_placement_rplacement(),
        name="Input-side motor can",
    )
    actuator = scad.ground_component_rassembly(assembly=actuator, component_id="reducer")
    actuator = scad.add_fixed_constraint_rassembly(
        assembly=actuator,
        constraint_id="motor_can_to_reducer_input",
        connector_a=connector_ref(component_id="reducer", connector_id="input_motor_axis"),
        connector_b=connector_ref(component_id="motor_can", connector_id="front_axis"),
        name="Motor can fixed to reducer input flange",
    )
    actuator = scad.solve_assembly_constraints_rassembly(assembly=actuator, strict=True)
    for connector_id, source_component_id, source_connector_id, name in (
        ("case_axis", "reducer", "housing_mount_axis", "Fixed housing case datum"),
        ("output_axis", "reducer", "output_link_axis", "Actuator output link datum"),
        ("input_axis", "motor_can", "rear_axis", "Motor rear service datum"),
    ):
        actuator = scad.forward_connector_rassembly(
            assembly=actuator,
            connector_id=connector_id,
            source_component_id=source_component_id,
            source_connector_id=source_connector_id,
            name=name,
        )
    print("joint_actuator_module: connectors=" + ",".join(actuator.connector_ids()))
    return actuator
