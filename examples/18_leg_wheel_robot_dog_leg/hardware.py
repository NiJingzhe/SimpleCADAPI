"""Modeled bolts, threaded fasteners, and joint bushings for Example 18."""

from __future__ import annotations

import simplecadapi as scad

from leg_common import make_part_with_connectors_rpart
from leg_dimensions import KNEE_AXIS


def make_socket_head_screw_rpart(
    *,
    part_id: str,
    shank_radius: float,
    shank_length: float,
    head_radius: float,
    head_height: float,
    material: scad.Material,
) -> scad.Part:
    """Create a socket-head screw with its seat plane at local Z=0."""

    shank = scad.make_cylinder_rsolid(
        radius=shank_radius,
        height=shank_length,
        bottom_face_center=(0.0, 0.0, -head_height - shank_length),
        axis=(0.0, 0.0, 1.0),
    )
    head = scad.make_cylinder_rsolid(
        radius=head_radius,
        height=head_height,
        bottom_face_center=(0.0, 0.0, -head_height),
        axis=(0.0, 0.0, 1.0),
    )
    screw = scad.union_rsolid(shank, head, glue=False)
    screw = scad.apply_tag(shape=screw, tag="role.socket_head_screw")
    return make_part_with_connectors_rpart(
        part_id=part_id,
        body=screw,
        name=f"Socket-head screw {shank_radius * 2.0:.1f} x {shank_length:.1f} mm",
        material=material,
        connectors=(("head_top_axis", (0.0, 0.0, 0.0), "z", "Flush screw head top plane"),),
    )


def make_clamp_bolt_stack_rpart(*, material: scad.Material) -> scad.Part:
    """Create an M4 bolt plus flange-nut stack for a split collar."""

    shank_length = 12.2
    shank = scad.make_cylinder_rsolid(
        radius=2.0,
        height=shank_length,
        bottom_face_center=(0.0, 0.0, -shank_length),
        axis=(0.0, 0.0, 1.0),
    )
    head = scad.make_cylinder_rsolid(
        radius=3.6,
        height=3.2,
        bottom_face_center=(0.0, 0.0, -0.05),
        axis=(0.0, 0.0, 1.0),
    )
    nut = scad.make_cylinder_rsolid(
        radius=3.8,
        height=3.2,
        bottom_face_center=(0.0, 0.0, -shank_length - 3.15),
        axis=(0.0, 0.0, 1.0),
    )
    stack = scad.union_rsolid(shank, head, nut, glue=False)
    stack = scad.apply_tag(shape=stack, tag="role.clamp_bolt_and_nut")
    return make_part_with_connectors_rpart(
        part_id="m4_split_clamp_bolt_stack",
        body=stack,
        name="M4 split-clamp socket bolt and flange nut",
        material=material,
        connectors=(("seat_axis", (0.0, 0.0, 0.0), "z", "Clamp bolt head seat"),),
    )


def make_knee_bushing_rpart(*, material: scad.Material) -> scad.Part:
    """Create a continuous bronze knee sleeve and axial spacer."""

    outer = scad.make_cylinder_rsolid(
        radius=5.95,
        height=13.0,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], 0.0),
        axis=(0.0, 0.0, 1.0),
    )
    bore = scad.make_cylinder_rsolid(
        radius=3.2,
        height=15.0,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], -1.0),
        axis=(0.0, 0.0, 1.0),
    )
    sleeve = scad.cut_rsolid(outer, bore, skip_non_intersecting=False)
    sleeve = scad.apply_tag(shape=sleeve, tag="role.knee_bearing_bushing")
    return make_part_with_connectors_rpart(
        part_id="knee_bronze_bushing",
        body=sleeve,
        name="12 mm OD bronze knee bushing and spacer",
        material=material,
        connectors=(
            ("knee_axis", (KNEE_AXIS[0], KNEE_AXIS[1], 6.5), "z", "Knee revolute axis"),
            ("bolt_head_top_axis", (KNEE_AXIS[0], KNEE_AXIS[1], 16.0), "z", "Shoulder bolt head top plane"),
        ),
    )


def make_knee_shoulder_bolt_stack_rpart(*, material: scad.Material) -> scad.Part:
    """Create the knee shoulder axle, socket head, and retained nut."""

    shaft = scad.make_cylinder_rsolid(
        radius=3.0,
        height=13.0,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], 0.0),
        axis=(0.0, 0.0, 1.0),
    )
    head = scad.make_cylinder_rsolid(
        radius=5.5,
        height=3.0,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], 13.0),
        axis=(0.0, 0.0, 1.0),
    )
    nut = scad.make_cylinder_rsolid(
        radius=5.5,
        height=4.0,
        bottom_face_center=(KNEE_AXIS[0], KNEE_AXIS[1], -4.0),
        axis=(0.0, 0.0, 1.0),
    )
    axle = scad.union_rsolid(shaft, head, nut, glue=False)
    axle = scad.apply_tag(shape=axle, tag="role.knee_shoulder_axle")
    return make_part_with_connectors_rpart(
        part_id="knee_shoulder_bolt_stack",
        body=axle,
        name="M6 knee shoulder axle with socket head and retained nut",
        material=material,
        connectors=(("knee_axis", (KNEE_AXIS[0], KNEE_AXIS[1], 6.5), "z", "Knee axle axis"),),
    )
def make_linkage_pin_stack_rpart(*, material: scad.Material) -> scad.Part:
    """Create a retained M4 shoulder pin spanning crank, gap, and pushrod."""

    span = 9.3
    shaft = scad.make_cylinder_rsolid(
        radius=2.0,
        height=span,
        bottom_face_center=(0.0, 0.0, -span / 2.0),
        axis=(0.0, 0.0, 1.0),
    )
    retainers = [
        scad.make_cylinder_rsolid(
            radius=3.5,
            height=1.2,
            bottom_face_center=(0.0, 0.0, sign * span / 2.0 - (1.2 if sign < 0.0 else 0.0)),
            axis=(0.0, 0.0, 1.0),
        )
        for sign in (-1.0, 1.0)
    ]
    pin = scad.union_rsolid(shaft, retainers, glue=False)
    pin = scad.apply_tag(shape=pin, tag="role.retained_linkage_pin")
    return make_part_with_connectors_rpart(
        part_id="m4_linkage_shoulder_pin_stack",
        body=pin,
        name="M4 retained linkage shoulder pin",
        material=material,
        connectors=(("pin_axis", (0.0, 0.0, 0.0), "z", "Linkage pin axis"),),
    )
