"""Circular integrated controller PCB, power stages, and rear terminals."""

from __future__ import annotations

import math

import simplecadapi as scad

from common import (
    apply_tags,
    connector_ref,
    ground_constraint_report,
    make_axial_hole_cutters_rsolids,
    make_axis_part_rpart,
    radial_centers,
)
from dimensions import (
    PCB_BOTTOM_Z,
    PCB_CENTER_BORE_RADIUS,
    PCB_MOUNT_HOLE_RADIUS,
    PCB_RADIUS,
    PCB_STANDOFF_PCD,
    PCB_THICKNESS,
    REAR_COLUMN_PCD,
)


PHASE_TERMINAL_CENTER = (-11.0, 0.0)
POWER_CAN_TERMINAL_CENTER = (11.0, 0.0)
MOSFET_ANGLES = (22.5, 67.5, 112.5, 202.5, 247.5, 292.5)


def make_integrated_controller_rassembly(
    *,
    pcb_material: scad.Material,
    terminal_material: scad.Material,
) -> scad.Assembly:
    """Build the circular ESC with six power devices and two service terminals."""

    pcb = _make_controller_pcb_rpart(material=pcb_material)
    mosfet = _make_mosfet_package_rpart(material=terminal_material)
    phase_terminal = _make_terminal_block_rpart(
        part_id="three_phase_terminal",
        name="Three-position motor phase terminal",
        width=8.0,
        pin_count=3,
        material=terminal_material,
    )
    power_terminal = _make_terminal_block_rpart(
        part_id="power_can_terminal",
        name="Four-position DC power and CAN terminal",
        width=8.0,
        pin_count=4,
        material=terminal_material,
    )
    controller = scad.make_assembly_rassembly(
        assembly_id="integrated_circular_motor_controller",
        name="44.4 mm circular integrated BLDC controller",
    )
    controller = scad.add_component_rassembly(
        assembly=controller,
        item=pcb,
        component_id="pcb",
        placement=scad.identity_placement_rplacement(),
        name="Circular controller PCB",
    )
    controller = scad.ground_component_rassembly(assembly=controller, component_id="pcb")

    for index, angle in enumerate(MOSFET_ANGLES):
        radians = math.radians(angle)
        center = (13.2 * math.cos(radians), 13.2 * math.sin(radians))
        component_id = f"mosfet_{index + 1}"
        z = PCB_BOTTOM_Z + PCB_THICKNESS
        controller = scad.add_component_rassembly(
            assembly=controller,
            item=mosfet,
            component_id=component_id,
            placement=scad.make_placement_rplacement(origin=(center[0], center[1], z)),
            name=f"Power MOSFET package {index + 1}",
        )
        controller = scad.add_fixed_constraint_rassembly(
            assembly=controller,
            constraint_id=f"{component_id}_soldered",
            connector_a=connector_ref(component_id="pcb", connector_id=component_id),
            connector_b=connector_ref(component_id=component_id, connector_id="solder_axis"),
            name=f"MOSFET {index + 1} solder attachment",
        )

    for component_id, item, center, connector_id in (
        ("phase_terminal", phase_terminal, PHASE_TERMINAL_CENTER, "phase_terminal"),
        ("power_can_terminal", power_terminal, POWER_CAN_TERMINAL_CENTER, "power_can_terminal"),
    ):
        controller = scad.add_component_rassembly(
            assembly=controller,
            item=item,
            component_id=component_id,
            placement=scad.make_placement_rplacement(origin=(center[0], center[1], -38.5)),
            name=item.name,
        )
        controller = scad.add_fixed_constraint_rassembly(
            assembly=controller,
            constraint_id=f"{component_id}_soldered",
            connector_a=connector_ref(component_id="pcb", connector_id=connector_id),
            connector_b=connector_ref(component_id=component_id, connector_id="solder_axis"),
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
    controller = scad.solve_assembly_constraints_rassembly(assembly=controller, strict=True)
    ground_constraint_report(label="controller", assembly=controller)
    print("controller_packaging: pcb_d=44.4 mosfets=6 phase_pins=3 power_can_pins=4")
    return controller


def _make_controller_pcb_rpart(*, material: scad.Material) -> scad.Part:
    board = scad.make_cylinder_rsolid(
        radius=PCB_RADIUS,
        height=PCB_THICKNESS,
        bottom_face_center=(0.0, 0.0, PCB_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    cutters: list[scad.Solid] = [
        scad.make_cylinder_rsolid(
            radius=PCB_CENTER_BORE_RADIUS,
            height=PCB_THICKNESS + 2.0,
            bottom_face_center=(0.0, 0.0, PCB_BOTTOM_Z - 1.0),
            axis=(0.0, 0.0, 1.0),
        )
    ]
    cutters.extend(
        make_axial_hole_cutters_rsolids(
            count=4,
            pcd=PCB_STANDOFF_PCD,
            hole_radius=PCB_MOUNT_HOLE_RADIUS,
            bottom_z=PCB_BOTTOM_Z - 1.0,
            height=PCB_THICKNESS + 2.0,
            angle_offset=45.0,
        )
    )
    cutters.extend(
        make_axial_hole_cutters_rsolids(
            count=4,
            pcd=REAR_COLUMN_PCD,
            hole_radius=3.45,
            bottom_z=PCB_BOTTOM_Z - 1.0,
            height=PCB_THICKNESS + 2.0,
        )
    )
    for x, count in ((PHASE_TERMINAL_CENTER[0], 3), (POWER_CAN_TERMINAL_CENTER[0], 4)):
        for pin in range(count):
            y = (pin - (count - 1) / 2.0) * 1.8
            cutters.append(
                scad.make_cylinder_rsolid(
                    radius=0.65,
                    height=PCB_THICKNESS + 2.0,
                    bottom_face_center=(x, y, PCB_BOTTOM_Z - 1.0),
                    axis=(0.0, 0.0, 1.0),
                )
            )
    board = scad.cut_rsolid(board, cutters, skip_non_intersecting=False)
    board = apply_tags(
        shape=board,
        tags=("role.circular_esc_pcb", "role.controller_mounting_holes", "group.integrated_electronics"),
    )
    connectors = [
        ("cover_axis", (0.0, 0.0, PCB_BOTTOM_Z + PCB_THICKNESS / 2.0), "Rear-cover PCB plane"),
        ("phase_terminal", (*PHASE_TERMINAL_CENTER, PCB_BOTTOM_Z), "Phase terminal solder datum"),
        ("power_can_terminal", (*POWER_CAN_TERMINAL_CENTER, PCB_BOTTOM_Z), "Power/CAN terminal solder datum"),
        ("phase_access", (*PHASE_TERMINAL_CENTER, -37.0), "Phase terminal service axis"),
        ("power_can_access", (*POWER_CAN_TERMINAL_CENTER, -37.0), "Power/CAN service axis"),
    ]
    for index, angle in enumerate(MOSFET_ANGLES):
        radians = math.radians(angle)
        center = (13.2 * math.cos(radians), 13.2 * math.sin(radians))
        connectors.append(
            (
                f"mosfet_{index + 1}",
                (center[0], center[1], PCB_BOTTOM_Z + PCB_THICKNESS),
                f"MOSFET {index + 1} solder datum",
            )
        )
    print("pcb_holes: center=10.0 mount=4 column_notches=4 terminal_pins=7")
    return make_axis_part_rpart(
        part_id="circular_controller_pcb",
        body=board,
        name="44.4 mm circular ESC PCB with service cutouts",
        material=material,
        connectors=connectors,
    )


def _make_mosfet_package_rpart(*, material: scad.Material) -> scad.Part:
    package = scad.make_box_rsolid(
        width=4.0,
        height=3.0,
        depth=1.4,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    package = apply_tags(shape=package, tags=("role.power_mosfet", "group.three_phase_bridge"))
    return make_axis_part_rpart(
        part_id="reusable_power_mosfet",
        body=package,
        name="Reusable power MOSFET package",
        material=material,
        connectors=(("solder_axis", (0.0, 0.0, 0.0), "PCB solder plane"),),
    )


def _make_terminal_block_rpart(
    *,
    part_id: str,
    name: str,
    width: float,
    pin_count: int,
    material: scad.Material,
) -> scad.Part:
    body = scad.make_box_rsolid(
        width=width,
        height=6.0,
        depth=4.9,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    access_cutters = []
    for pin in range(pin_count):
        y = (pin - (pin_count - 1) / 2.0) * 1.8
        access_cutters.append(
            scad.make_cylinder_rsolid(
                radius=0.75,
                height=width + 2.0,
                bottom_face_center=(-width / 2.0 - 1.0, y, 2.45),
                axis=(1.0, 0.0, 0.0),
            )
        )
    body = scad.cut_rsolid(body, access_cutters, skip_non_intersecting=False)
    body = apply_tags(shape=body, tags=("role.rear_wiring_terminal", "role.service_access"))
    print(f"terminal_{part_id}: pins={pin_count} access_holes={pin_count} width={width:.1f}")
    return make_axis_part_rpart(
        part_id=part_id,
        body=body,
        name=name,
        material=material,
        connectors=(("solder_axis", (0.0, 0.0, 4.9), "PCB solder and screw datum"),),
    )
