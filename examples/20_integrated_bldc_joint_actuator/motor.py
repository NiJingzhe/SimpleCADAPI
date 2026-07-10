"""True 12-slot/14-pole BLDC stator and direct-drive rotor assemblies."""

from __future__ import annotations

import simplecadapi as scad

try:
    from .common import (
        apply_tags,
        connector_ref,
        ground_constraint_report,
        make_annulus_rsolid,
        make_axis_part_rpart,
        make_z_rotation_rplacement,
        radial_centers,
    )
    from .dimensions import (
        ADDENDUM_FACTOR,
        BACKLASH,
        CLEARANCE_FACTOR,
        GEAR_HEIGHT,
        HELIX_ANGLE,
        MOTOR_MAGNET_OUTER_RADIUS,
        MOTOR_MAGNET_TANGENTIAL_WIDTH,
        MOTOR_POLE_COUNT,
        MOTOR_ROTOR_BACKIRON_RADIUS,
        MOTOR_ROTOR_BOTTOM_Z,
        MOTOR_ROTOR_TOP_Z,
        MOTOR_SHAFT_RADIUS,
        MOTOR_SHELL_INNER_RADIUS,
        MOTOR_SLOT_COUNT,
        MOTOR_STATOR_BOTTOM_Z,
        MOTOR_STATOR_OUTER_RADIUS,
        MOTOR_STATOR_TOOTH_INNER_RADIUS,
        MOTOR_STATOR_TOOTH_WIDTH,
        MOTOR_STATOR_TOP_Z,
        MOTOR_STATOR_YOKE_INNER_RADIUS,
        PRESSURE_ANGLE,
        REAR_BEARING_CENTER_Z,
        STAGE_1,
    )
except ImportError:  # Support direct execution from this example directory.
    from common import (
        apply_tags,
        connector_ref,
        ground_constraint_report,
        make_annulus_rsolid,
        make_axis_part_rpart,
        make_z_rotation_rplacement,
        radial_centers,
    )
    from dimensions import (
    ADDENDUM_FACTOR,
    BACKLASH,
    CLEARANCE_FACTOR,
    GEAR_HEIGHT,
    HELIX_ANGLE,
    MOTOR_MAGNET_OUTER_RADIUS,
    MOTOR_MAGNET_TANGENTIAL_WIDTH,
    MOTOR_POLE_COUNT,
    MOTOR_ROTOR_BACKIRON_RADIUS,
    MOTOR_ROTOR_BOTTOM_Z,
    MOTOR_ROTOR_TOP_Z,
    MOTOR_SHAFT_RADIUS,
    MOTOR_SHELL_INNER_RADIUS,
    MOTOR_SLOT_COUNT,
    MOTOR_STATOR_BOTTOM_Z,
    MOTOR_STATOR_OUTER_RADIUS,
    MOTOR_STATOR_TOOTH_INNER_RADIUS,
    MOTOR_STATOR_TOOTH_WIDTH,
    MOTOR_STATOR_TOP_Z,
    MOTOR_STATOR_YOKE_INNER_RADIUS,
    PRESSURE_ANGLE,
    REAR_BEARING_CENTER_Z,
    STAGE_1,
    )


def make_bldc_stator_rassembly(
    *,
    steel_material: scad.Material,
    copper_material: scad.Material,
) -> scad.Assembly:
    """Build a laminated 12-slot stator and twelve fixed winding packs."""

    core = _make_stator_core_rpart(material=steel_material)
    winding = _make_winding_pack_rpart(material=copper_material)
    stator = scad.make_assembly_rassembly(
        assembly_id="bldc_12_slot_stator",
        name="12-slot laminated stator with discrete copper slot packs",
    )
    stator = scad.add_component_rassembly(
        assembly=stator,
        item=core,
        component_id="stator_core",
        placement=scad.identity_placement_rplacement(),
        name="Laminated stator core",
    )
    stator = scad.ground_component_rassembly(assembly=stator, component_id="stator_core")
    for index, angle, _center in radial_centers(
        count=MOTOR_SLOT_COUNT,
        radius=0.0,
        angle_offset=0.0,
    ):
        component_id = f"winding_{index + 1:02d}"
        stator = scad.add_component_rassembly(
            assembly=stator,
            item=winding,
            component_id=component_id,
            placement=make_z_rotation_rplacement(origin=(0.0, 0.0, 0.0), angle_degrees=angle),
            name=f"Slot winding pack {index + 1}",
        )
        stator = scad.add_fixed_constraint_rassembly(
            assembly=stator,
            constraint_id=f"{component_id}_potted_to_core",
            connector_a=connector_ref(component_id="stator_core", connector_id=component_id),
            connector_b=connector_ref(component_id=component_id, connector_id="mount_axis"),
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
    stator = scad.solve_assembly_constraints_rassembly(assembly=stator, strict=True)
    ground_constraint_report(label="stator", assembly=stator)
    return stator


def make_bldc_rotor_rassembly(
    *,
    steel_material: scad.Material,
    magnet_material: scad.Material,
) -> scad.Assembly:
    """Build the rotor, bonded magnets, shaft, and integrated stage-1 sun."""

    core = _make_rotor_shaft_sun_rpart(material=steel_material)
    magnet = _make_rotor_magnet_rpart(material=magnet_material)
    rotor = scad.make_assembly_rassembly(
        assembly_id="direct_coupled_bldc_rotor",
        name="14-pole BLDC rotor with integrated stage-1 sun shaft",
    )
    rotor = scad.add_component_rassembly(
        assembly=rotor,
        item=core,
        component_id="rotor_core_shaft_sun",
        placement=scad.identity_placement_rplacement(),
        name="Rotor back iron, shaft, and stage-1 sun",
    )
    rotor = scad.ground_component_rassembly(assembly=rotor, component_id="rotor_core_shaft_sun")
    for index, angle, _center in radial_centers(count=MOTOR_POLE_COUNT, radius=0.0):
        component_id = f"magnet_{index + 1:02d}"
        rotor = scad.add_component_rassembly(
            assembly=rotor,
            item=magnet,
            component_id=component_id,
            placement=make_z_rotation_rplacement(origin=(0.0, 0.0, 0.0), angle_degrees=angle),
            name=f"Bonded rotor magnet {index + 1}",
        )
        rotor = scad.add_fixed_constraint_rassembly(
            assembly=rotor,
            constraint_id=f"{component_id}_bonded_to_rotor",
            connector_a=connector_ref(component_id="rotor_core_shaft_sun", connector_id=component_id),
            connector_b=connector_ref(component_id=component_id, connector_id="bond_axis"),
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
    rotor = scad.solve_assembly_constraints_rassembly(assembly=rotor, strict=True)
    ground_constraint_report(label="rotor", assembly=rotor)
    print(
        f"rotor_direct_coupling: shaft_d={MOTOR_SHAFT_RADIUS * 2.0:.1f} "
        f"magnets={MOTOR_POLE_COUNT} stage1_sun_teeth={STAGE_1.sun_teeth}"
    )
    return rotor


def _make_stator_core_rpart(*, material: scad.Material) -> scad.Part:
    yoke = make_annulus_rsolid(
        outer_radius=MOTOR_STATOR_OUTER_RADIUS,
        inner_radius=MOTOR_STATOR_YOKE_INNER_RADIUS,
        bottom_z=MOTOR_STATOR_BOTTOM_Z,
        height=MOTOR_STATOR_TOP_Z - MOTOR_STATOR_BOTTOM_Z,
        tags=("role.stator_back_iron",),
    )
    tooth_length = MOTOR_STATOR_YOKE_INNER_RADIUS - MOTOR_STATOR_TOOTH_INNER_RADIUS + 0.40
    tooth_center_radius = MOTOR_STATOR_TOOTH_INNER_RADIUS + tooth_length / 2.0
    teeth = []
    for _index, angle, _center in radial_centers(count=MOTOR_SLOT_COUNT, radius=0.0):
        tooth = scad.make_box_rsolid(
            width=tooth_length,
            height=MOTOR_STATOR_TOOTH_WIDTH,
            depth=MOTOR_STATOR_TOP_Z - MOTOR_STATOR_BOTTOM_Z,
            bottom_face_center=(tooth_center_radius, 0.0, MOTOR_STATOR_BOTTOM_Z),
        )
        teeth.append(
            scad.rotate_shape(
                shape=tooth,
                angle=angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        )
    core = scad.union_rsolid(yoke, teeth, glue=False)
    core = apply_tags(
        shape=core,
        tags=("role.stator_core", "role.stator_thermal_path", "group.bldc_motor"),
    )
    connectors = [
        (
            "shell_axis",
            (0.0, 0.0, (MOTOR_STATOR_BOTTOM_Z + MOTOR_STATOR_TOP_Z) / 2.0),
            "Stator press-fit axis",
        )
    ]
    part = make_axis_part_rpart(
        part_id="stator_core",
        body=core,
        name="12-slot laminated electrical-steel stator stack",
        material=material,
        connectors=connectors,
    )
    for index, angle, _center in radial_centers(
        count=MOTOR_SLOT_COUNT,
        radius=0.0,
        angle_offset=0.0,
    ):
        rotation = make_z_rotation_rplacement(origin=(0.0, 0.0, 0.0), angle_degrees=angle)
        connector = scad.make_placement_connector_rconnector(
            connector_id=f"winding_{index + 1:02d}",
            placement=rotation,
            name=f"Slot winding {index + 1} retention datum",
        )
        part = scad.add_connector_rpart(part=part, connector=connector)
    print(
        f"stator_core_geometry: slots={MOTOR_SLOT_COUNT} active_length="
        f"{MOTOR_STATOR_TOP_Z - MOTOR_STATOR_BOTTOM_Z:.1f} radial_fit_clearance="
        f"{MOTOR_SHELL_INNER_RADIUS - MOTOR_STATOR_OUTER_RADIUS:.2f}"
    )
    return part


def _make_winding_pack_rpart(*, material: scad.Material) -> scad.Part:
    side_depth = MOTOR_STATOR_TOP_Z - MOTOR_STATOR_BOTTOM_Z + 0.4
    side_bottom_z = MOTOR_STATOR_BOTTOM_Z - 0.2
    side_positive = scad.make_box_rsolid(
        width=4.2,
        height=1.2,
        depth=side_depth,
        bottom_face_center=(17.55, 2.1, side_bottom_z),
    )
    side_negative = scad.make_box_rsolid(
        width=4.2,
        height=1.2,
        depth=side_depth,
        bottom_face_center=(17.55, -2.1, side_bottom_z),
    )
    rear_end_turn = scad.make_box_rsolid(
        width=4.2,
        height=5.4,
        depth=0.9,
        bottom_face_center=(17.55, 0.0, MOTOR_STATOR_BOTTOM_Z - 1.0),
    )
    front_end_turn = scad.make_box_rsolid(
        width=4.2,
        height=5.4,
        depth=0.9,
        bottom_face_center=(17.55, 0.0, MOTOR_STATOR_TOP_Z + 0.1),
    )
    winding = scad.union_rsolid(
        side_positive,
        side_negative,
        rear_end_turn,
        front_end_turn,
        glue=False,
    )
    winding = apply_tags(
        shape=winding,
        tags=("role.copper_slot_winding", "group.three_phase_windings"),
    )
    return make_axis_part_rpart(
        part_id="reusable_slot_winding",
        body=winding,
        name="Reusable four-segment copper tooth winding pack",
        material=material,
        connectors=(("mount_axis", (0.0, 0.0, 0.0), "Core potting datum"),),
    )


def _make_rotor_shaft_sun_rpart(*, material: scad.Material) -> scad.Part:
    shaft_bottom_z = REAR_BEARING_CENTER_Z - 3.0
    shaft = scad.make_cylinder_rsolid(
        radius=MOTOR_SHAFT_RADIUS,
        height=STAGE_1.top_z - shaft_bottom_z,
        bottom_face_center=(0.0, 0.0, shaft_bottom_z),
        axis=(0.0, 0.0, 1.0),
    )
    back_iron = scad.make_cylinder_rsolid(
        radius=MOTOR_ROTOR_BACKIRON_RADIUS,
        height=MOTOR_ROTOR_TOP_Z - MOTOR_ROTOR_BOTTOM_Z,
        bottom_face_center=(0.0, 0.0, MOTOR_ROTOR_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
    )
    sun = scad.std.gear.make_herringbone_gear_rsolid(
        n_teeth=STAGE_1.sun_teeth,
        module=STAGE_1.module,
        pressure_angle=PRESSURE_ANGLE,
        helix_angle=HELIX_ANGLE,
        gear_height=GEAR_HEIGHT,
        addendum_factor=ADDENDUM_FACTOR,
        clearance_factor=CLEARANCE_FACTOR,
        backlash=BACKLASH,
    )
    sun = scad.translate_shape(shape=sun, vector=(0.0, 0.0, STAGE_1.bottom_z))
    rotor = scad.union_rsolid(shaft, back_iron, sun, glue=False)
    rotor = apply_tags(
        shape=rotor,
        tags=("role.rotor_back_iron", "role.direct_drive_shaft", "role.stage1.sun_gear", "group.bldc_motor"),
    )
    part = make_axis_part_rpart(
        part_id="rotor_core_shaft_sun",
        body=rotor,
        name="Integrated rotor back iron, 8 mm shaft, and stage-1 sun",
        material=material,
        connectors=(
            ("rotor_axis", (0.0, 0.0, -2.5), "Motor rotation axis"),
            ("rear_bearing_axis", (0.0, 0.0, REAR_BEARING_CENTER_Z), "Rear motor bearing shaft seat"),
            ("front_bearing_axis", (0.0, 0.0, -2.5), "Front motor bearing shaft seat"),
            ("stage1_sun_axis", (0.0, 0.0, STAGE_1.mid_z), "Integrated stage-1 sun axis"),
        ),
    )
    for index, angle, _center in radial_centers(count=MOTOR_POLE_COUNT, radius=0.0):
        connector = scad.make_placement_connector_rconnector(
            connector_id=f"magnet_{index + 1:02d}",
            placement=make_z_rotation_rplacement(origin=(0.0, 0.0, 0.0), angle_degrees=angle),
            name=f"Magnet {index + 1} bond datum",
        )
        part = scad.add_connector_rpart(part=part, connector=connector)
    return part


def _make_rotor_magnet_rpart(*, material: scad.Material) -> scad.Part:
    half_width = MOTOR_MAGNET_TANGENTIAL_WIDTH / 2.0
    outer_x = (MOTOR_MAGNET_OUTER_RADIUS**2 - half_width**2) ** 0.5
    radial_depth = outer_x - MOTOR_ROTOR_BACKIRON_RADIUS + 0.05
    magnet = scad.make_box_rsolid(
        width=radial_depth,
        height=MOTOR_MAGNET_TANGENTIAL_WIDTH,
        depth=MOTOR_ROTOR_TOP_Z - MOTOR_ROTOR_BOTTOM_Z,
        bottom_face_center=(outer_x - radial_depth / 2.0, 0.0, MOTOR_ROTOR_BOTTOM_Z),
    )
    magnet = apply_tags(shape=magnet, tags=("role.rotor_magnet", "group.rotor_magnets"))
    print(
        f"rotor_magnet_envelope: corner_radius={MOTOR_MAGNET_OUTER_RADIUS:.2f} "
        f"air_gap={MOTOR_STATOR_TOOTH_INNER_RADIUS - MOTOR_MAGNET_OUTER_RADIUS:.2f}"
    )
    return make_axis_part_rpart(
        part_id="reusable_rotor_magnet",
        body=magnet,
        name="Reusable bonded NdFeB rotor magnet",
        material=material,
        connectors=(("bond_axis", (0.0, 0.0, 0.0), "Rotor bond datum"),),
    )
