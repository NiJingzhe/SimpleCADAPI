"""Static external-envelope collision probe for the rebuilt Example 18."""

from __future__ import annotations

import contextlib
import io
import sys
import time

import simplecadapi as scad

from actuator import make_actuator_materials_rdict
from leg_assembly import make_leg_wheel_robot_dog_leg_rassembly
from leg_materials import make_leg_materials_rdict


ACTUATOR_IDS = (
    "thigh_actuator",
    "knee_drive_actuator",
    "wheel_hub_actuator",
)
EXTERNAL_ACTUATOR_LEAVES = (
    ("reducer_housing",),
    ("motor_shell",),
    ("rear_electronics_cover",),
    ("output_bearing_cap",),
    ("output_carrier",),
    ("controller", "three_phase_terminal"),
    ("controller", "power_can_terminal"),
)
TOP_LEVEL_EXTERNALS = (
    "body_mount_plate",
    "upper_link_plate",
    "proximal_output_crank",
    "knee_pushrod",
    "shank_link",
    "wheel_hub",
    "wheel_tire",
    "knee_bushing",
    "knee_axle",
    "thigh_clamp_bolt",
    "knee_drive_clamp_bolt",
    "wheel_clamp_bolt",
    "proximal_linkage_pin",
    "distal_linkage_pin",
)


def _leg_level_component_paths() -> tuple[tuple[str, ...], ...]:
    paths: list[tuple[str, ...]] = []
    for actuator_id in ACTUATOR_IDS:
        for leaf in EXTERNAL_ACTUATOR_LEAVES:
            if leaf == ("output_carrier",):
                paths.append((actuator_id, *leaf))
            else:
                paths.append((actuator_id, "fixed_body", *leaf))
    paths.extend((component_id,) for component_id in TOP_LEVEL_EXTERNALS)
    for interface in ("thigh", "knee_drive", "wheel"):
        paths.extend((f"{interface}_output_screw_{index}",) for index in range(1, 7))
    return tuple(paths)


def _intentional_mating_pairs() -> tuple[scad.verifier.ComponentPair, ...]:
    pairs = [
        scad.verifier.ComponentPair("wheel_hub", "wheel_tire"),
        scad.verifier.ComponentPair("body_mount_plate", "thigh_clamp_bolt"),
        scad.verifier.ComponentPair("body_mount_plate", "knee_drive_clamp_bolt"),
        scad.verifier.ComponentPair("shank_link", "wheel_clamp_bolt"),
    ]
    for actuator_id in ACTUATOR_IDS:
        pairs.append(
            scad.verifier.ComponentPair(
                (actuator_id, "fixed_body", "reducer_housing"),
                (actuator_id, "fixed_body", "output_bearing_cap"),
            )
        )
    for interface, actuator_id, driven_component_id in (
        ("thigh", "thigh_actuator", "upper_link_plate"),
        ("knee_drive", "knee_drive_actuator", "proximal_output_crank"),
        ("wheel", "wheel_hub_actuator", "wheel_hub"),
    ):
        pairs.append(
            scad.verifier.ComponentPair(
                (actuator_id, "output_carrier"),
                driven_component_id,
            )
        )
        for index in range(1, 7):
            pairs.append(
                scad.verifier.ComponentPair(
                    f"{interface}_output_screw_{index}",
                    (actuator_id, "output_carrier"),
                )
            )
    return tuple(pairs)


def main() -> None:
    sys.setrecursionlimit(40000)
    build_log = io.StringIO()
    start = time.perf_counter()
    with contextlib.redirect_stdout(build_log):
        assembly = make_leg_wheel_robot_dog_leg_rassembly(
            actuator_materials=make_actuator_materials_rdict(),
            leg_materials=make_leg_materials_rdict(),
        )
    build_seconds = time.perf_counter() - start

    config = scad.verifier.CollisionCheckConfig(
        max_allowed_penetration=0.08,
        max_contacts_per_pair=32,
        scope=scad.verifier.CollisionScope(
            component_paths=_leg_level_component_paths(),
            exclude_pairs=_intentional_mating_pairs(),
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
    for failure in sorted(
        report.failures,
        key=lambda item: item.penetration_depth,
        reverse=True,
    )[:25]:
        print(
            "failure",
            "/".join(failure.component_a),
            "/".join(failure.component_b),
            f"depth={failure.penetration_depth:.3f}",
            f"allowed={failure.allowed_penetration:.3f}",
        )


if __name__ == "__main__":
    main()
