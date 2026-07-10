"""Example 17: static current-pose collision verification.

Run from the repository root with:
    uv run python examples/17_static_collision_verifier.py

This example checks the current placements of two box components. The verifier
uses internal cached meshes and python-fcl to report mesh contact penetration
deeper than the configured tolerance. It does not solve constraints or detect
complete containment cases.
"""

from __future__ import annotations

import simplecadapi as scad


def _box_part() -> scad.Part:
    body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
    return scad.make_part_rpart(part_id="unit_box", body=body)


def _assembly_with_offset(offset: tuple[float, float, float]) -> scad.Assembly:
    part = _box_part()
    assembly = scad.make_assembly_rassembly(assembly_id="static_collision_demo")
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="box_a",
        placement=scad.identity_placement_rplacement(),
    )
    assembly = scad.add_component_rassembly(
        assembly=assembly,
        item=part,
        component_id="box_b",
        placement=scad.make_placement_rplacement(origin=offset),
    )
    return assembly


def _print_report(label: str, report: scad.verifier.CollisionReport) -> None:
    print(label, f"completed={report.completed}", f"passed={report.passed}")
    print(label, f"checked_pairs={report.checked_pair_count}", f"failures={report.failed_pair_count}")
    for failure in report.failures:
        print(
            label,
            "failure",
            "/".join(failure.component_a),
            "/".join(failure.component_b),
            f"depth={failure.penetration_depth:.4f}",
            f"allowed={failure.allowed_penetration:.4f}",
        )
    for warning in report.warnings:
        print(label, "warning", warning.code, warning.message)


def main() -> None:
    config = scad.verifier.CollisionCheckConfig(max_allowed_penetration=0.01)

    separated = _assembly_with_offset(offset=(2.0, 0.0, 0.0))
    separated_report = scad.verifier.check_collision_rcollisionreport(
        assembly=separated,
        config=config,
    )
    _print_report("separated", separated_report)

    overlapping = _assembly_with_offset(offset=(0.5, 0.0, 0.0))
    overlapping_report = scad.verifier.check_collision_rcollisionreport(
        assembly=overlapping,
        config=config,
    )
    _print_report("overlapping", overlapping_report)


if __name__ == "__main__":
    main()
