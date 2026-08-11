"""Standard bearing factories and coaxial/planet placements."""

from __future__ import annotations

import simplecadapi as scad

try:
    from .common import PART_INPUTS, CACHE, make_z_rotation_rplacement
    from .dimensions import BearingSpec, PLANET_COUNT, StageSpec
    from .gears import planet_center_xy
    from .materials import make_actuator_material_rmaterial
except ImportError:  # Support direct execution from this example directory.
    from common import PART_INPUTS, CACHE, make_z_rotation_rplacement
    from dimensions import BearingSpec, PLANET_COUNT, StageSpec
    from gears import planet_center_xy
    from materials import make_actuator_material_rmaterial


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
def make_planet_bearing_rplacement(*, stage: StageSpec, index: int) -> scad.Placement:
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


@scad.requires_session
def _make_bearing_ring_part_rpart(
    *,
    bearing_id: str,
    spec: BearingSpec,
    role: str,
    material: scad.Material,
) -> scad.Part:
    bearing = make_main_bearing_rassembly(
        bearing_id=bearing_id,
        spec=spec,
        material=material,
    )
    return bearing.get_component(role).item


def _bearing_part_builder(
    *,
    bearing_id: str,
    spec: BearingSpec,
    role: str,
):
    @scad.part(
        id=f"{bearing_id}_{role}",
        inputs=PART_INPUTS,
        cache=CACHE,
    )
    def build() -> scad.Part:
        return _make_bearing_ring_part_rpart(
            bearing_id=bearing_id,
            spec=spec,
            role=role,
            material=make_actuator_material_rmaterial(key="gear"),
        )

    return build


def build_bearing_ring_definitions(
    *,
    bearing_id: str,
    spec: BearingSpec,
) -> tuple[scad.PartBuildResult, scad.PartBuildResult]:
    """Build the two immutable ring definitions for one bearing size."""

    outer = _bearing_part_builder(
        bearing_id=bearing_id,
        spec=spec,
        role="outer_ring",
    )()
    inner = _bearing_part_builder(
        bearing_id=bearing_id,
        spec=spec,
        role="inner_ring",
    )()
    return outer, inner


def coaxial_bearing_placement(*, center_z: float) -> scad.Placement:
    return scad.make_placement_rplacement(origin=(0.0, 0.0, center_z))


def planet_bearing_placement(
    *,
    stage: StageSpec,
    index: int,
) -> scad.Placement:
    if index < 0 or index >= PLANET_COUNT:
        raise ValueError(f"planet bearing index out of range: {index}")
    center = planet_center_xy(stage=stage, index=index)
    return scad.make_placement_rplacement(
        origin=(center[0], center[1], stage.mid_z),
    )
