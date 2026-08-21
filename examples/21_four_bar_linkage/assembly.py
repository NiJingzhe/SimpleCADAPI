"""Four-bar linkage assembly with a closed kinematic loop.

Realistic forged links (bearing eyes, I-beam webs, lightening holes) are
joined by hex-head pivot bolts. The ground span is grounded; crank and rocker
pivot on it and the coupler closes the loop between their tips. The closing
revolute carries an angle limit so the solver can resolve the loop; MJCF
export emits the loop-closing constraint as a MuJoCo equality.

Bolts are fasteners, not kinematic bodies: each bolt is fixed to one adjacent
bar at its pivot so it shares that bar's rigid group, and the pin fits both
bores because all bar bores share the pivot axis at the assembled pose.
"""

from __future__ import annotations

import math
from pathlib import Path

import simplecadapi as scad

from dimensions import (
    CLOSURE_ANGLE_LIMIT,
    COUPLER_ASSEMBLED_ANGLE_DEG,
    COUPLER_LENGTH,
    CRANK_ASSEMBLED_ANGLE_DEG,
    CRANK_LENGTH,
    CRANK_PIVOT,
    GROUND_LENGTH,
    PIVOT_BOLT_SHANK_LENGTH,
    ROCKER_ASSEMBLED_ANGLE_DEG,
    ROCKER_LENGTH,
    ROCKER_PIVOT,
)
from link_bar import make_link_part
from pivot_bolt import make_pivot_bolt_part

CACHE = scad.CachePolicy(root=Path(__file__).resolve().parents[1] / "out" / ".cache")
MATERIAL = scad.make_material_rmaterial(
    material_id="linkage_steel",
    name="Linkage steel",
    density=7.85e-6,
    density_unit="kg/mm^3",
    color=(0.65, 0.65, 0.68),
)
BOLT_MATERIAL = scad.make_material_rmaterial(
    material_id="bolt_steel",
    name="Bolt steel",
    density=7.85e-6,
    density_unit="kg/mm^3",
    color=(0.25, 0.27, 0.30),
)


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


def _durable_parts():
    @scad.part(id="ground_span", cache=CACHE, project_root=Path(__file__).parent)
    def build_ground() -> scad.Part:
        return make_link_part("ground_span", GROUND_LENGTH, material=MATERIAL)

    @scad.part(id="crank", cache=CACHE, project_root=Path(__file__).parent)
    def build_crank() -> scad.Part:
        return make_link_part("crank", CRANK_LENGTH, material=MATERIAL)

    @scad.part(id="coupler", cache=CACHE, project_root=Path(__file__).parent)
    def build_coupler() -> scad.Part:
        return make_link_part("coupler", COUPLER_LENGTH, material=MATERIAL)

    @scad.part(id="rocker", cache=CACHE, project_root=Path(__file__).parent)
    def build_rocker() -> scad.Part:
        return make_link_part("rocker", ROCKER_LENGTH, material=MATERIAL)

    @scad.part(id="pivot_bolt", cache=CACHE, project_root=Path(__file__).parent)
    def build_bolt() -> scad.Part:
        return make_pivot_bolt_part(
            "pivot_bolt", PIVOT_BOLT_SHANK_LENGTH, material=BOLT_MATERIAL
        )
    return build_ground(), build_crank(), build_coupler(), build_rocker(), build_bolt()


def build_four_bar_linkage() -> scad.AssemblyBuildResult:
    """Build the closed four-bar linkage through durable definitions."""

    ground_r, crank_r, coupler_r, rocker_r, bolt_r = _durable_parts()

    @scad.assemble(
        id="four_bar_linkage",
        definitions=(ground_r, crank_r, coupler_r, rocker_r, bolt_r),
        cache=CACHE,
        project_root=Path(__file__).parent,
    )
    def build() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly(
            assembly_id="four_bar_linkage",
            name="Planar four-bar linkage with closed loop",
        )
        bars = (
            ("ground", ground_r, scad.identity_placement_rplacement()),
            ("crank", crank_r, _rotation_placement(CRANK_PIVOT, CRANK_ASSEMBLED_ANGLE_DEG)),
            ("rocker", rocker_r, _rotation_placement(ROCKER_PIVOT, ROCKER_ASSEMBLED_ANGLE_DEG)),
            ("coupler", coupler_r, _rotation_placement((CRANK_LENGTH, 0.0), COUPLER_ASSEMBLED_ANGLE_DEG)),
        )
        for component_id, result, placement in bars:
            assembly = scad.add_component_rassembly(
                assembly=assembly,
                item=result.part,
                component_id=component_id,
                placement=placement,
                name=component_id.replace("_", " ").title(),
            )
        # Pivot bolts: one per joint, fixed to one adjacent bar (fastener,
        # not a kinematic body), placed at the pivot on the bar's +Z face.
        bolt_joints = (
            ("bolt_a", "ground", (0.0, 0.0), "pivot_a"),
            ("bolt_d", "ground", ROCKER_PIVOT, "pivot_b"),
            ("bolt_b", "crank", (CRANK_LENGTH, 0.0), "pivot_b"),
        )
        for bolt_id, host_id, host_local_pivot, host_connector in bolt_joints:
            host_placement = next(
                placement for cid, _r, placement in bars if cid == host_id
            )
            bolt_world = scad.make_placement_rplacement(
                origin=(
                    host_placement.origin[0] + host_local_pivot[0],
                    host_placement.origin[1] + host_local_pivot[1],
                    0.0,
                )
            )
            assembly = scad.add_component_rassembly(
                assembly=assembly,
                item=bolt_r.part,
                component_id=bolt_id,
                placement=bolt_world,
                name=bolt_id.replace("_", " ").title(),
            )
            assembly = scad.add_fixed_constraint_rassembly(
                assembly=assembly,
                constraint_id=f"{bolt_id}_pin",
                connector_a=scad.make_connector_ref_rconnectorref(
                    host_id, host_connector
                ),
                connector_b=scad.make_connector_ref_rconnectorref(bolt_id, "axis"),
            )
        rocker_placement = _rotation_placement(
            ROCKER_PIVOT, ROCKER_ASSEMBLED_ANGLE_DEG
        )
        rocker_tip_world = (
            rocker_placement.origin[0] + ROCKER_LENGTH * rocker_placement.x_axis[0],
            rocker_placement.origin[1] + ROCKER_LENGTH * rocker_placement.x_axis[1],
        )
        assembly = scad.add_component_rassembly(
            assembly=assembly,
            item=bolt_r.part,
            component_id="bolt_c",
            placement=scad.make_placement_rplacement(
                origin=(rocker_tip_world[0], rocker_tip_world[1], 0.0)
            ),
            name="Bolt C",
        )
        assembly = scad.add_fixed_constraint_rassembly(
            assembly=assembly,
            constraint_id="bolt_c_pin",
            connector_a=scad.make_connector_ref_rconnectorref("rocker", "pivot_b"),
            connector_b=scad.make_connector_ref_rconnectorref("bolt_c", "axis"),
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
        solved = scad.solve_assembly_constraints_rassembly(assembly=assembly, strict=True)
        report = solved._get_runtime("constraint_report")
        print(
            f"four_bar_solved: components={len(solved.component_ids())} "
            f"constraints={len(solved.constraint_ids())} "
            f"residuals_ok={all(r['within_tolerance'] for r in report['residuals'])}"
        )
        return solved

    return build()
