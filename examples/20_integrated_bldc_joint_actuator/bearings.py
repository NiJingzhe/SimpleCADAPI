"""Standard bearing factories and coaxial/planet placements."""

from __future__ import annotations

import simplecadapi as scad

if __package__:
    from .common import make_annulus_rsolid, make_axis_part_rpart, make_z_rotation_rplacement
    from .dimensions import BearingSpec, PLANET_COUNT, StageSpec
    from .gears import planet_center_xy
else:
    from common import make_annulus_rsolid, make_axis_part_rpart, make_z_rotation_rplacement
    from dimensions import BearingSpec, PLANET_COUNT, StageSpec
    from gears import planet_center_xy


def make_standard_planet_bearing_rassembly(
    *,
    bearing_id: str,
    spec: BearingSpec,
    material: scad.Material,
) -> scad.Assembly:
    """Create the reused catalog-style planet ball bearing assembly."""

    bearing = make_main_bearing_rassembly(
        bearing_id=bearing_id,
        spec=spec,
        material=material,
    )
    print(
        f"bearing_{bearing_id}: bore={spec.bore_diameter:.1f} od={spec.outer_diameter:.1f} "
        f"width={spec.width:.1f} balls={spec.ball_count} material={material.material_id}"
    )
    return bearing


def make_main_bearing_rassembly(
    *,
    bearing_id: str,
    spec: BearingSpec,
    material: scad.Material,
) -> scad.Assembly:
    """Create a uniquely identified bearing when several catalog sizes share one graph."""

    bore_radius = spec.bore_diameter / 2.0
    outer_radius = spec.outer_diameter / 2.0
    ball_radius = spec.ball_diameter / 2.0
    pitch_radius = (bore_radius + outer_radius) / 2.0
    inner_outer_radius = pitch_radius - ball_radius * 0.55
    outer_inner_radius = pitch_radius + ball_radius * 0.55
    inner_ring = make_annulus_rsolid(
        outer_radius=inner_outer_radius,
        inner_radius=bore_radius,
        bottom_z=-spec.width / 2.0,
        height=spec.width,
        tags=("role.bearing_inner_ring",),
    )
    outer_ring = make_annulus_rsolid(
        outer_radius=outer_radius,
        inner_radius=outer_inner_radius,
        bottom_z=-spec.width / 2.0,
        height=spec.width,
        tags=("role.bearing_outer_ring",),
    )
    ball = scad.make_sphere_rsolid(
        radius=ball_radius,
        center=(pitch_radius, 0.0, 0.0),
    )
    inner_part = make_axis_part_rpart(
        part_id=f"{bearing_id}_inner_ring",
        body=inner_ring,
        name=f"{bearing_id} inner race",
        material=material,
        connectors=(("axis", (0.0, 0.0, 0.0), "Inner-ring axis"),),
    )
    outer_part = make_axis_part_rpart(
        part_id=f"{bearing_id}_outer_ring",
        body=outer_ring,
        name=f"{bearing_id} outer race",
        material=material,
        connectors=(("axis", (0.0, 0.0, 0.0), "Outer-ring axis"),),
    )
    ball_part = make_axis_part_rpart(
        part_id=f"{bearing_id}_reusable_ball",
        body=ball,
        name=f"{bearing_id} reusable rolling element",
        material=material,
        connectors=(),
    )
    bearing = scad.make_assembly_rassembly(
        assembly_id=bearing_id,
        name=f"Ball bearing {spec.bore_diameter:g}x{spec.outer_diameter:g}x{spec.width:g}",
    )
    bearing = scad.add_component_rassembly(
        assembly=bearing,
        item=outer_part,
        component_id="outer_ring",
        placement=scad.identity_placement_rplacement(),
        name="Outer ring",
    )
    bearing = scad.add_component_rassembly(
        assembly=bearing,
        item=inner_part,
        component_id="inner_ring",
        placement=scad.identity_placement_rplacement(),
        name="Inner ring",
    )
    for index in range(spec.ball_count):
        angle = 360.0 * index / spec.ball_count
        bearing = scad.add_component_rassembly(
            assembly=bearing,
            item=ball_part,
            component_id=f"ball_{index + 1:02d}",
            placement=make_z_rotation_rplacement(origin=(0.0, 0.0, 0.0), angle_degrees=angle),
            name=f"Rolling element {index + 1}",
        )
    bearing = scad.add_revolute_constraint_rassembly(
        assembly=bearing,
        constraint_id="inner_outer_revolute",
        connector_a=scad.make_connector_ref_rconnectorref(
            component_id="outer_ring",
            connector_id="axis",
        ),
        connector_b=scad.make_connector_ref_rconnectorref(
            component_id="inner_ring",
            connector_id="axis",
        ),
        drive_angle_degrees=None,
        angle_limit=None,
        name="Inner ring rotation in outer ring",
    )
    for connector_id, component_id in (("outer_axis", "outer_ring"), ("inner_axis", "inner_ring")):
        bearing = scad.forward_connector_rassembly(
            assembly=bearing,
            connector_id=connector_id,
            source_component_id=component_id,
            source_connector_id="axis",
            name=connector_id.replace("_", " "),
            offset=None,
        )
    radial_wall = (spec.outer_diameter - spec.bore_diameter) / 2.0 - spec.ball_diameter
    axial_margin = spec.width - spec.ball_diameter
    print(
        f"bearing_{bearing_id}: bore={spec.bore_diameter:.1f} od={spec.outer_diameter:.1f} "
        f"width={spec.width:.1f} balls={spec.ball_count} radial_wall={radial_wall:.2f} "
        f"axial_margin={axial_margin:.2f}"
    )
    return bearing


def make_coaxial_bearing_rplacement(*, center_z: float) -> scad.Placement:
    """Place a standard bearing center plane on the actuator Z axis."""

    return make_z_rotation_rplacement(origin=(0.0, 0.0, center_z), angle_degrees=0.0)


def make_planet_bearing_rplacement(
    *,
    stage: StageSpec,
    index: int,
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
        origin=(center[0], center[1], stage.mid_z),
        angle_degrees=0.0,
    )
