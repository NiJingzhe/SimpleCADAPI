"""Refine the Gmsh/CalculiX mesh until two adjacent response pairs form a platform."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import sys
import subprocess
from typing import Sequence

EXAMPLE_DIR = Path(__file__).resolve().parent
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from export_fem_mesh import PACKAGE_PATH, STEP_PATH, mesh_step_with_gmsh
from run_calculix import DEFAULT_LOAD_Z_N, build_calculix_input, run_calculix_static


OUT_DIR = EXAMPLE_DIR.parent / "out" / "ap242_gmsh_volume_mesh"
STUDY_DIR = OUT_DIR / "mesh_convergence"
REPORT_PATH = STUDY_DIR / "mesh_convergence.json"
CSV_PATH = STUDY_DIR / "mesh_convergence.csv"
DEFAULT_MESH_SIZES = (3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.375, 0.3, 0.28, 0.27, 0.25)
DISPLACEMENT_TOLERANCE = 0.05
STRESS_TOLERANCE = 0.10
REQUIRED_PLATFORM_PAIRS = 3

@dataclass(frozen=True, slots=True)
class MeshConvergenceLevel:
    mesh_size_mm: float
    node_count: int
    element_count: int
    fixed_node_count: int
    load_node_count: int
    max_displacement_mm: float
    max_von_mises_mpa: float
    reaction_force_z_n: float
    force_balance_z_n: float
    displacement_change_from_previous: float | None
    stress_change_from_previous: float | None
    mesh_path: str
    input_path: str
    summary_path: str
    linear_solver: str = "SPOOLES"


def _slug(mesh_size: float) -> str:
    return f"h{mesh_size:g}".replace(".", "p")


def _relative_change(current: float, previous: float) -> float:
    return abs(current - previous) / max(abs(current), 1.0e-30)


def _pair_is_converged(
    level: MeshConvergenceLevel,
    *,
    displacement_tolerance: float,
    stress_tolerance: float,
) -> bool:
    return (
        level.displacement_change_from_previous is not None
        and level.stress_change_from_previous is not None
        and level.displacement_change_from_previous <= displacement_tolerance
        and level.stress_change_from_previous <= stress_tolerance
    )


def assess_mesh_convergence(
    levels: Sequence[MeshConvergenceLevel],
    *,
    displacement_tolerance: float = DISPLACEMENT_TOLERANCE,
    stress_tolerance: float = STRESS_TOLERANCE,
    required_platform_pairs: int = REQUIRED_PLATFORM_PAIRS,
) -> dict[str, object]:
    """Recommend N-1 only after N confirms a sustained response platform."""

    if len(levels) < 3:
        raise ValueError("mesh convergence requires at least three refinement levels")
    if required_platform_pairs < 1:
        raise ValueError("required_platform_pairs must be positive")
    converged_pairs = [
        _pair_is_converged(
            level,
            displacement_tolerance=displacement_tolerance,
            stress_tolerance=stress_tolerance,
        )
        for level in levels[1:]
    ]
    trailing_converged_pairs = 0
    for converged in reversed(converged_pairs):
        if not converged:
            break
        trailing_converged_pairs += 1
    platform_reached = trailing_converged_pairs >= required_platform_pairs
    finest = levels[-1]
    recommended = levels[-2] if platform_reached else None
    return {
        "displacement_tolerance": displacement_tolerance,
        "stress_tolerance": stress_tolerance,
        "required_consecutive_converged_pairs": required_platform_pairs,
        "trailing_converged_pairs": trailing_converged_pairs,
        "platform_reached": platform_reached,
        "mesh_independent": platform_reached,
        "recommended_mesh_size_mm": (
            None if recommended is None else recommended.mesh_size_mm
        ),
        "production_level_n_minus_1": (
            None if recommended is None else len(levels) - 1
        ),
        "verification_level_n": None if recommended is None else len(levels),
        "finest_pair_displacement_within_tolerance": (
            finest.displacement_change_from_previous is not None
            and finest.displacement_change_from_previous <= displacement_tolerance
        ),
        "finest_pair_stress_within_tolerance": (
            finest.stress_change_from_previous is not None
            and finest.stress_change_from_previous <= stress_tolerance
        ),
        "stress_caution": (
            None
            if platform_reached
            else "No sustained platform was observed; peak stress may be mesh-sensitive or singular."
        ),
    }


def run_mesh_convergence_study(
    *,
    mesh_sizes: Sequence[float] = DEFAULT_MESH_SIZES,
    ccx: str | Path | None = None,
    load_z_n: float = DEFAULT_LOAD_Z_N,
    study_dir: str | Path = STUDY_DIR,
    displacement_tolerance: float = DISPLACEMENT_TOLERANCE,
    stress_tolerance: float = STRESS_TOLERANCE,
    required_platform_pairs: int = REQUIRED_PLATFORM_PAIRS,
    solver_timeout_seconds: float = 300.0,
    linear_solver: str = "SPOOLES",
    resume_report: str | Path | None = None,
) -> dict[str, object]:
    if len(mesh_sizes) < 3:
        raise ValueError("provide at least three mesh sizes")
    sizes = tuple(float(value) for value in mesh_sizes)
    if any(not math.isfinite(value) or value <= 0.0 for value in sizes):
        raise ValueError("mesh sizes must be finite and positive")
    if any(first <= second for first, second in zip(sizes, sizes[1:])):
        raise ValueError("mesh sizes must be strictly decreasing from coarse to fine")
    if (
        not math.isfinite(displacement_tolerance)
        or displacement_tolerance <= 0.0
        or not math.isfinite(stress_tolerance)
        or stress_tolerance <= 0.0
    ):
        raise ValueError("convergence tolerances must be finite and positive")
    if required_platform_pairs < 1:
        raise ValueError("required_platform_pairs must be positive")
    if not math.isfinite(solver_timeout_seconds) or solver_timeout_seconds <= 0.0:
        raise ValueError("solver_timeout_seconds must be finite and positive")

    destination = Path(study_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    levels: list[MeshConvergenceLevel] = []
    failed_levels: list[dict[str, object]] = []
    if resume_report is not None:
        resume_path = Path(resume_report).expanduser().resolve()
        resume_payload = json.loads(resume_path.read_text(encoding="utf-8"))
        levels = [
            MeshConvergenceLevel(
                **({"linear_solver": "SPOOLES"} | item)
            )
            for item in resume_payload["levels"]
        ]
        failed_levels = list(resume_payload.get("failed_levels", []))
        completed_sizes = tuple(level.mesh_size_mm for level in levels)
        if completed_sizes != sizes[: len(completed_sizes)]:
            raise ValueError("resume report levels must be a prefix of mesh_sizes")
        if not math.isclose(
            float(resume_payload["load_z_n"]),
            load_z_n,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        ):
            raise ValueError("resume report load_z_n does not match this study")

    previous_displacement = None if not levels else levels[-1].max_displacement_mm
    previous_stress = None if not levels else levels[-1].max_von_mises_mpa
    converged_pair_streak = 0
    for completed_level in reversed(levels[1:]):
        if not _pair_is_converged(
            completed_level,
            displacement_tolerance=displacement_tolerance,
            stress_tolerance=stress_tolerance,
        ):
            break
        converged_pair_streak += 1

    for mesh_size in sizes[len(levels) :]:
        slug = _slug(mesh_size)
        mesh_path = destination / f"bracket_{slug}.msh"
        mapping_path = destination / f"bracket_{slug}.gmsh.json"
        input_path = destination / f"bracket_{slug}.inp"
        summary_path = destination / f"bracket_{slug}.calculix.json"
        if mesh_path.is_file() and resume_report is not None:
            print("mesh_reuse", mesh_path)
        else:
            mesh_step_with_gmsh(
                STEP_PATH,
                mesh_path,
                package_path=PACKAGE_PATH,
                mapping_path=mapping_path,
                mesh_size=mesh_size,
            )
        input_report = build_calculix_input(
            mesh_path,
            input_path,
            load_z_n=load_z_n,
            linear_solver=linear_solver,
        )
        failed_levels = [
            failure
            for failure in failed_levels
            if float(failure["mesh_size_mm"]) != mesh_size
        ]
        try:
            result = run_calculix_static(
                input_report,
                ccx=ccx,
                summary_path=summary_path,
                timeout_seconds=solver_timeout_seconds,
            )
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            failure = {
                "mesh_size_mm": mesh_size,
                "mesh_path": str(mesh_path),
                "input_path": str(input_path),
                "linear_solver": linear_solver,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            failed_levels.append(failure)
            print("mesh_level_failed", json.dumps(failure, sort_keys=True))
            break
        displacement_change = (
            None
            if previous_displacement is None
            else _relative_change(result.max_displacement_mm, previous_displacement)
        )
        stress_change = (
            None
            if previous_stress is None
            else _relative_change(result.max_von_mises_mpa, previous_stress)
        )
        level = MeshConvergenceLevel(
            mesh_size_mm=mesh_size,
            node_count=input_report.node_count,
            element_count=input_report.element_count,
            fixed_node_count=input_report.fixed_node_count,
            load_node_count=input_report.load_node_count,
            max_displacement_mm=result.max_displacement_mm,
            max_von_mises_mpa=result.max_von_mises_mpa,
            reaction_force_z_n=result.reaction_force_z_n,
            force_balance_z_n=result.force_balance_z_n,
            linear_solver=input_report.linear_solver,
            displacement_change_from_previous=displacement_change,
            stress_change_from_previous=stress_change,
            mesh_path=str(mesh_path),
            input_path=str(input_path),
            summary_path=str(summary_path),
        )
        levels.append(level)
        print(
            "mesh_level",
            f"h={mesh_size:g}",
            f"nodes={level.node_count}",
            f"elements={level.element_count}",
            f"umax_mm={level.max_displacement_mm:.9g}",
            f"smax_mpa={level.max_von_mises_mpa:.9g}",
        )
        if _pair_is_converged(
            level,
            displacement_tolerance=displacement_tolerance,
            stress_tolerance=stress_tolerance,
        ):
            converged_pair_streak += 1
        else:
            converged_pair_streak = 0
        if converged_pair_streak >= required_platform_pairs:
            print(
                "mesh_platform",
                f"production_h={levels[-2].mesh_size_mm:g}",
                f"verification_h={mesh_size:g}",
            )
            break
        previous_displacement = result.max_displacement_mm
        previous_stress = result.max_von_mises_mpa

    assessment = assess_mesh_convergence(
        levels,
        displacement_tolerance=displacement_tolerance,
        stress_tolerance=stress_tolerance,
        required_platform_pairs=required_platform_pairs,
    )
    payload = {
        "schema_version": "1.1",
        "analysis": "linear_static_adaptive_mesh_convergence",
        "units": {"mesh_size": "mm", "displacement": "mm", "stress": "MPa"},
        "load_z_n": load_z_n,
        "requested_mesh_sizes_mm": list(sizes),
        "linear_solver_for_new_levels": linear_solver,
        "evaluated_level_count": len(levels),
        "levels": [asdict(level) for level in levels],
        "failed_levels": failed_levels,
        "assessment": assessment,
    }
    report_path = destination / REPORT_PATH.name
    csv_path = destination / CSV_PATH.name
    payload["report_path"] = str(report_path)
    payload["csv_path"] = str(csv_path)
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(asdict(levels[0])))
        writer.writeheader()
        writer.writerows(asdict(level) for level in levels)
    return payload


def main(
    *,
    ccx: str | None = None,
    mesh_sizes: Sequence[float] = DEFAULT_MESH_SIZES,
    solver_timeout_seconds: float = 300.0,
    linear_solver: str = "SPOOLES",
    required_platform_pairs: int = REQUIRED_PLATFORM_PAIRS,
    resume_report: Path | None = None,
) -> None:
    report = run_mesh_convergence_study(
        ccx=ccx,
        mesh_sizes=mesh_sizes,
        solver_timeout_seconds=solver_timeout_seconds,
        linear_solver=linear_solver,
        required_platform_pairs=required_platform_pairs,
        resume_report=resume_report,
    )
    assessment = report["assessment"]
    print("mesh_convergence_json", report["report_path"])
    print("mesh_convergence_csv", report["csv_path"])
    print("mesh_platform_reached", assessment["platform_reached"])
    print("recommended_mesh_size_mm", assessment["recommended_mesh_size_mm"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ccx")
    parser.add_argument("--solver-timeout", type=float, default=300.0)
    parser.add_argument("--linear-solver", default="SPOOLES")
    parser.add_argument(
        "--required-platform-pairs",
        type=int,
        default=REQUIRED_PLATFORM_PAIRS,
    )
    parser.add_argument("--resume", type=Path)
    parser.add_argument(
        "--mesh-sizes",
        nargs="+",
        type=float,
        default=DEFAULT_MESH_SIZES,
        metavar="MM",
    )
    arguments = parser.parse_args()
    main(
        ccx=arguments.ccx,
        mesh_sizes=arguments.mesh_sizes,
        solver_timeout_seconds=arguments.solver_timeout,
        linear_solver=arguments.linear_solver,
        required_platform_pairs=arguments.required_platform_pairs,
        resume_report=arguments.resume,
    )
