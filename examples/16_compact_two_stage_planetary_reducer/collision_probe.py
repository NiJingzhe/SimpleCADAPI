"""Run static collision verification on the compact reducer example.

Run from the repository root with:
    uv run python examples/16_compact_two_stage_planetary_reducer/collision_probe.py

This probe builds the solved reducer assembly without exporting STEP/FCStd, then
checks the current pose with ``scad.verifier.check_collision_rcollisionreport``.
The current verifier uses FCL-reported mesh contact penetration only; it does
not handle complete containment cases.
"""

from __future__ import annotations

import contextlib
import io
import sys
import time

import simplecadapi as scad

if __package__:
    from .main import _build_compact_two_stage_planetary_reducer
else:
    from main import _build_compact_two_stage_planetary_reducer


sys.setrecursionlimit(30000)


def _build_reducer_quietly() -> tuple[scad.Assembly, int, float]:
    log_buffer = io.StringIO()
    start = time.perf_counter()
    with contextlib.redirect_stdout(log_buffer):
        result = _build_compact_two_stage_planetary_reducer()
        assembly, _preview = result.value
    elapsed = time.perf_counter() - start
    return assembly, len(log_buffer.getvalue().splitlines()), elapsed


def main() -> None:
    assembly, log_lines, build_seconds = _build_reducer_quietly()

    start = time.perf_counter()
    report = scad.verifier.check_collision_rcollisionreport(
        assembly=assembly,
        config=scad.verifier.CollisionCheckConfig(
            max_allowed_penetration=0.02,
            max_contacts_per_pair=16,
        ),
    )
    check_seconds = time.perf_counter() - start

    print("assembly", assembly.assembly_id)
    print("build_log_lines", log_lines)
    print("build_seconds", round(build_seconds, 3))
    print("check_seconds", round(check_seconds, 3))
    print("completed", report.completed)
    print("passed", report.passed)
    print("checked_pair_count", report.checked_pair_count)
    print("failed_pair_count", report.failed_pair_count)
    print("warning_count", len(report.warnings))

    for warning in report.warnings[:20]:
        path = "/".join(warning.component_path or ())
        print("warning", warning.code, path, warning.message)

    for failure in sorted(
        report.failures,
        key=lambda item: item.penetration_depth,
        reverse=True,
    )[:20]:
        print(
            "failure",
            "/".join(failure.component_a),
            "/".join(failure.component_b),
            "depth",
            round(failure.penetration_depth, 4),
            "contacts",
            len(failure.contacts),
        )


if __name__ == "__main__":
    main()
