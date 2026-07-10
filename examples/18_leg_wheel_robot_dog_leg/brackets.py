"""Stationary bolt-aligned mounting brackets for the leg-wheel example."""

from __future__ import annotations

import simplecadapi as scad

from leg_common import make_bolt_circle_cutters_rsolidlist, make_part_with_connectors_rpart
from leg_dimensions import (
    ACTUATOR_CASE_OUTER_RADIUS,
    BODY_STANDOFF_THICKNESS,
    BODY_STANDOFF_Z,
    FASTENER_CLEARANCE_RADIUS,
    HOUSING_MOUNT_BOLT_ANGLES_DEGREES,
    HOUSING_MOUNT_BOLT_CIRCLE_RADIUS,
    HOUSING_MOUNT_BOLT_CLEARANCE_RADIUS,
    HOUSING_MOUNT_COUNTERBORE_RADIUS,
    KNEE_STACK_CLAMP_THICKNESS,
    KNEE_STACK_CLAMP_Z,
    KNEE_DRIVE_AXIS,
    ROOT_AXIS,
)


def make_body_mount_plate_rpart(*, material: scad.Material) -> scad.Part:
    """Create the body-fixed hip stack bracket for both coaxial actuator cases."""

    z_min = BODY_STANDOFF_Z - BODY_STANDOFF_THICKNESS / 2.0
    clamp_z_min = KNEE_STACK_CLAMP_Z - KNEE_STACK_CLAMP_THICKNESS / 2.0
    stack_post_height = clamp_z_min + KNEE_STACK_CLAMP_THICKNESS - z_min
    ring = scad.make_cylinder_rsolid(
        radius=38.0,
        height=BODY_STANDOFF_THICKNESS,
        bottom_face_center=(ROOT_AXIS[0], ROOT_AXIS[1], z_min),
        axis=(0.0, 0.0, 1.0),
    )
    left_ear = scad.make_box_rsolid(
        width=24.0,
        height=16.0,
        depth=BODY_STANDOFF_THICKNESS,
        bottom_face_center=(-45.0, ROOT_AXIS[1], z_min),
    )
    right_ear = scad.make_box_rsolid(
        width=24.0,
        height=16.0,
        depth=BODY_STANDOFF_THICKNESS,
        bottom_face_center=(45.0, ROOT_AXIS[1], z_min),
    )
    top_clamp = scad.make_cylinder_rsolid(
        radius=43.0,
        height=KNEE_STACK_CLAMP_THICKNESS,
        bottom_face_center=(KNEE_DRIVE_AXIS[0], KNEE_DRIVE_AXIS[1], clamp_z_min),
        axis=(0.0, 0.0, 1.0),
    )
    left_stack_post = scad.make_cylinder_rsolid(
        radius=5.5,
        height=stack_post_height,
        bottom_face_center=(-42.0, ROOT_AXIS[1], z_min),
        axis=(0.0, 0.0, 1.0),
    )
    right_stack_post = scad.make_cylinder_rsolid(
        radius=5.5,
        height=stack_post_height,
        bottom_face_center=(42.0, ROOT_AXIS[1], z_min),
        axis=(0.0, 0.0, 1.0),
    )
    plate = scad.union_rsolid(
        [ring, left_ear, right_ear, top_clamp, left_stack_post, right_stack_post],
        glue=False,
    )
    cutters = [
        scad.make_cylinder_rsolid(
            radius=11.0,
            height=BODY_STANDOFF_THICKNESS + 2.0,
            bottom_face_center=(ROOT_AXIS[0], ROOT_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=FASTENER_CLEARANCE_RADIUS + 0.6,
            height=BODY_STANDOFF_THICKNESS + 2.0,
            bottom_face_center=(-45.0, ROOT_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=FASTENER_CLEARANCE_RADIUS + 0.6,
            height=BODY_STANDOFF_THICKNESS + 2.0,
            bottom_face_center=(45.0, ROOT_AXIS[1], z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        ),
        scad.make_cylinder_rsolid(
            radius=ACTUATOR_CASE_OUTER_RADIUS + 2.2,
            height=KNEE_STACK_CLAMP_THICKNESS + 2.0,
            bottom_face_center=(
                KNEE_DRIVE_AXIS[0],
                KNEE_DRIVE_AXIS[1],
                clamp_z_min - 1.0,
            ),
            axis=(0.0, 0.0, 1.0),
        ),
    ]
    cutters.extend(
        make_bolt_circle_cutters_rsolidlist(
            center=ROOT_AXIS,
            bolt_circle_radius=HOUSING_MOUNT_BOLT_CIRCLE_RADIUS,
            angles_degrees=HOUSING_MOUNT_BOLT_ANGLES_DEGREES,
            hole_radius=HOUSING_MOUNT_BOLT_CLEARANCE_RADIUS,
            z_min=z_min - 1.0,
            height=BODY_STANDOFF_THICKNESS + 2.0,
            counterbore_radius=HOUSING_MOUNT_COUNTERBORE_RADIUS,
            counterbore_depth=1.4,
            counterbore_from_top=False,
            counterbore_face_z=z_min,
        )
    )
    plate = scad.cut_rsolid(plate, cutters, skip_non_intersecting=False)
    plate = scad.apply_tag(shape=plate, tag="role.body_mount_plate")
    print(
        f"body_mount_plate: housing_bolt_circle={HOUSING_MOUNT_BOLT_CIRCLE_RADIUS:.1f} "
        f"holes={len(HOUSING_MOUNT_BOLT_ANGLES_DEGREES)} z={BODY_STANDOFF_Z:.1f} "
        f"knee_drive_stack_clamp_z={KNEE_STACK_CLAMP_Z:.1f} "
        f"faces={len(plate.get_faces())} volume={plate.get_volume():.3f}"
    )
    return make_part_with_connectors_rpart(
        part_id="body_mount_plate",
        body=plate,
        name=(
            "Body-fixed hip motor stack bracket with separate thigh and "
            "knee-drive case datums"
        ),
        material=material,
        connectors=(
            ("case_axis", ROOT_AXIS, "z", "Body-fixed thigh actuator case datum"),
            (
                "knee_drive_case_axis",
                KNEE_DRIVE_AXIS,
                "z",
                "Body-fixed knee-drive actuator case datum",
            ),
            (
                "body_frame_axis",
                (ROOT_AXIS[0], ROOT_AXIS[1], BODY_STANDOFF_Z),
                "z",
                "Body frame datum",
            ),
        ),
    )
