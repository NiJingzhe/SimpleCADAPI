"""Serviceable motor shell, reducer case, bearing caps, and electronics cover."""

from __future__ import annotations

import simplecadapi as scad

try:
    from .common import (
        apply_tags,
        make_annulus_rsolid,
        make_axis_part_rpart,
        make_axial_hole_cutters_rsolids,
        radial_centers,
    )
    from .dimensions import (
        FRONT_MOTOR_BEARING,
        FRONT_MOTOR_BEARING_CENTER_Z,
        HOUSING_INTERFACE_LAND_INNER_RADIUS,
        INTERSTAGE_BEARING,
        INTERSTAGE_BEARING_CENTER_Z,
        MOTOR_INTERFACE_PCD,
        MOTOR_SHELL_BOTTOM_Z,
        MOTOR_SHELL_INNER_RADIUS,
        MOTOR_SHELL_TOP_Z,
        MOTOR_STATOR_BOTTOM_Z,
        MOTOR_STATOR_TOP_Z,
        M3_CLEARANCE_RADIUS,
        OUTPUT_BEARING_1_CENTER_Z,
        OUTPUT_BEARING_2_CENTER_Z,
        OUTPUT_CAP_BOTTOM_Z,
        OUTPUT_CAP_CARTRIDGE_TOP_Z,
        OUTPUT_CAP_INTERFACE_PCD,
        OUTPUT_CAP_TOP_Z,
        OUTPUT_CASE_CLAMP_CENTER_Z,
        OUTPUT_FLANGE_RADIUS,
        PACKAGE_RADIUS,
        PCB_BOTTOM_Z,
        PCB_STANDOFF_PCD,
        REAR_BEARING_CENTER_Z,
        REAR_COLUMN_PCD,
        REAR_COLUMN_RADIUS,
        REAR_COVER_BOTTOM_Z,
        REAR_COVER_THICKNESS,
        REAR_FASTENER_HOLE_RADIUS,
        REAR_SPIDER_BOSS_RADIUS,
        REAR_SPIDER_BOTTOM_Z,
        REDUCER_HOUSING_BOTTOM_Z,
        REDUCER_HOUSING_FRONT_Z,
        REDUCER_HOUSING_INNER_RADIUS,
        STAGE1_CARRIER_BOTTOM_Z,
        STAGE2_CARRIER_BOTTOM_Z,
        STAGE_1,
        STAGE_2,
    )
except ImportError:  # Support direct execution from this example directory.
    from common import (
        apply_tags,
        make_annulus_rsolid,
        make_axial_hole_cutters_rsolids,
        make_axis_part_rpart,
        radial_centers,
    )
    from dimensions import (
        FRONT_MOTOR_BEARING,
        FRONT_MOTOR_BEARING_CENTER_Z,
        HOUSING_INTERFACE_LAND_INNER_RADIUS,
        INTERSTAGE_BEARING,
        INTERSTAGE_BEARING_CENTER_Z,
        M3_CLEARANCE_RADIUS,
        MOTOR_INTERFACE_PCD,
        MOTOR_SHELL_BOTTOM_Z,
        MOTOR_SHELL_INNER_RADIUS,
        MOTOR_SHELL_TOP_Z,
        MOTOR_STATOR_BOTTOM_Z,
        MOTOR_STATOR_TOP_Z,
        OUTPUT_BEARING_1_CENTER_Z,
        OUTPUT_BEARING_2_CENTER_Z,
        OUTPUT_CAP_BOTTOM_Z,
        OUTPUT_CAP_CARTRIDGE_TOP_Z,
        OUTPUT_CAP_INTERFACE_PCD,
        OUTPUT_CAP_TOP_Z,
        OUTPUT_CASE_CLAMP_CENTER_Z,
        OUTPUT_FLANGE_RADIUS,
        PACKAGE_RADIUS,
        PCB_BOTTOM_Z,
        PCB_STANDOFF_PCD,
        REAR_BEARING_CENTER_Z,
        REAR_COLUMN_PCD,
        REAR_COLUMN_RADIUS,
        REAR_COVER_BOTTOM_Z,
        REAR_COVER_THICKNESS,
        REAR_FASTENER_HOLE_RADIUS,
        REAR_SPIDER_BOSS_RADIUS,
        REAR_SPIDER_BOTTOM_Z,
        REDUCER_HOUSING_BOTTOM_Z,
        REDUCER_HOUSING_FRONT_Z,
        REDUCER_HOUSING_INNER_RADIUS,
        STAGE1_CARRIER_BOTTOM_Z,
        STAGE2_CARRIER_BOTTOM_Z,
        STAGE_1,
        STAGE_2,
    )


@scad.requires_session
def make_motor_shell_rpart(*, material: scad.Material) -> scad.Part:
    """Create the stator sleeve, front attachment land, and rear columns."""

    sleeve = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=MOTOR_SHELL_INNER_RADIUS,
        bottom_z=MOTOR_SHELL_BOTTOM_Z,
        height=MOTOR_SHELL_TOP_Z - MOTOR_SHELL_BOTTOM_Z,
        tag_prefix="housing.motor.shell.sleeve",
        tags=("role.motor_shell", "role.stator_thermal_path"),
    )
    front_land = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=HOUSING_INTERFACE_LAND_INNER_RADIUS,
        bottom_z=MOTOR_SHELL_TOP_Z - 1.4,
        height=1.4,
        tag_prefix="housing.motor.shell.front.land",
        tags=("role.motor_reducer_mount",),
    )
    columns = []
    for index, _angle, center in radial_centers(count=4, radius=REAR_COLUMN_PCD / 2.0):
        columns.append(
            scad.make_cylinder_rsolid(
                radius=REAR_COLUMN_RADIUS,
                height=REAR_SPIDER_BOTTOM_Z - MOTOR_SHELL_BOTTOM_Z,
                bottom_face_center=(center[0], center[1], MOTOR_SHELL_BOTTOM_Z),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"housing.motor.shell.rear.column{index + 1}",
                result_tag=f"feature.housing.motor.shell.rear.column{index + 1}",
            )
        )
    shell = scad.union_rsolid(sleeve, front_land, columns, glue=False)
    shell = scad.cut_rsolid(
        shell,
        make_axial_hole_cutters_rsolids(
            count=6,
            pcd=MOTOR_INTERFACE_PCD,
            hole_radius=M3_CLEARANCE_RADIUS,
            bottom_z=MOTOR_SHELL_TOP_Z - 2.8,
            height=3.6,
            tag_prefix="housing.motor.shell.interface.clearance",
            angle_offset=30.0,
        ),
        make_axial_hole_cutters_rsolids(
            count=4,
            pcd=REAR_COLUMN_PCD,
            hole_radius=REAR_FASTENER_HOLE_RADIUS,
            bottom_z=MOTOR_SHELL_BOTTOM_Z - 1.0,
            height=10.4,
            tag_prefix="housing.motor.shell.rear.fastener.clearance",
        ),
        skip_non_intersecting=False,
    )
    shell = apply_tags(
        shape=shell,
        tags=("role.fixed_motor_housing", "group.integrated_bldc_actuator"),
    )
    print(
        f"motor_shell_interface: stator_d={MOTOR_SHELL_INNER_RADIUS * 2.0:.2f} "
        f"front_holes=6 rear_columns=4 wall={PACKAGE_RADIUS - MOTOR_SHELL_INNER_RADIUS:.2f}"
    )
    return make_axis_part_rpart(
        part_id="motor_shell",
        body=shell,
        name="50 mm BLDC motor shell with rear structural columns",
        material=material,
        connectors=(
            ("reducer_mount_axis", (0.0, 0.0, MOTOR_SHELL_TOP_Z), "Six-screw reducer mount"),
            (
                "stator_axis",
                (0.0, 0.0, (MOTOR_STATOR_BOTTOM_Z + MOTOR_STATOR_TOP_Z) / 2.0),
                "Stator thermal press-fit axis",
            ),
            ("rear_spider_axis", (0.0, 0.0, REAR_SPIDER_BOTTOM_Z), "Rear bearing spider mount"),
            ("rear_cover_axis", (0.0, 0.0, MOTOR_SHELL_BOTTOM_Z), "Rear electronics cover mount"),
        ),
    )


@scad.requires_session
def make_reducer_housing_rpart(*, material: scad.Material) -> scad.Part:
    """Create the reducer sleeve and front motor-bearing bulkhead."""

    sleeve = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=REDUCER_HOUSING_INNER_RADIUS,
        bottom_z=REDUCER_HOUSING_BOTTOM_Z,
        height=REDUCER_HOUSING_FRONT_Z - REDUCER_HOUSING_BOTTOM_Z,
        tag_prefix="housing.reducer.sleeve",
        tags=("role.reducer_housing_sleeve",),
    )
    bulkhead = make_annulus_rsolid(
        outer_radius=23.10,
        inner_radius=FRONT_MOTOR_BEARING.outer_diameter / 2.0 + 0.05,
        bottom_z=REDUCER_HOUSING_BOTTOM_Z,
        height=STAGE_1.bottom_z - REDUCER_HOUSING_BOTTOM_Z,
        tag_prefix="housing.reducer.front.bulkhead",
        tags=("role.motor_front_bearing_bulkhead",),
    )
    interstage_divider = make_annulus_rsolid(
        outer_radius=23.10,
        inner_radius=INTERSTAGE_BEARING.outer_diameter / 2.0 + 0.05,
        bottom_z=INTERSTAGE_BEARING_CENTER_Z - INTERSTAGE_BEARING.width / 2.0,
        height=INTERSTAGE_BEARING.width,
        tag_prefix="housing.reducer.interstage.divider",
        tags=("role.interstage_bearing_divider",),
    )
    output_mount_land = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=HOUSING_INTERFACE_LAND_INNER_RADIUS,
        bottom_z=REDUCER_HOUSING_FRONT_Z - 2.2,
        height=2.2,
        tag_prefix="housing.reducer.output.mount.land",
        tags=("role.output_cap_mount_land",),
    )
    housing = scad.union_rsolid(
        sleeve,
        bulkhead,
        interstage_divider,
        output_mount_land,
        glue=False,
    )
    housing = scad.cut_rsolid(
        housing,
        make_axial_hole_cutters_rsolids(
            count=6,
            pcd=MOTOR_INTERFACE_PCD,
            hole_radius=M3_CLEARANCE_RADIUS,
            bottom_z=REDUCER_HOUSING_BOTTOM_Z - 1.0,
            height=STAGE_1.bottom_z - REDUCER_HOUSING_BOTTOM_Z + 2.0,
            tag_prefix="housing.reducer.motor.interface.clearance",
            angle_offset=30.0,
        ),
        make_axial_hole_cutters_rsolids(
            count=6,
            pcd=OUTPUT_CAP_INTERFACE_PCD,
            hole_radius=M3_CLEARANCE_RADIUS,
            bottom_z=REDUCER_HOUSING_FRONT_Z - 2.2,
            height=3.2,
            tag_prefix="housing.reducer.output.interface.clearance",
        ),
        skip_non_intersecting=False,
    )
    housing = apply_tags(
        shape=housing,
        tags=("role.fixed_reducer_housing", "role.ring_gear_press_fit", "group.integrated_bldc_actuator"),
    )
    print(
        f"reducer_housing: bore_d={REDUCER_HOUSING_INNER_RADIUS * 2.0:.2f} "
        f"wall={PACKAGE_RADIUS - REDUCER_HOUSING_INNER_RADIUS:.2f} bulkhead=8.00 "
        f"interstage_bearing_z={INTERSTAGE_BEARING_CENTER_Z:.2f} "
        f"m3_inner_ligament={MOTOR_INTERFACE_PCD / 2.0 - M3_CLEARANCE_RADIUS - HOUSING_INTERFACE_LAND_INNER_RADIUS:.2f}"
    )
    return make_axis_part_rpart(
        part_id="reducer_housing",
        body=housing,
        name="50 mm reducer housing with motor bearing bulkhead",
        material=material,
        connectors=(
            ("motor_mount_axis", (0.0, 0.0, MOTOR_SHELL_TOP_Z), "Motor shell six-screw interface"),
            ("front_motor_bearing_axis", (0.0, 0.0, FRONT_MOTOR_BEARING_CENTER_Z), "Front motor bearing seat"),
            ("stage1_ring_axis", (0.0, 0.0, STAGE_1.mid_z), "Stage 1 fixed ring seat"),
            ("stage1_carrier_axis", (0.0, 0.0, INTERSTAGE_BEARING_CENTER_Z), "Stage 1 carrier axis"),
            ("interstage_bearing_axis", (0.0, 0.0, INTERSTAGE_BEARING_CENTER_Z), "Interstage bearing outer seat"),
            ("stage2_ring_axis", (0.0, 0.0, STAGE_2.mid_z), "Stage 2 fixed ring seat"),
            ("stage2_carrier_axis", (0.0, 0.0, STAGE2_CARRIER_BOTTOM_Z + 1.50), "Output carrier axis"),
            (
                "case_clamp_axis",
                (0.0, 0.0, OUTPUT_CASE_CLAMP_CENTER_Z),
                "External split-clamp datum on reducer sleeve",
            ),
            ("output_cap_axis", (0.0, 0.0, REDUCER_HOUSING_FRONT_Z), "Output bearing cap interface"),
        ),
    )


@scad.requires_session
def make_rear_bearing_spider_rpart(*, material: scad.Material) -> scad.Part:
    """Create a four-arm removable rear motor-bearing support."""

    bottom_z = REAR_SPIDER_BOTTOM_Z
    hub = make_annulus_rsolid(
        outer_radius=10.5,
        inner_radius=8.05,
        bottom_z=bottom_z,
        height=5.0,
        tag_prefix="housing.rear.spider.bearing.hub",
        tags=("role.rear_motor_bearing_seat",),
    )
    solids = [hub]
    for index, angle, center in radial_centers(count=4, radius=REAR_COLUMN_PCD / 2.0):
        arm = scad.make_box_rsolid(
            width=12.0,
            height=3.0,
            depth=5.0,
            bottom_face_center=(14.5, 0.0, bottom_z),
            tag_prefix=f"housing.rear.spider.arm{index + 1}",
            result_tag=f"feature.housing.rear.spider.arm{index + 1}",
        )
        solids.append(
            scad.rotate_shape(
                shape=arm,
                angle=angle,
                axis=(0.0, 0.0, 1.0),
                origin=(0.0, 0.0, 0.0),
            )
        )
        solids.append(
            scad.make_cylinder_rsolid(
                radius=REAR_SPIDER_BOSS_RADIUS,
                height=5.0,
                bottom_face_center=(center[0], center[1], bottom_z),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"housing.rear.spider.boss{index + 1}",
                result_tag=f"feature.housing.rear.spider.boss{index + 1}",
            )
        )
    spider = scad.union_rsolid(solids, glue=False)
    spider = scad.cut_rsolid(
        spider,
        make_axial_hole_cutters_rsolids(
            count=4,
            pcd=REAR_COLUMN_PCD,
            hole_radius=REAR_FASTENER_HOLE_RADIUS,
            bottom_z=bottom_z - 1.0,
            height=7.0,
            tag_prefix="housing.rear.spider.fastener.clearance",
        ),
        skip_non_intersecting=False,
    )
    spider = apply_tags(
        shape=spider,
        tags=("role.removable_rear_bearing_spider", "group.integrated_bldc_actuator"),
    )
    print("rear_bearing_spider: arms=4 bearing_seat_d=16.10 fasteners=4")
    return make_axis_part_rpart(
        part_id="rear_bearing_spider",
        body=spider,
        name="Four-arm removable rear motor-bearing spider",
        material=material,
        connectors=(
            ("shell_axis", (0.0, 0.0, REAR_SPIDER_BOTTOM_Z), "Motor shell column interface"),
            ("bearing_axis", (0.0, 0.0, REAR_BEARING_CENTER_Z), "Rear motor bearing outer seat"),
        ),
    )


@scad.requires_session
def make_rear_electronics_cover_rpart(*, material: scad.Material) -> scad.Part:
    """Create the rear cover with PCB standoffs and terminal apertures."""

    cover = scad.make_cylinder_rsolid(
        radius=PACKAGE_RADIUS,
        height=REAR_COVER_THICKNESS,
        bottom_face_center=(0.0, 0.0, REAR_COVER_BOTTOM_Z),
        axis=(0.0, 0.0, 1.0),
        tag_prefix="housing.rear.cover.plate",
        result_tag="feature.housing.rear.cover.plate",
    )
    standoffs = []
    for index, _angle, center in radial_centers(
        count=4,
        radius=PCB_STANDOFF_PCD / 2.0,
        angle_offset=45.0,
    ):
        standoffs.append(
            scad.make_cylinder_rsolid(
                radius=2.4,
                height=PCB_BOTTOM_Z - REAR_COVER_BOTTOM_Z - REAR_COVER_THICKNESS + 0.1,
                bottom_face_center=(center[0], center[1], REAR_COVER_BOTTOM_Z + REAR_COVER_THICKNESS - 0.1),
                axis=(0.0, 0.0, 1.0),
                tag_prefix=f"housing.rear.cover.pcb.standoff{index + 1}",
                result_tag=f"feature.housing.rear.cover.pcb.standoff{index + 1}",
            )
        )
    cover = scad.union_rsolid(cover, standoffs, glue=False)
    phase_aperture = scad.make_box_rsolid(
        width=9.2,
        height=7.2,
        depth=REAR_COVER_THICKNESS + 2.0,
        bottom_face_center=(-11.0, 0.0, REAR_COVER_BOTTOM_Z - 1.0),
        tag_prefix="housing.rear.cover.phase.aperture",
        result_tag="tool.housing.rear.cover.phase.aperture",
    )
    power_aperture = scad.make_box_rsolid(
        width=9.2,
        height=7.2,
        depth=REAR_COVER_THICKNESS + 2.0,
        bottom_face_center=(11.0, 0.0, REAR_COVER_BOTTOM_Z - 1.0),
        tag_prefix="housing.rear.cover.power.can.aperture",
        result_tag="tool.housing.rear.cover.power.can.aperture",
    )
    center_service = scad.make_cylinder_rsolid(
        radius=3.2,
        height=REAR_COVER_THICKNESS + 2.0,
        bottom_face_center=(0.0, 0.0, REAR_COVER_BOTTOM_Z - 1.0),
        axis=(0.0, 0.0, 1.0),
        tag_prefix="housing.rear.cover.center.service",
        result_tag="tool.housing.rear.cover.center.service",
    )
    cover = scad.cut_rsolid(
        cover,
        phase_aperture,
        power_aperture,
        center_service,
        make_axial_hole_cutters_rsolids(
            count=4,
            pcd=REAR_COLUMN_PCD,
            hole_radius=REAR_FASTENER_HOLE_RADIUS,
            bottom_z=REAR_COVER_BOTTOM_Z - 1.0,
            height=REAR_COVER_THICKNESS + 2.0,
            tag_prefix="housing.rear.cover.column.fastener.clearance",
        ),
        make_axial_hole_cutters_rsolids(
            count=4,
            pcd=PCB_STANDOFF_PCD,
            hole_radius=1.1,
            bottom_z=REAR_COVER_BOTTOM_Z - 1.0,
            height=PCB_BOTTOM_Z - REAR_COVER_BOTTOM_Z + 2.0,
            tag_prefix="housing.rear.cover.pcb.fastener.clearance",
            angle_offset=45.0,
        ),
        skip_non_intersecting=False,
    )
    cover = apply_tags(
        shape=cover,
        tags=("role.rear_electronics_cover", "role.terminal_access", "group.integrated_bldc_actuator"),
    )
    print("rear_cover_access: phase_opening=9.2x7.2 power_can_opening=9.2x7.2 pcb_holes=4")
    return make_axis_part_rpart(
        part_id="rear_electronics_cover",
        body=cover,
        name="Rear electronics cover with terminal access",
        material=material,
        connectors=(
            ("shell_axis", (0.0, 0.0, MOTOR_SHELL_BOTTOM_Z), "Four-screw motor shell interface"),
            ("pcb_axis", (0.0, 0.0, PCB_BOTTOM_Z + 0.8), "Controller PCB mounting plane"),
            ("phase_access", (-11.0, 0.0, REAR_COVER_BOTTOM_Z), "Three-phase terminal access"),
            ("power_can_access", (11.0, 0.0, REAR_COVER_BOTTOM_Z), "Power and CAN terminal access"),
        ),
    )


@scad.requires_session
def make_output_bearing_cap_rpart(*, material: scad.Material) -> scad.Part:
    """Create the removable paired-bearing cartridge and front cap."""

    bearing_clearance_radius = 12.05
    rear_flange = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=bearing_clearance_radius,
        bottom_z=OUTPUT_CAP_BOTTOM_Z,
        height=3.0,
        tag_prefix="housing.output.cap.rear.flange",
        tags=("role.output_cap_mount_flange",),
    )
    cartridge = make_annulus_rsolid(
        outer_radius=15.0,
        inner_radius=bearing_clearance_radius,
        bottom_z=OUTPUT_CAP_BOTTOM_Z,
        height=OUTPUT_CAP_CARTRIDGE_TOP_Z - OUTPUT_CAP_BOTTOM_Z + 0.1,
        tag_prefix="housing.output.cap.bearing.cartridge",
        tags=("role.paired_output_bearing_seat",),
    )
    bearing_retainer = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=8.10,
        bottom_z=OUTPUT_CAP_CARTRIDGE_TOP_Z - 0.1,
        height=0.5,
        tag_prefix="housing.output.cap.bearing.retainer",
        tags=("role.output_axial_retainer",),
    )
    outer_lip = make_annulus_rsolid(
        outer_radius=PACKAGE_RADIUS,
        inner_radius=OUTPUT_FLANGE_RADIUS + 0.30,
        bottom_z=OUTPUT_CAP_CARTRIDGE_TOP_Z - 0.1,
        height=OUTPUT_CAP_TOP_Z - OUTPUT_CAP_CARTRIDGE_TOP_Z + 0.1,
        tag_prefix="housing.output.cap.labyrinth.lip",
        tags=("role.output_labyrinth_lip",),
    )
    cap = scad.union_rsolid(rear_flange, cartridge, bearing_retainer, outer_lip, glue=False)
    cap = scad.cut_rsolid(
        cap,
        make_axial_hole_cutters_rsolids(
            count=6,
            pcd=OUTPUT_CAP_INTERFACE_PCD,
            hole_radius=M3_CLEARANCE_RADIUS,
            bottom_z=OUTPUT_CAP_BOTTOM_Z - 1.0,
            height=OUTPUT_CAP_TOP_Z - OUTPUT_CAP_BOTTOM_Z + 2.0,
            tag_prefix="housing.output.cap.interface.clearance",
        ),
        skip_non_intersecting=False,
    )
    cap = apply_tags(
        shape=cap,
        tags=("role.removable_output_bearing_cap", "group.integrated_bldc_actuator"),
    )
    print(
        f"output_bearing_cap: bearing_seat_d={bearing_clearance_radius * 2.0:.2f} "
        f"bearing_span={OUTPUT_BEARING_2_CENTER_Z - OUTPUT_BEARING_1_CENTER_Z:.1f} fasteners=6"
    )
    return make_axis_part_rpart(
        part_id="output_bearing_cap",
        body=cap,
        name="Paired output-bearing cartridge and removable cap",
        material=material,
        connectors=(
            ("housing_axis", (0.0, 0.0, OUTPUT_CAP_BOTTOM_Z), "Six-screw housing interface"),
            ("bearing_1_axis", (0.0, 0.0, OUTPUT_BEARING_1_CENTER_Z), "Rear output bearing seat"),
            ("bearing_2_axis", (0.0, 0.0, OUTPUT_BEARING_2_CENTER_Z), "Front output bearing seat"),
            ("case_mount_axis", (0.0, 0.0, OUTPUT_CAP_TOP_Z), "Fixed actuator case datum"),
        ),
    )
