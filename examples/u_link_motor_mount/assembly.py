"""u_link assembly: upper body + lower shell, shell fixed onto split plane.

Both parts modeled in install position -> identity placements, zero-residual
fixed constraint through placement connectors (z axes -Y, origin on 7.5 plane).
"""
from __future__ import annotations

import sys
from pathlib import Path

import simplecadapi as scad

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shell import build_shell_part  # noqa: E402
from u_link import build_u_link_part  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_u_link_assembly() -> scad.AssemblyBuildResult:
    body_result = build_u_link_part()
    shell_result = build_shell_part()
    definitions = (body_result, shell_result)
    parts = {r.part.part_id: r.part for r in definitions}

    @scad.assemble(
        id="u-link-motor-mount-assembly",
        revision="1.0.0",
        definitions=definitions,
        cache="off",
        project_root=PROJECT_ROOT,
    )
    def build() -> scad.Assembly:
        assembly = scad.make_assembly_rassembly(
            assembly_id="u-link-motor-mount-assembly",
            name="U link body + shell",
        )
        identity = scad.identity_placement_rplacement()
        assembly = scad.add_component_rassembly(
            assembly=assembly, item=parts["u-link-motor-mount"],
            component_id="body", placement=identity, name="U link upper body")
        assembly = scad.add_component_rassembly(
            assembly=assembly, item=parts["u-link-shell"],
            component_id="shell", placement=identity, name="U link shell")
        assembly = scad.ground_component_rassembly(assembly=assembly, component_id="body")
        assembly = scad.add_fixed_constraint_rassembly(
            assembly=assembly,
            constraint_id="shell_on_split",
            connector_a=scad.make_connector_ref_rconnectorref(
                component_id="body", connector_id="back_datum"),
            connector_b=scad.make_connector_ref_rconnectorref(
                component_id="shell", connector_id="shell_rim"),
        )
        solved = scad.solve_assembly_constraints_rassembly(assembly=assembly, strict=True)
        report = solved._get_runtime("constraint_report")
        residuals_ok = all(r["within_tolerance"] for r in report["residuals"])
        print(f"assembly solved: components={len(solved.component_ids())} "
              f"residuals_ok={residuals_ok}")
        assert residuals_ok, f"assembly residuals out of tolerance: {report['residuals']}"
        return solved

    return build()


if __name__ == "__main__":
    result = build_u_link_assembly()
    print(f"assembly ok: {result.value.assembly_id} components={len(result.value.component_ids())}")
