"""Standard ball bearing assemblies placed in the reducer."""

from __future__ import annotations

import math

import simplecadapi as scad

from common import make_z_rotation_rplacement
from dimensions import BearingSpec, PLANET_COUNT, StageSpec


@scad.requires_session
def make_radial_ball_bearing_rassembly(
    *,
    bearing_id: str,
    spec: BearingSpec,
    tag_prefix: str,
) -> scad.Assembly:
    """Create a standard radial ball bearing assembly for reducer placement."""

    bearing = scad.std.bearing.make_ball_bearing_rassembly(
        bore_diameter=spec.bore_diameter,
        outer_diameter=spec.outer_diameter,
        bearing_width=spec.width,
        ball_diameter=spec.ball_diameter,
        ball_count=spec.ball_count,
        raceway_clearance=spec.raceway_clearance,
        edge_chamfer=spec.edge_chamfer,
        assembly_id=bearing_id,
        drive_angle_degrees=None,
    )
    meta = bearing.get_metadata("std.bearing.ball_bearing")
    outer_ring = bearing.get_component("outer_ring").item.body
    outer_ring = scad.apply_tag(shape=outer_ring, tag=f"solid.{tag_prefix}.outer.ring")
    inner_ring = bearing.get_component("inner_ring").item.body
    inner_ring = scad.apply_tag(shape=inner_ring, tag=f"solid.{tag_prefix}.inner.ring")
    rolling_element = bearing.get_component(meta["ball_component_ids"][0]).item.body
    scad.apply_tag(shape=rolling_element, tag=f"solid.{tag_prefix}.rolling.element")
    print(
        f"bearing_{bearing_id}: components={len(bearing.component_ids())} balls={meta['ball_count']} "
        f"od={spec.outer_diameter:.2f} bore={spec.bore_diameter:.2f} width={spec.width:.2f}"
    )
    print(
        f"bearing_{bearing_id}_rings: outer_faces={len(outer_ring.get_faces())} "
        f"inner_faces={len(inner_ring.get_faces())}"
    )
    return bearing


@scad.requires_session
def make_coaxial_bearing_rplacement(*, z: float) -> scad.Placement:
    """Return a coaxial bearing placement at the requested axial center."""

    return make_z_rotation_rplacement(origin=(0.0, 0.0, z), angle_degrees=0.0)


@scad.requires_session
def make_planet_bearing_rplacements(*, stage: StageSpec) -> list[scad.Placement]:
    """Return placed bearing placements centered in all planets of one stage."""

    placements = []
    for index in range(PLANET_COUNT):
        angle = math.radians(360.0 * index / PLANET_COUNT)
        center = (
            stage.planet_center_radius * math.cos(angle),
            stage.planet_center_radius * math.sin(angle),
            stage.mid_z,
        )
        placements.append(make_z_rotation_rplacement(origin=center, angle_degrees=0.0))
        print(
            f"{stage.stage_id}_planet_bearing_{index + 1}: "
            f"center=({center[0]:.3f},{center[1]:.3f},{center[2]:.3f})"
        )
    return placements
