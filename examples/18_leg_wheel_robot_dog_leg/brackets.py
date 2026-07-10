"""Split-clamp actuator mounts for the leg-wheel example."""

from __future__ import annotations

import simplecadapi as scad

from leg_common import make_part_with_connectors_rpart
from leg_dimensions import (
    BODY_STANDOFF_THICKNESS,
    BODY_STANDOFF_Z,
    CASE_CLAMP_INNER_RADIUS,
    CASE_CLAMP_OUTER_RADIUS,
    CASE_CLAMP_PINCH_AXIS_RADIUS,
    CASE_CLAMP_PINCH_HALF_SPAN,
    CASE_CLAMP_PINCH_HOLE_RADIUS,
    CASE_CLAMP_SLIT_WIDTH,
    CASE_CLAMP_WIDTH,
    KNEE_CASE_CLAMP_Z,
    ROOT_AXIS,
    THIGH_CASE_CLAMP_Z,
)


def make_split_case_clamp_rsolid(
    *, center: tuple[float, float, float], z_center: float, tag: str
) -> scad.Solid:
    """Create one machinable C-clamp with coaxial pinch-bolt ears."""

    z_min = z_center - CASE_CLAMP_WIDTH / 2.0
    outer = scad.make_cylinder_rsolid(
        radius=CASE_CLAMP_OUTER_RADIUS,
        height=CASE_CLAMP_WIDTH,
        bottom_face_center=(center[0], center[1], z_min),
        axis=(0.0, 0.0, 1.0),
    )
    bore = scad.make_cylinder_rsolid(
        radius=CASE_CLAMP_INNER_RADIUS,
        height=CASE_CLAMP_WIDTH + 2.0,
        bottom_face_center=(center[0], center[1], z_min - 1.0),
        axis=(0.0, 0.0, 1.0),
    )
    clamp = scad.cut_rsolid(outer, bore, skip_non_intersecting=False)

    ear_center_x = center[0] + CASE_CLAMP_PINCH_AXIS_RADIUS - 2.5
    ear_center_y = CASE_CLAMP_SLIT_WIDTH / 2.0 + 2.5
    ears = [
        scad.make_box_rsolid(
            width=8.0,
            height=5.0,
            depth=CASE_CLAMP_WIDTH,
            bottom_face_center=(ear_center_x, center[1] + sign * ear_center_y, z_min),
        )
        for sign in (-1.0, 1.0)
    ]
    clamp = scad.union_rsolid(clamp, ears, glue=False)
    slit = scad.make_box_rsolid(
        width=15.0,
        height=CASE_CLAMP_SLIT_WIDTH,
        depth=CASE_CLAMP_WIDTH + 2.0,
        bottom_face_center=(center[0] + 31.0, center[1], z_min - 1.0),
    )
    pinch_hole = scad.make_cylinder_rsolid(
        radius=CASE_CLAMP_PINCH_HOLE_RADIUS,
        height=CASE_CLAMP_PINCH_HALF_SPAN * 2.0,
        bottom_face_center=(
            center[0] + CASE_CLAMP_PINCH_AXIS_RADIUS,
            center[1] - CASE_CLAMP_PINCH_HALF_SPAN,
            z_center,
        ),
        axis=(0.0, 1.0, 0.0),
    )
    clamp = scad.cut_rsolid(
        clamp,
        slit,
        pinch_hole,
        skip_non_intersecting=False,
    )
    clamp = scad.apply_tag(shape=clamp, tag=tag)
    print(
        f"{tag}: bore_d={CASE_CLAMP_INNER_RADIUS * 2.0:.2f} "
        f"pinch_hole_d={CASE_CLAMP_PINCH_HOLE_RADIUS * 2.0:.2f} "
        f"faces={len(clamp.get_faces())} volume={clamp.get_volume():.3f}"
    )
    return clamp


def make_body_mount_plate_rpart(*, material: scad.Material) -> scad.Part:
    """Build the two-collar body mount for coaxial tandem root actuators."""

    lower = make_split_case_clamp_rsolid(
        center=ROOT_AXIS,
        z_center=THIGH_CASE_CLAMP_Z,
        tag="role.thigh_actuator_split_clamp",
    )
    upper = make_split_case_clamp_rsolid(
        center=ROOT_AXIS,
        z_center=KNEE_CASE_CLAMP_Z,
        tag="role.knee_drive_split_clamp",
    )
    lower_z = THIGH_CASE_CLAMP_Z - CASE_CLAMP_WIDTH / 2.0
    upper_z = KNEE_CASE_CLAMP_Z + CASE_CLAMP_WIDTH / 2.0
    post_height = upper_z - lower_z
    post_offset_x = 35.0
    posts = [
        scad.make_cylinder_rsolid(
            radius=3.8,
            height=post_height,
            bottom_face_center=(ROOT_AXIS[0] + sign * post_offset_x, ROOT_AXIS[1], lower_z),
            axis=(0.0, 0.0, 1.0),
        )
        for sign in (-1.0, 1.0)
    ]
    collar_bridges = [
        scad.make_box_rsolid(
            width=8.0,
            height=7.6,
            depth=CASE_CLAMP_WIDTH,
            bottom_face_center=(
                ROOT_AXIS[0] + sign * 33.0,
                ROOT_AXIS[1],
                clamp_z - CASE_CLAMP_WIDTH / 2.0,
            ),
        )
        for sign in (-1.0, 1.0)
        for clamp_z in (THIGH_CASE_CLAMP_Z, KNEE_CASE_CLAMP_Z)
    ]
    lug_z_min = BODY_STANDOFF_Z - BODY_STANDOFF_THICKNESS / 2.0
    lugs = [
        scad.make_box_rsolid(
            width=24.0,
            height=18.0,
            depth=BODY_STANDOFF_THICKNESS,
            bottom_face_center=(ROOT_AXIS[0] + sign * 41.0, ROOT_AXIS[1], lug_z_min),
        )
        for sign in (-1.0, 1.0)
    ]
    mount = scad.union_rsolid(lower, upper, posts, collar_bridges, lugs, glue=False)
    torso_holes = [
        scad.make_cylinder_rsolid(
            radius=2.3,
            height=BODY_STANDOFF_THICKNESS + 2.0,
            bottom_face_center=(ROOT_AXIS[0] + sign * 45.0, ROOT_AXIS[1], lug_z_min - 1.0),
            axis=(0.0, 0.0, 1.0),
        )
        for sign in (-1.0, 1.0)
    ]
    mount = scad.cut_rsolid(mount, torso_holes, skip_non_intersecting=False)
    mount = scad.apply_tag(shape=mount, tag="role.body_mount_plate")
    print(
        "body_mount_plate: root_actuators=2 tandem=true "
        f"clamp_z=({THIGH_CASE_CLAMP_Z:.1f},{KNEE_CASE_CLAMP_Z:.1f}) "
        f"torso_holes=2 faces={len(mount.get_faces())} volume={mount.get_volume():.3f}"
    )
    return make_part_with_connectors_rpart(
        part_id="body_mount_plate",
        body=mount,
        name="Coaxial tandem root actuator split-clamp and body lug bracket",
        material=material,
        connectors=(
            ("case_axis", (ROOT_AXIS[0], ROOT_AXIS[1], THIGH_CASE_CLAMP_Z), "z", "Thigh actuator clamp datum"),
            (
                "knee_drive_case_axis",
                (ROOT_AXIS[0], ROOT_AXIS[1], KNEE_CASE_CLAMP_Z),
                "z",
                "Knee-drive actuator clamp datum opposite the crank",
            ),
            (
                "thigh_clamp_bolt_seat",
                (
                    ROOT_AXIS[0] + CASE_CLAMP_PINCH_AXIS_RADIUS,
                    ROOT_AXIS[1] + CASE_CLAMP_PINCH_HALF_SPAN - 0.9,
                    THIGH_CASE_CLAMP_Z,
                ),
                "y",
                "Thigh collar M4 bolt head seat",
            ),
            (
                "knee_clamp_bolt_seat",
                (
                    ROOT_AXIS[0] + CASE_CLAMP_PINCH_AXIS_RADIUS,
                    ROOT_AXIS[1] + CASE_CLAMP_PINCH_HALF_SPAN - 0.9,
                    KNEE_CASE_CLAMP_Z,
                ),
                "y",
                "Knee-drive collar M4 bolt head seat",
            ),
            (
                "body_frame_axis",
                (ROOT_AXIS[0], ROOT_AXIS[1], BODY_STANDOFF_Z),
                "z",
                "Body frame datum",
            ),
        ),
    )
