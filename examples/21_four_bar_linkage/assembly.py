"""Four-bar linkage assembly with a closed kinematic loop.

The ground span is grounded; crank and rocker pivot on it and the coupler
closes the loop between their tips. The closing revolute carries an angle
limit so the solver can resolve the loop; MJCF export emits the loop-closing
constraint as a MuJoCo equality instead of silently dropping it.
"""

from __future__ import annotations

import math
from pathlib import Path

import simplecadapi as scad

from dimensions import (
    BAR_THICKNESS,
    BAR_WIDTH,
    COUPLER_ASSEMBLED_ANGLE_DEG,
    COUPLER_LENGTH,
    COUPLER_TIP,
    CRANK_ASSEMBLED_ANGLE_DEG,
    CRANK_LENGTH,
    CRANK_PIVOT,
    CLOSURE_ANGLE_LIMIT,
    GROUND_LENGTH,
    PIVOT_RADIUS,
    ROCKER_ASSEMBLED_ANGLE_DEG,
    ROCKER_LENGTH,
    ROCKER_PIVOT,
)

CACHE = scad.CachePolicy(root=Path(__file__).resolve().parents[1] / "out" / ".cache")
MATERIAL = scad.make_material_rmaterial(
    material_id="linkage_steel",
    name="Linkage steel",
    density=7.85e-6,
    density_unit="kg/mm^3",
    color=(0.65, 0.65, 0.68),
)


def _bar_between(part_id: str, start: tuple[float, float], end: tuple[float, float]) -> scad.Part:
    """One flat bar with pivot bosses at both ends, Z-axis pivot connectors."""

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    angle = math.degrees(math.atan2(dy, dx))
    body = scad.make_box_rsolid(width=length, height=BAR_WIDTH, depth=BAR_THICKNESS)
    body = scad.translate_shape(
        body, vector=(-length / 2.0, 0.0, -BAR_THICKNESS / 2.0)
    )
    body = scad.rotate_shape(body, angle, axis=(0.0, 0.0, 1.0), origin=(0.0, 0.0, 0.0))
    body = scad.translate_shape(body, vector=(start[0], start[1], 0.0))
    part = scad.make_part_rpart(part_id=part_id, body=body, name=part_id.replace("_", " "))
    part = scad.assign_material_rpart(part=part, material=MATERIAL)
    for connector_id, center in (("pivot_a", start), ("pivot_b", end)):
        part = scad.add_connector_rpart(
            part=part,
            connector=scad.make_placement_connector_rconnector(
                connector_id=connector_id,
                placement=scad.make_placement_rplacement(
                    origin=(center[0], center[1], 0.0)
                ),
            ),
        )
    return part


def _rotation_placement(origin: tuple[float, float], angle_deg: float) -> scad.Placement:
    """Place a bar's local pivot_a at *origin* with a CCW bar angle.

    The rotation applies to the bar frame about the pivot itself; the
    translation to the pivot is not rotated.
    """
    radians = math.radians(angle_deg)
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    return scad.make_placement_rplacement(
        origin=(origin[0], origin[1], 0.0),
        x_axis=(cos_a, sin_a, 0.0),
        y_axis=(-sin_a, cos_a, 0.0),
    )


def _bar_builders():
    @scad.part(id="ground_span", cache=CACHE, project_root=Path(__file__).parent)
    def build_ground() -> scad.Part:
        return _bar_between("ground_span", CRANK_PIVOT, ROCKER_PIVOT)

    @scad.part(id="crank", cache=CACHE, project_root=Path(__file__).parent)
    def build_crank() -> scad.Part:
        return _bar_between("crank", (0.0, 0.0), (CRANK_LENGTH, 0.0))

    @scad.part(id="coupler", cache=CACHE, project_root=Path(__file__).parent)
    def build_coupler() -> scad.Part:
        return _bar_between("coupler", (0.0, 0.0), (COUPLER_LENGTH, 0.0))

    @scad.part(id="rocker", cache=CACHE, project_root=Path(__file__).parent)
    def build_rocker() -> scad.Part:
        return _bar_between("rocker", (0.0, 0.0), (ROCKER_LENGTH, 0.0))

    return build_ground(), build_crank(), build_coupler(), build_rocker()


def build_four_bar_linkage() -> scad.AssemblyBuildResult:
    """Build the closed four-bar linkage through durable definitions."""

    ground_r, crank_r, coupler_r, rocker_r = _bar_builders()

    @scad.assemble(
        id="four_bar_linkage",
        definitions=(ground_r, crank_r, coupler_r, rocker_r),
        cache=CACHE,
        project_root=Path(__file__).parent,
    )
    def build() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly(
            assembly_id="four_bar_linkage",
            name="Planar four-bar linkage with closed loop",
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=ground_r.part,
            component_id="ground",
            placement=scad.identity_placement_rplacement(),
            name="Ground span",
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=crank_r.part,
            component_id="crank",
            placement=_rotation_placement(CRANK_PIVOT, CRANK_ASSEMBLED_ANGLE_DEG),
            name="Crank",
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=rocker_r.part,
            component_id="rocker",
            placement=_rotation_placement(ROCKER_PIVOT, ROCKER_ASSEMBLED_ANGLE_DEG),
            name="Rocker",
        )
        # Coupler pivot_a sits at the crank tip, rotated to the coupler line
        # angle so pivot_b lands on the rocker tip in the assembled pose.
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=coupler_r.part,
            component_id="coupler",
            placement=_rotation_placement(
                (CRANK_LENGTH, 0.0), COUPLER_ASSEMBLED_ANGLE_DEG
            ),
            name="Coupler",
        )
        assembly = scad.ground_component_rassembly(
            assembly=assembly, component_id="ground"
        )
        # Drive angles stay None: the authored closed pose is the reference,
        # and a non-None drive would rotate a bar to a zero-relative-frame
        # pose that conflicts with the loop closure.
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id="crank_to_ground",
            connector_a=scad.make_connector_ref_rconnectorref("ground", "pivot_a"),
            connector_b=scad.make_connector_ref_rconnectorref("crank", "pivot_a"),
        )
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id="rocker_to_ground",
            connector_a=scad.make_connector_ref_rconnectorref("ground", "pivot_b"),
            connector_b=scad.make_connector_ref_rconnectorref("rocker", "pivot_a"),
        )
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id="coupler_to_crank",
            connector_a=scad.make_connector_ref_rconnectorref("crank", "pivot_b"),
            connector_b=scad.make_connector_ref_rconnectorref("coupler", "pivot_a"),
        )
        assembly = scad.add_revolute_constraint_rassembly(
            assembly=assembly,
            constraint_id="coupler_to_rocker",
            connector_a=scad.make_connector_ref_rconnectorref("rocker", "pivot_b"),
            connector_b=scad.make_connector_ref_rconnectorref("coupler", "pivot_b"),
            angle_limit=scad.make_scalar_limit_rscalarlimit(
                lower_value=CLOSURE_ANGLE_LIMIT[0],
                upper_value=CLOSURE_ANGLE_LIMIT[1],
            ),
        )
        assembly = scad.set_public_connector_rassembly(
            assembly=assembly,
            public_connector_id="crank_input_axis",
            source_component_id="crank",
            source_connector_id="pivot_a",
            name="Crank input axis",
        )
        return scad.solve_assembly_constraints_rassembly(assembly=assembly, strict=True)

    return build()
