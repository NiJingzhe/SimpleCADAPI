"""Bolt-aligned link, crank, pushrod, shank, and wheel parts for Example 18."""

from __future__ import annotations

import math

import simplecadapi as scad

from leg_common import (
    make_bolt_circle_cutters_rsolidlist,
    make_part_with_connectors_rpart,
    make_rounded_bar_rsolid,
    make_rounded_slot_cutter_rsolid,
)
from leg_dimensions import (
    DISTAL_CRANK_LENGTH,
    DISTAL_CRANK_THICKNESS,
    DISTAL_CRANK_WIDTH,
    DISTAL_CRANK_Z,
    DISTAL_PUSHROD_PIN,
    FASTENER_CLEARANCE_RADIUS,
    HOUSING_MOUNT_BOLT_ANGLES_DEGREES,
    HOUSING_MOUNT_BOLT_CIRCLE_RADIUS,
    HOUSING_MOUNT_BOLT_CLEARANCE_RADIUS,
    HOUSING_MOUNT_COUNTERBORE_RADIUS,
    KNEE_AXIS,
    KNEE_BEARING_BOLT_CIRCLE_RADIUS,
    KNEE_BEARING_BOLT_COUNT,
    KNEE_BEARING_BORE_RADIUS,
    KNEE_BEARING_OUTER_RADIUS,
    KNEE_DRIVE_AXIS,
    KNEE_PIVOT_Z,
    OUTPUT_FLANGE_BOLT_ANGLES_DEGREES,
    OUTPUT_FLANGE_BOLT_CIRCLE_RADIUS,
    OUTPUT_FLANGE_BOLT_CLEARANCE_RADIUS,
    OUTPUT_FLANGE_BOLT_COUNTERBORE_RADIUS,
    OUTPUT_FLANGE_OUTER_RADIUS,
    OUTPUT_FLANGE_REGISTER_INNER_RADIUS,
    OUTPUT_FLANGE_REGISTER_OUTER_RADIUS,
    PIN_CLEARANCE_RADIUS,
    PROXIMAL_PUSHROD_PIN,
    PUSHROD_THICKNESS,
    PUSHROD_WIDTH,
    PUSHROD_Z,
    REMOTE_CRANK_LENGTH,
    REMOTE_CRANK_THICKNESS,
    REMOTE_CRANK_WIDTH,
    REMOTE_CRANK_Z,
    ROD_PIN_AXIS_Z,
    ROD_PIN_CLEARANCE_RADIUS,
    ROOT_AXIS,
    SHANK_KNEE_RADIUS,
    SHANK_LENGTH,
    SHANK_LINK_THICKNESS,
    SHANK_LINK_Z,
    SHANK_WEB_WIDTH,
    SHANK_WHEEL_RADIUS,
    SHANK_WINDOW_LENGTH,
    SHANK_WINDOW_WIDTH,
    UPPER_LINK_KNEE_RADIUS,
    UPPER_LINK_ROOT_RADIUS,
    UPPER_LINK_THICKNESS,
    UPPER_LINK_WEB_WIDTH,
    UPPER_LINK_WINDOW_LENGTH,
    UPPER_LINK_WINDOW_WIDTH,
    UPPER_LINK_Z,
    WHEEL_AXIS,
    WHEEL_HUB_PLATE_RADIUS,
    WHEEL_HUB_PLATE_THICKNESS,
    WHEEL_SPOKE_COUNT,
    WHEEL_SPOKE_WIDTH,
    WHEEL_TIRE_BORE_RADIUS,
    WHEEL_TIRE_RADIUS,
    WHEEL_TIRE_WIDTH,
)


def make_upper_link_plate_rpart(*, material: scad.Material) -> scad.Part:
    """Build the output-bolted upper link plate with knee bearing holes."""

    plate = _make_axis_plate_base_rsolid(
        start=ROOT_AXIS,
        end=KNEE_AXIS,
        z_center=UPPER_LINK_Z,
        thickness=UPPER_LINK_THICKNESS,
        start_radius=UPPER_LINK_ROOT_RADIUS,
        end_radius=UPPER_LINK_KNEE_RADIUS,
        web_width=UPPER_LINK_WEB_WIDTH,
        tag="role.upper_link_plate_base",
    )
    z_min = UPPER_LINK_Z - UPPER_LINK_THICKNESS / 2.0
    cutters = [
        scad.make_cylinder_rsolid(
            radius=OUTPUT_FLANGE_REGISTER_INNER_RADIUS + 0.8,
            height=UPPER_LINK_THICKNESS + 2.0,
            bottom_face_center=(ROOT_AXIS[0], ROOT_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=KNEE_BEARING_BORE_RADIUS,
            height=UPPER_LINK_THICKNESS + 2.0,
            bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
    ]
    cutters.extend(
        make_bolt_circle_cutters_rsolidlist(
            center=ROOT_AXIS,
            bolt_circle_radius=OUTPUT_FLANGE_BOLT_CIRCLE_RADIUS,
            angles_degrees=OUTPUT_FLANGE_BOLT_ANGLES_DEGREES,
            hole_radius=OUTPUT_FLANGE_BOLT_CLEARANCE_RADIUS,
            z_min=z_min - 1.0,
            height=UPPER_LINK_THICKNESS + 2.0,
            counterbore_radius=OUTPUT_FLANGE_BOLT_COUNTERBORE_RADIUS,
            counterbore_depth=1.0,
            counterbore_from_top=True,
            counterbore_face_z=z_min + UPPER_LINK_THICKNESS,
        )
    )
    cutters.extend(_make_knee_retainer_cutters(z_min=z_min - 1.0, height=UPPER_LINK_THICKNESS + 2.0))
    cutters.extend(
        _make_link_window_cutters(
            start=ROOT_AXIS,
            end=KNEE_AXIS,
            z_center=UPPER_LINK_Z,
            thickness=UPPER_LINK_THICKNESS,
            fractions=(0.40, 0.67),
            length=UPPER_LINK_WINDOW_LENGTH,
            width=UPPER_LINK_WINDOW_WIDTH,
            tag_prefix="upper_link_window",
        )
    )
    plate = scad.cut_rsolid(plate, cutters, skip_non_intersecting=False)
    plate = scad.apply_tag(shape=plate, tag="role.upper_link_plate")
    print(
        f"upper_link_plate: output_holes={len(OUTPUT_FLANGE_BOLT_ANGLES_DEGREES)} "
        f"output_pcd={OUTPUT_FLANGE_BOLT_CIRCLE_RADIUS * 2.0:.1f} "
        f"knee_retainer_holes={KNEE_BEARING_BOLT_COUNT} faces={len(plate.get_faces())} "
        f"volume={plate.get_volume():.3f}"
    )
    return make_part_with_connectors_rpart(
        part_id="upper_link_plate",
        body=plate,
        name="Upper link plate bolted to actuator output flange and knee bearing retainer",
        material=material,
        connectors=(
            ("output_axis", ROOT_AXIS, "z", "Actuator output flange datum"),
            ("knee_axis", (KNEE_AXIS[0], KNEE_AXIS[1], KNEE_PIVOT_Z), "z", "Knee bearing datum"),
        ),
    )


def make_proximal_crank_rpart(*, material: scad.Material) -> scad.Part:
    """Create the short crank on the independent knee-drive actuator output."""

    crank = _make_axis_plate_base_rsolid(
        start=KNEE_DRIVE_AXIS,
        end=PROXIMAL_PUSHROD_PIN,
        z_center=REMOTE_CRANK_Z,
        thickness=REMOTE_CRANK_THICKNESS,
        start_radius=OUTPUT_FLANGE_OUTER_RADIUS,
        end_radius=REMOTE_CRANK_WIDTH / 2.0 + 2.0,
        web_width=REMOTE_CRANK_WIDTH,
        tag="role.proximal_output_crank_base",
    )
    z_min = REMOTE_CRANK_Z - REMOTE_CRANK_THICKNESS / 2.0
    cutters = [
        scad.make_cylinder_rsolid(
            radius=OUTPUT_FLANGE_REGISTER_INNER_RADIUS + 0.6,
            height=REMOTE_CRANK_THICKNESS + 2.0,
            bottom_face_center=(KNEE_DRIVE_AXIS[0], KNEE_DRIVE_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=ROD_PIN_CLEARANCE_RADIUS,
            height=REMOTE_CRANK_THICKNESS + 2.0,
            bottom_face_center=(PROXIMAL_PUSHROD_PIN[0], PROXIMAL_PUSHROD_PIN[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
    ]
    cutters.extend(
        make_bolt_circle_cutters_rsolidlist(
            center=KNEE_DRIVE_AXIS,
            bolt_circle_radius=OUTPUT_FLANGE_BOLT_CIRCLE_RADIUS,
            angles_degrees=OUTPUT_FLANGE_BOLT_ANGLES_DEGREES,
            hole_radius=OUTPUT_FLANGE_BOLT_CLEARANCE_RADIUS,
            z_min=z_min - 1.0,
            height=REMOTE_CRANK_THICKNESS + 2.0,
        )
    )
    crank = scad.cut_rsolid(crank, cutters, skip_non_intersecting=False)
    crank = scad.apply_tag(shape=crank, tag="role.proximal_output_crank")
    print(
        f"knee_drive_output_crank: length={REMOTE_CRANK_LENGTH:.1f} "
        f"output_flange_holes={len(OUTPUT_FLANGE_BOLT_ANGLES_DEGREES)} "
        f"faces={len(crank.get_faces())} volume={crank.get_volume():.3f}"
    )
    return make_part_with_connectors_rpart(
        part_id="proximal_output_crank",
        body=crank,
        name="Knee-drive crank plate using the second actuator output flange holes",
        material=material,
        connectors=(
            ("output_axis", KNEE_DRIVE_AXIS, "z", "Knee-drive actuator output flange datum"),
            ("rod_pin", (PROXIMAL_PUSHROD_PIN[0], PROXIMAL_PUSHROD_PIN[1], ROD_PIN_AXIS_Z), "z", "Proximal pushrod pin datum"),
        ),
    )


def make_pushrod_rpart(*, material: scad.Material) -> scad.Part:
    """Create the flat pushrod with real pin-clearance holes."""

    pushrod = make_rounded_bar_rsolid(
        start=(PROXIMAL_PUSHROD_PIN[0], PROXIMAL_PUSHROD_PIN[1], PUSHROD_Z),
        end=(DISTAL_PUSHROD_PIN[0], DISTAL_PUSHROD_PIN[1], PUSHROD_Z),
        width=PUSHROD_WIDTH,
        thickness=PUSHROD_THICKNESS,
        end_hole_radius=ROD_PIN_CLEARANCE_RADIUS,
        lightening_hole_radius=None,
        lightening_count=0,
        tag="role.knee_pushrod_plate",
    )
    print(
        f"knee_pushrod: pin_distance={_xy_distance(PROXIMAL_PUSHROD_PIN, DISTAL_PUSHROD_PIN):.1f} "
        f"pin_hole_diameter={ROD_PIN_CLEARANCE_RADIUS * 2.0:.1f}"
    )
    return make_part_with_connectors_rpart(
        part_id="knee_pushrod",
        body=pushrod,
        name="Flat pushrod plate with matched clevis pin holes",
        material=material,
        connectors=(
            ("proximal_pin", (PROXIMAL_PUSHROD_PIN[0], PROXIMAL_PUSHROD_PIN[1], ROD_PIN_AXIS_Z), "z", "Proximal crank pin datum"),
            ("distal_pin", (DISTAL_PUSHROD_PIN[0], DISTAL_PUSHROD_PIN[1], ROD_PIN_AXIS_Z), "z", "Integral shank ear pin datum"),
        ),
    )


def make_shank_link_rpart(*, material: scad.Material) -> scad.Part:
    """Build the lower shank plate with an integral pushrod extension ear."""

    shank = _make_axis_plate_base_rsolid(
        start=KNEE_AXIS,
        end=WHEEL_AXIS,
        z_center=SHANK_LINK_Z,
        thickness=SHANK_LINK_THICKNESS,
        start_radius=SHANK_KNEE_RADIUS,
        end_radius=SHANK_WHEEL_RADIUS,
        web_width=SHANK_WEB_WIDTH,
        tag="role.shank_link_base",
    )
    z_min = SHANK_LINK_Z - SHANK_LINK_THICKNESS / 2.0
    distal_z_min = DISTAL_CRANK_Z - DISTAL_CRANK_THICKNESS / 2.0
    distal_z_top = distal_z_min + DISTAL_CRANK_THICKNESS
    distal_drive_ear = _make_axis_plate_base_rsolid(
        start=KNEE_AXIS,
        end=DISTAL_PUSHROD_PIN,
        z_center=DISTAL_CRANK_Z,
        thickness=DISTAL_CRANK_THICKNESS,
        start_radius=KNEE_BEARING_OUTER_RADIUS,
        end_radius=DISTAL_CRANK_WIDTH / 2.0 + 2.0,
        web_width=DISTAL_CRANK_WIDTH,
        tag="role.shank_integral_pushrod_ear_base",
    )
    standoff_outer = scad.make_cylinder_rsolid(
        radius=KNEE_BEARING_OUTER_RADIUS,
        height=distal_z_top - z_min,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], z_min),
        axis=(0.0, 0.0, 1.0),
    )
    standoff_inner = scad.make_cylinder_rsolid(
        radius=KNEE_BEARING_BORE_RADIUS,
        height=distal_z_top - z_min + 2.0,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], z_min - 1.0),
        axis=(0.0, 0.0, 1.0),
    )
    knee_standoff = scad.cut_rsolid(standoff_outer, standoff_inner, skip_non_intersecting=False)
    shank = scad.union_rsolid([shank, distal_drive_ear, knee_standoff], glue=False)
    integrated_knee_height = distal_z_top - z_min + 2.0
    cutters = [
        scad.make_cylinder_rsolid(
            radius=PIN_CLEARANCE_RADIUS + 2.8,
            height=integrated_knee_height,
            bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=ROD_PIN_CLEARANCE_RADIUS,
            height=DISTAL_CRANK_THICKNESS + 2.0,
            bottom_face_center=(DISTAL_PUSHROD_PIN[0], DISTAL_PUSHROD_PIN[1], distal_z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=19.5,
            height=SHANK_LINK_THICKNESS + 2.0,
            bottom_face_center=(WHEEL_AXIS[0], WHEEL_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
    ]
    cutters.extend(_make_knee_retainer_cutters(z_min=z_min - 1.0, height=integrated_knee_height))
    cutters.extend(
        make_bolt_circle_cutters_rsolidlist(
            center=WHEEL_AXIS,
            bolt_circle_radius=HOUSING_MOUNT_BOLT_CIRCLE_RADIUS,
            angles_degrees=HOUSING_MOUNT_BOLT_ANGLES_DEGREES,
            hole_radius=HOUSING_MOUNT_BOLT_CLEARANCE_RADIUS,
            z_min=z_min - 1.0,
            height=SHANK_LINK_THICKNESS + 2.0,
            counterbore_radius=HOUSING_MOUNT_COUNTERBORE_RADIUS,
            counterbore_depth=1.0,
            counterbore_from_top=True,
            counterbore_face_z=z_min + SHANK_LINK_THICKNESS,
        )
    )
    cutters.extend(
        _make_link_window_cutters(
            start=KNEE_AXIS,
            end=WHEEL_AXIS,
            z_center=SHANK_LINK_Z,
            thickness=SHANK_LINK_THICKNESS,
            fractions=(0.42, 0.66),
            length=SHANK_WINDOW_LENGTH,
            width=SHANK_WINDOW_WIDTH,
            tag_prefix="shank_window",
        )
    )
    shank = scad.cut_rsolid(shank, cutters, skip_non_intersecting=False)
    shank = scad.apply_tag(shape=shank, tag="role.shank_wheel_plate")
    print(
        f"shank_link: wheel_case_holes={len(HOUSING_MOUNT_BOLT_ANGLES_DEGREES)} "
        f"wheel_case_pcd={HOUSING_MOUNT_BOLT_CIRCLE_RADIUS * 2.0:.1f} "
        f"integral_pushrod_ear={DISTAL_CRANK_LENGTH:.1f} "
        f"length={SHANK_LENGTH:.1f} faces={len(shank.get_faces())} volume={shank.get_volume():.3f}"
    )
    return make_part_with_connectors_rpart(
        part_id="shank_link",
        body=shank,
        name="Lower shank plate with integral pushrod ear and wheel actuator housing bolt circle",
        material=material,
        connectors=(
            ("knee_axis", (KNEE_AXIS[0], KNEE_AXIS[1], KNEE_PIVOT_Z), "z", "Knee revolute datum"),
            ("rod_pin", (DISTAL_PUSHROD_PIN[0], DISTAL_PUSHROD_PIN[1], ROD_PIN_AXIS_Z), "z", "Integral shank pushrod pin datum"),
            ("wheel_case_axis", WHEEL_AXIS, "z", "Wheel hub actuator case datum"),
        ),
    )


def make_wheel_tire_rpart(*, material: scad.Material) -> scad.Part:
    """Create a spoked wheel bolted to the actuator output flange."""

    tire_outer = scad.make_cylinder_rsolid(
        radius=WHEEL_TIRE_RADIUS,
        height=WHEEL_TIRE_WIDTH,
        bottom_face_center=(WHEEL_AXIS[0], WHEEL_AXIS[1], -WHEEL_TIRE_WIDTH / 2.0),
        axis=(0.0, 0.0, 1.0),
    )
    tire_bore = scad.make_cylinder_rsolid(
        radius=WHEEL_TIRE_BORE_RADIUS,
        height=WHEEL_TIRE_WIDTH + 2.0,
        bottom_face_center=(WHEEL_AXIS[0], WHEEL_AXIS[1], -WHEEL_TIRE_WIDTH / 2.0 - 1.0),
        axis=(0.0, 0.0, 1.0),
    )
    tire_ring = scad.cut_rsolid(tire_outer, tire_bore, skip_non_intersecting=False)
    hub_z = 3.0
    hub_z_min = hub_z - WHEEL_HUB_PLATE_THICKNESS / 2.0
    hub = scad.make_cylinder_rsolid(
        radius=WHEEL_HUB_PLATE_RADIUS,
        height=WHEEL_HUB_PLATE_THICKNESS,
        bottom_face_center=(WHEEL_AXIS[0], WHEEL_AXIS[1], hub_z_min),
        axis=(0.0, 0.0, 1.0),
    )
    spokes = [_make_wheel_spoke_rsolid(angle_degrees=360.0 * index / WHEEL_SPOKE_COUNT) for index in range(WHEEL_SPOKE_COUNT)]
    wheel = scad.union_rsolid([tire_ring, hub, spokes], glue=False)
    cutters = [
        scad.make_cylinder_rsolid(
            radius=OUTPUT_FLANGE_REGISTER_INNER_RADIUS + 0.4,
            height=WHEEL_HUB_PLATE_THICKNESS + 2.0,
            bottom_face_center=(WHEEL_AXIS[0], WHEEL_AXIS[1], hub_z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        )
    ]
    cutters.extend(
        make_bolt_circle_cutters_rsolidlist(
            center=WHEEL_AXIS,
            bolt_circle_radius=OUTPUT_FLANGE_BOLT_CIRCLE_RADIUS,
            angles_degrees=OUTPUT_FLANGE_BOLT_ANGLES_DEGREES,
            hole_radius=OUTPUT_FLANGE_BOLT_CLEARANCE_RADIUS,
            z_min=hub_z_min - 1.0,
            height=WHEEL_HUB_PLATE_THICKNESS + 2.0,
            counterbore_radius=OUTPUT_FLANGE_BOLT_COUNTERBORE_RADIUS,
            counterbore_depth=0.9,
            counterbore_from_top=True,
            counterbore_face_z=hub_z_min + WHEEL_HUB_PLATE_THICKNESS,
        )
    )
    wheel = scad.cut_rsolid(wheel, cutters, skip_non_intersecting=False)
    wheel = scad.apply_tag(shape=wheel, tag="role.spoked_wheel_tire")
    print(
        f"wheel_tire: output_holes={len(OUTPUT_FLANGE_BOLT_ANGLES_DEGREES)} "
        f"spokes={WHEEL_SPOKE_COUNT} tire_radius={WHEEL_TIRE_RADIUS:.1f} "
        f"faces={len(wheel.get_faces())} volume={wheel.get_volume():.3f}"
    )
    return make_part_with_connectors_rpart(
        part_id="wheel_tire",
        body=wheel,
        name="Spoked wheel bolted to the hub actuator output flange",
        material=material,
        connectors=(("wheel_axis", WHEEL_AXIS, "z", "Wheel spin datum"),),
    )


def _make_axis_plate_base_rsolid(
    *,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    z_center: float,
    thickness: float,
    start_radius: float,
    end_radius: float,
    web_width: float,
    tag: str,
) -> scad.Solid:
    length = _xy_distance(start, end)
    if length <= max(start_radius, end_radius):
        raise ValueError("axis plate endpoints are too close")
    z_min = z_center - thickness / 2.0
    web = scad.make_box_rsolid(
        width=length,
        height=web_width,
        depth=thickness,
        bottom_face_center=(length / 2.0, 0.0, z_min),
    )
    start_boss = scad.make_cylinder_rsolid(
        radius=start_radius,
        height=thickness,
        bottom_face_center=(0.0, 0.0, z_min),
        axis=(0.0, 0.0, 1.0),
    )
    end_boss = scad.make_cylinder_rsolid(
        radius=end_radius,
        height=thickness,
        bottom_face_center=(length, 0.0, z_min),
        axis=(0.0, 0.0, 1.0),
    )
    plate = scad.union_rsolid([web, start_boss, end_boss], glue=False)
    angle_degrees = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
    plate = scad.rotate_shape(
        shape=plate,
        angle=angle_degrees,
        axis=(0.0, 0.0, 1.0),
        origin=(0.0, 0.0, z_center),
    )
    plate = scad.translate_shape(shape=plate, vector=(start[0], start[1], 0.0))
    return scad.apply_tag(shape=plate, tag=tag)


def _make_knee_retainer_cutters(*, z_min: float, height: float) -> list[scad.Solid]:
    angles = tuple(360.0 * index / KNEE_BEARING_BOLT_COUNT for index in range(KNEE_BEARING_BOLT_COUNT))
    return make_bolt_circle_cutters_rsolidlist(
        center=KNEE_AXIS,
        bolt_circle_radius=KNEE_BEARING_BOLT_CIRCLE_RADIUS,
        angles_degrees=angles,
        hole_radius=FASTENER_CLEARANCE_RADIUS,
        z_min=z_min,
        height=height,
    )


def _make_link_window_cutters(
    *,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    z_center: float,
    thickness: float,
    fractions: tuple[float, ...],
    length: float,
    width: float,
    tag_prefix: str,
) -> list[scad.Solid]:
    angle_degrees = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
    cutters = []
    for index, fraction in enumerate(fractions, start=1):
        cutters.append(
            make_rounded_slot_cutter_rsolid(
                center=(
                    start[0] + (end[0] - start[0]) * fraction,
                    start[1] + (end[1] - start[1]) * fraction,
                    z_center,
                ),
                length=length,
                width=width,
                height=thickness + 2.0,
                angle_degrees=angle_degrees,
                tag=f"role.{tag_prefix}_{index}",
            )
        )
    return cutters


def _make_wheel_spoke_rsolid(*, angle_degrees: float) -> scad.Solid:
    hub_overlap_radius = WHEEL_HUB_PLATE_RADIUS - 1.5
    rim_overlap_radius = WHEEL_TIRE_BORE_RADIUS + 1.5
    length = rim_overlap_radius - hub_overlap_radius
    radial_center = (hub_overlap_radius + rim_overlap_radius) / 2.0
    z_center = 3.0
    spoke = scad.make_box_rsolid(
        width=length,
        height=WHEEL_SPOKE_WIDTH,
        depth=WHEEL_HUB_PLATE_THICKNESS,
        bottom_face_center=(WHEEL_AXIS[0] + radial_center, WHEEL_AXIS[1], z_center - WHEEL_HUB_PLATE_THICKNESS / 2.0),
    )
    return scad.rotate_shape(
        shape=spoke,
        angle=angle_degrees,
        axis=(0.0, 0.0, 1.0),
        origin=WHEEL_AXIS,
    )


def _xy_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])
