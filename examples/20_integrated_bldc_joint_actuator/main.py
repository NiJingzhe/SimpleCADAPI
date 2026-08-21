"""Build the integrated BLDC joint actuator and capture its product package."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import simplecadapi as scad

try:
    from .assembly import build_integrated_bldc_joint_actuator as build_durable_actuator
    from .dimensions import (
        PACKAGE_RADIUS,
        PACKAGE_STRUCTURAL_BOTTOM_Z,
        PACKAGE_TOP_Z,
        TOTAL_REDUCTION,
        validate_design_dimensions,
    )
except ImportError:  # Support direct execution from this example directory.
    from assembly import build_integrated_bldc_joint_actuator as build_durable_actuator
    from dimensions import (
        PACKAGE_RADIUS,
        PACKAGE_STRUCTURAL_BOTTOM_Z,
        PACKAGE_TOP_Z,
        TOTAL_REDUCTION,
        validate_design_dimensions,
    )


sys.setrecursionlimit(30000)

OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "integrated_bldc_joint_actuator"

# STEP, MJCF, and FreeCAD exports read meshes and feature graphs from the
# definition closure, so the tessellated Scene projection is skipped here.
INCLUDE_SCENE = False


class _StageTimer:
    """Print one line per pipeline stage with elapsed seconds."""

    def __init__(self) -> None:
        self._stage_start = time.perf_counter()
        self._run_start = self._stage_start

    def mark(self, label: str) -> None:
        now = time.perf_counter()
        print(f"[stage] {label}: {now - self._stage_start:.1f}s (total {now - self._run_start:.1f}s)", flush=True)
        self._stage_start = now


def build_integrated_bldc_joint_actuator() -> scad.AssemblyBuildResult:
    """Build the actuator through durable part and assembly boundaries."""

    validate_design_dimensions()
    return build_durable_actuator()


def main() -> None:
    """Build the actuator and capture the durable `.scadpkg`."""

    timer = _StageTimer()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    package_path = OUT_DIR / "integrated_bldc_joint_actuator.scadpkg"

    product_result = build_integrated_bldc_joint_actuator()
    assembly = product_result.value
    timer.mark("build")

    scad.capture(product_result, package_path, include_scene=INCLUDE_SCENE)
    print(f"[stage] package_bytes={package_path.stat().st_size}", flush=True)
    timer.mark("capture")

    print(f"envelope_diameter={PACKAGE_RADIUS * 2.0:.1f}")
    print(f"structural_length={PACKAGE_TOP_Z - PACKAGE_STRUCTURAL_BOTTOM_Z:.1f}")
    print(f"total_reduction={TOTAL_REDUCTION:.1f}")
    print(f"assembly={assembly.assembly_id}")
    print(f"components={len(assembly.component_ids())}")
    print(f"constraints={len(assembly.constraint_ids())}")
    print(f"product_package={package_path}")


if __name__ == "__main__":
    main()
