"""Standard bearing factories and coaxial/planet placements."""

from __future__ import annotations

import simplecadapi as scad

if __package__:
    from .common import make_z_rotation_rplacement
    from .dimensions import BearingSpec, PLANET_COUNT, StageSpec
    from .gears import planet_center_xy
else:
    from common import make_z_rotation_rplacement
    from dimensions import BearingSpec, PLANET_COUNT, StageSpec
    from gears import planet_center_xy


@scad.requires_session
def make_standard_planet_bearing_rassembly(
    *, bearing_id: str, spec: BearingSpec, material: scad.Material
) -> scad.Assembly:
    """Create a fused standard-library planet ball-bearing assembly."""

    return make_main_bearing_rassembly(
        bearing_id=bearing_id,
        spec=spec,
        material=material,
    )


@scad.requires_session
def make_main_bearing_rassembly(
    *, bearing_id: str, spec: BearingSpec, material: scad.Material
) -> scad.Assembly:
    """Create a standard-library bearing with fused rolling elements."""

    bearing = scad.std.bearing.make_ball_bearing_rassembly(
        bore_diameter=spec.bore_diameter,
        outer_diameter=spec.outer_diameter,
        bearing_width=spec.width,
        ball_diameter=spec.ball_diameter,
        ball_count=spec.ball_count,
        raceway_clearance=0.0,
        edge_chamfer=0.0,
        assembly_id=bearing_id,
        drive_angle_degrees=None,
        fuse_rolling_elements=True,
        rolling_element_fuse_overlap=0.03,
        material=material,
    )
    meta = bearing.get_metadata("std.bearing.ball_bearing")
    outer = bearing.get_component("outer_ring").item.body
    inner = bearing.get_component("inner_ring").item.body
    print(
        f"bearing_{bearing_id}: stdlib=fused rollers={meta['ball_count']} "
        f"bore={spec.bore_diameter:.1f} od={spec.outer_diameter:.1f} "
        f"width={spec.width:.1f} outer_faces={len(outer.get_faces())} "
        f"inner_faces={len(inner.get_faces())} material={material.material_id}"
    )
    return bearing


@scad.requires_session
def make_coaxial_bearing_rplacement(*, center_z: float) -> scad.Placement:
    """Place a standard bearing center plane on the actuator Z axis."""

    return make_z_rotation_rplacement(origin=(0.0, 0.0, center_z), angle_degrees=0.0)


@scad.requires_session
def make_planet_bearing_rplacement(
    *, stage: StageSpec, index: int
) -> scad.Placement:
    """Place a standard planet bearing at the gear midplane."""

    if index < 0 or index >= PLANET_COUNT:
        raise ValueError(f"planet bearing index out of range: {index}")
    center = planet_center_xy(stage=stage, index=index)
    print(
        f"{stage.stage_id}_planet_bearing_{index + 1}: "
        f"center=({center[0]:.3f},{center[1]:.3f},{stage.mid_z:.3f})"
    )
    return make_z_rotation_rplacement(
        origin=(center[0], center[1], stage.mid_z), angle_degrees=0.0
    )


