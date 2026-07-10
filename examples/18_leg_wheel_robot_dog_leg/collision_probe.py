"""Static current-pose collision probe for Example 18.

Run from the repository root with:
    uv run python examples/18_leg_wheel_robot_dog_leg/collision_probe.py

The probe intentionally checks the visible packaging surfaces and leg links, not
every internal reducer gear.  The reducer core is already checked in Example 16;
this probe is for leg-level interferences such as links buried inside actuator
cases, motor cans, wheel forks, and four-bar rods.
"""

from __future__ import annotations

import contextlib
import io
import sys
import time

import simplecadapi as scad

from leg_assembly import make_leg_wheel_robot_dog_leg_rassembly


ACTUATOR_IDS = (
    "thigh_actuator",
    "knee_drive_actuator",
    "wheel_hub_actuator",
)
EXTERNAL_ACTUATOR_LEAVES = (
    ("reducer", "housing"),
    ("reducer", "input_flange"),
    ("reducer", "output_flange"),
    ("motor_can",),
)
LINK_LEAVES = (
    ("body_mount_plate",),
    ("upper_link_plate",),
    ("proximal_output_crank",),
    ("knee_pushrod",),
    ("shank_link",),
    ("wheel_tire",),
)


def _leg_level_component_paths() -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for actuator_id in ACTUATOR_IDS:
        for leaf in EXTERNAL_ACTUATOR_LEAVES:
            paths.append((actuator_id, *leaf))
    paths.extend(LINK_LEAVES)
    return tuple(paths)


def main() -> None:
    sys.setrecursionlimit(40000)
    build_log = io.StringIO()
    start = time.perf_counter()
    with contextlib.redirect_stdout(build_log):
        assembly = make_leg_wheel_robot_dog_leg_rassembly()
    build_seconds = time.perf_counter() - start

    config = scad.verifier.CollisionCheckConfig(
        max_allowed_penetration=0.05,
        max_contacts_per_pair=32,
        scope=scad.verifier.CollisionScope(
            component_paths=_leg_level_component_paths(),
        ),
    )
    start = time.perf_counter()
    report = scad.verifier.check_collision_rcollisionreport(
        assembly=assembly,
        config=config,
    )
    check_seconds = time.perf_counter() - start

    print(f"assembly {assembly.assembly_id}")
    print(f"build_log_lines {len(build_log.getvalue().splitlines())}")
    print(f"build_seconds {build_seconds:.3f}")
    print(f"check_seconds {check_seconds:.3f}")
    print(f"completed {report.completed}")
    print(f"passed {report.passed}")
    print(f"checked_pair_count {report.checked_pair_count}")
    print(f"failed_pair_count {report.failed_pair_count}")
    print(f"warning_count {len(report.warnings)}")
    for warning in report.warnings:
        path = "/".join(warning.component_path or ())
        print(f"warning {path} {warning.code} {warning.message}")
    for failure in sorted(report.failures, key=lambda item: item.penetration_depth, reverse=True)[:25]:
        print(
            "failure",
            "/".join(failure.component_a),
            "/".join(failure.component_b),
            f"depth={failure.penetration_depth:.3f}",
            f"allowed={failure.allowed_penetration:.3f}",
        )


if __name__ == "__main__":
    main()
