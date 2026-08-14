"""Trusted-side comparison bundle and result classification for benchmarks."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping


def _relative_error(current: float, target: float) -> float:
    return abs(float(current) - float(target)) / max(abs(float(target)), 1.0e-12)


def _stage(
    *,
    name: str,
    request: Mapping[str, Any],
    output_directory: Path,
    timeout_seconds: float,
    python_executable: str,
) -> dict[str, Any]:
    """Execute one OCP-heavy evaluation stage with a hard process timeout."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError("stage name must be a filename-safe token")
    if output_directory.is_symlink():
        raise ValueError("output_directory must not be a symbolic link")
    output_directory = output_directory.resolve()
    if not output_directory.is_dir():
        raise ValueError("output_directory must be an existing directory")
    stage_directory = Path(
        tempfile.mkdtemp(prefix=f"{name}-", dir=output_directory)
    )
    request_path = stage_directory / "request.json"
    report_path = stage_directory / "report.json"
    stdout_path = stage_directory / "stdout.log"
    stderr_path = stage_directory / "stderr.log"
    with request_path.open("x", encoding="utf-8") as request_stream:
        request_stream.write(json.dumps(dict(request), indent=2))
    started = time.perf_counter()
    trusted_src = Path(__file__).resolve().parents[3]
    bootstrap = (
        "import runpy,sys;"
        "sys.path.insert(0,sys.argv.pop(1));"
        "runpy.run_module('simplecadapi.inverse_engineer.brep.worker',"
        "run_name='__main__')"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"PYTHONPATH", "PYTHONSTARTUP"}
    }
    environment["PYTHONUTF8"] = "1"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        try:
            process = subprocess.run(
                [
                    python_executable,
                    "-I",
                    "-c",
                    bootstrap,
                    str(trusted_src),
                    str(request_path),
                    str(report_path),
                ],
                cwd=trusted_src,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "gate_passed": False,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "report": None,
                "report_path": None,
                "error": f"evaluation stage timed out after {timeout_seconds} seconds",
            }
    elapsed = round(time.perf_counter() - started, 3)
    if process.returncode != 0:
        error = stderr_path.read_text(encoding="utf-8", errors="replace").strip()
        return {
            "status": "error",
            "gate_passed": False,
            "elapsed_seconds": elapsed,
            "report": None,
            "report_path": None,
            "error": error or f"worker exited with code {process.returncode}",
        }
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "status": "error",
            "gate_passed": False,
            "elapsed_seconds": elapsed,
            "report": None,
            "report_path": None,
            "error": f"worker produced an invalid report: {error}",
        }
    return {
        "status": "completed",
        "gate_passed": None,
        "elapsed_seconds": elapsed,
        "report": report,
        "report_path": str(report_path),
        "error": None,
    }


def inspect_benchmark_step(
    path: str | Path,
    *,
    name: str,
    output_directory: str | Path,
    timeout_seconds: float,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    """Inspect one candidate or target STEP in a bounded worker process."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    result = _stage(
        name=name,
        request={"task": "inspect", "current": str(Path(path).resolve())},
        output_directory=output,
        timeout_seconds=timeout_seconds,
        python_executable=python_executable,
    )
    if result["status"] == "completed":
        report = result["report"]
        result["gate_passed"] = bool(report.get("valid"))
        result["status"] = "passed" if result["gate_passed"] else "failed"
    return result


def _finalize_stage(
    result: dict[str, Any], checks: Mapping[str, bool]
) -> dict[str, Any]:
    if result["status"] == "error":
        return result
    result["checks"] = dict(checks)
    result["gate_passed"] = all(checks.values())
    result["status"] = "passed" if result["gate_passed"] else "failed"
    return result


def _strict_material_equal(report: Mapping[str, Any], tolerance: float) -> bool:
    volume_balance = report.get("volume_balance")
    return bool(
        report.get("method") == "bidirectional_cut"
        and report.get("strict_equality_supported") is True
        and report.get("boolean_result_valid") is True
        and isinstance(volume_balance, Mapping)
        and volume_balance.get("valid") is True
        and float(report["missing_material"]["volume"]) < tolerance
        and float(report["excess_material"]["volume"]) < tolerance
    )


def run_comparison_bundle(
    config: Any,
    *,
    target_path: str | Path,
    candidate_path: str | Path,
    output_directory: str | Path,
    diagnostics: bool = False,
    strict_topology: bool = False,
    python_executable: str = sys.executable,
) -> dict[str, dict[str, Any]]:
    """Run acceptance proof, with geometric diagnostics only when requested."""

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    target = str(Path(target_path).resolve())
    current = str(Path(candidate_path).resolve())
    stages: dict[str, dict[str, Any]] = {}

    global_stage = _stage(
        name="global",
        request={"task": "global", "target": target, "current": current},
        output_directory=output,
        timeout_seconds=config.stage_timeout_seconds,
        python_executable=python_executable,
    )
    if global_stage["status"] != "error":
        report = global_stage["report"]
        checks = {
            "bounding_box": report["bounding_box"]["max_absolute_coordinate_delta"]
            <= config.global_max_bbox_delta,
            "centroid": report["centroid"]["distance"]
            <= config.global_max_centroid_distance,
            "surface_area": abs(report["surface_area"]["relative_delta"])
            <= config.global_max_relative_area_error,
        }
        if config.target_kind == "solid":
            checks.update(
                {
                    "material_body_count": report["material_body_count"]["delta"]
                    == 0,
                    "volume": abs(report["volume"]["relative_delta"])
                    <= config.global_max_relative_volume_error,
                }
            )
        global_stage = _finalize_stage(global_stage, checks)
    stages["global"] = global_stage

    global_report = global_stage.get("report")
    volume_delta = (
        abs(float(global_report["volume"]["absolute_delta"]))
        if isinstance(global_report, Mapping)
        else None
    )
    volume_error_margin = (
        max(
            abs(float(global_report["volume"]["target"])),
            abs(float(global_report["volume"]["current"])),
            1.0,
        )
        * 1.0e-12
        if isinstance(global_report, Mapping)
        else 0.0
    )
    if (
        config.target_kind == "solid"
        and volume_delta is not None
        and volume_delta > config.strict_material_tolerance + volume_error_margin
    ):
        target_volume = max(float(global_report["volume"]["target"]), 1.0e-12)
        material_stage = {
            "status": "failed",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": (
                "strict material equality is impossible because the global "
                "volume delta exceeds the strict material tolerance"
            ),
            "strict_point_set_equal": False,
            "absolute_volume_difference_lower_bound": volume_delta,
            "relative_total_difference_lower_bound": volume_delta / target_volume,
            "checks": {"strict_volume_necessary_condition": False},
        }
    elif config.target_kind == "solid":
        material_stage = _stage(
            name="material",
            request={
                "task": "material",
                "target": target,
                "current": current,
                "options": {
                    "boolean_tolerance": None,
                    "include_components": True,
                },
            },
            output_directory=output,
            timeout_seconds=config.material_timeout_seconds,
            python_executable=python_executable,
        )
        if material_stage["status"] != "error":
            report = material_stage["report"]
            global_report = stages["global"].get("report") or {}
            target_volume = global_report.get("volume", {}).get("target")
            relative = (
                (
                    float(report["missing_material"]["volume"])
                    + float(report["excess_material"]["volume"])
                )
                / max(float(target_volume), 1.0e-12)
                if target_volume is not None
                else None
            )
            strict_equal = _strict_material_equal(
                report, config.strict_material_tolerance
            )
            strict_supported = bool(
                report.get("method") == "bidirectional_cut"
                and report.get("strict_equality_supported") is True
                and report.get("boolean_result_valid") is True
                and report.get("volume_balance", {}).get("valid") is True
            )
            material_stage["relative_total_difference"] = relative
            material_stage["strict_point_set_equal"] = (
                strict_equal if strict_supported else None
            )
            material_stage = _finalize_stage(
                material_stage,
                {
                    "boolean_result_valid": report.get("boolean_result_valid")
                    is True,
                    "strict_equality_supported": report.get(
                        "strict_equality_supported"
                    )
                    is True,
                    "volume_balance_valid": report.get("volume_balance", {}).get(
                        "valid"
                    )
                    is True,
                    "strict_missing_material": float(
                        report["missing_material"]["volume"]
                    )
                    < config.strict_material_tolerance,
                    "strict_excess_material": float(
                        report["excess_material"]["volume"]
                    )
                    < config.strict_material_tolerance,
                },
            )
    else:
        material_stage = {
            "status": "not_applicable",
            "gate_passed": True,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "open-shell targets have no solid material point set",
            "strict_point_set_equal": None,
        }
    stages["material"] = material_stage

    if diagnostics:
        boundary_stage = _stage(
            name="boundary",
            request={
                "task": "boundary",
                "target": target,
                "current": current,
                "options": {
                    "linear_deflection": config.boundary_linear_deflection,
                    "max_samples": config.boundary_max_samples,
                },
            },
            output_directory=output,
            timeout_seconds=config.stage_timeout_seconds,
            python_executable=python_executable,
        )
        if boundary_stage["status"] != "error":
            report = boundary_stage["report"]
            boundary_stage = _finalize_stage(
                boundary_stage,
                {
                    "hausdorff": report["symmetric"]["hausdorff_approximation"]
                    <= config.boundary_max_hausdorff,
                    "target_p95": report["target_to_current"]["statistics"]["p95"]
                    <= config.boundary_max_p95,
                    "current_p95": report["current_to_target"]["statistics"]["p95"]
                    <= config.boundary_max_p95,
                },
            )
        stages["boundary"] = boundary_stage

        section_results = []
        for section in config.sections:
            section_stage = _stage(
                name=f"section-{section.section_id}",
                request={
                    "task": "section",
                    "target": target,
                    "current": current,
                    "options": {
                        "plane_origin": section.origin,
                        "plane_normal": section.normal,
                        "tolerance": section.tolerance,
                        "samples_per_edge": section.samples_per_edge,
                    },
                },
                output_directory=output,
                timeout_seconds=config.stage_timeout_seconds,
                python_executable=python_executable,
            )
            if section_stage["status"] != "error":
                report = section_stage["report"]
                comparison = report["comparison"]
                target_area = float(report["target"]["material_area"])
                relative_area = _relative_error(
                    report["current"]["material_area"], target_area
                )
                target_nonempty = bool(report["target"]["edge_count"])
                current_nonempty = bool(report["current"]["edge_count"])
                hausdorff = comparison["hausdorff_approximation"]
                section_stage["relative_area_error"] = relative_area
                section_stage = _finalize_stage(
                    section_stage,
                    {
                        "empty_match": not comparison["empty_section_mismatch"],
                        "required_nonempty": (
                            target_nonempty and current_nonempty
                            if section.require_nonempty
                            else True
                        ),
                        "hausdorff": hausdorff is not None
                        and hausdorff <= section.max_hausdorff,
                        "relative_area": relative_area
                        <= section.max_relative_area_error,
                    },
                )
            section_stage["section_id"] = section.section_id
            section_results.append(section_stage)
        stages["sections"] = {
            "status": (
                "passed"
                if all(item["status"] == "passed" for item in section_results)
                else "error"
                if any(item["status"] == "error" for item in section_results)
                else "failed"
            ),
            "gate_passed": all(
                item.get("gate_passed") is True for item in section_results
            ),
            "elapsed_seconds": round(
                sum(item["elapsed_seconds"] for item in section_results), 3
            ),
            "reports": section_results,
            "error": next(
                (item["error"] for item in section_results if item.get("error")),
                None,
            ),
        }

    strict_material_equal = material_stage.get("strict_point_set_equal") is True
    if config.target_kind != "solid":
        strict_stage = {
            "status": "not_applicable",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "open-shell boundary-set equality is not implemented",
        }
    elif not strict_topology:
        strict_stage = {
            "status": "skipped",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "strict topology comparison was not requested",
        }
    elif not strict_material_equal:
        strict_stage = {
            "status": "skipped",
            "gate_passed": False,
            "elapsed_seconds": 0.0,
            "report": None,
            "report_path": None,
            "error": None,
            "reason": "strict topology requires proven material equality",
        }
    else:
        strict_stage = _stage(
            name="strict",
            request={
                "task": "strict",
                "target": target,
                "current": current,
                "options": {
                    "geometric_tolerance": config.strict_geometric_tolerance,
                    "boolean_volume_tolerance": config.strict_material_tolerance,
                    "boolean_fuzzy_tolerance": None,
                },
            },
            output_directory=output,
            timeout_seconds=config.stage_timeout_seconds,
            python_executable=python_executable,
        )
        if strict_stage["status"] != "error":
            strict_stage = _finalize_stage(
                strict_stage,
                {"hard_gate": bool(strict_stage["report"]["hard_gate_passed"])},
            )
    stages["strict"] = strict_stage
    return stages


def classify_benchmark_result(
    *,
    replay_succeeded: bool,
    persistence_succeeded: bool,
    baseline_integrity_passed: bool,
    candidate_bytes_equal_target: bool,
    candidate_valid: bool,
    target_kind: str,
    candidate_kind_matches: bool,
    candidate_has_solid: bool,
    candidate_has_shell: bool,
    stages: Mapping[str, Mapping[str, Any]],
    strict_topology_requested: bool,
    parameter_representation_required: bool,
    parameter_representation_passed: bool | None,
) -> dict[str, Any]:
    """Classify evidence without letting diagnostics erase proven lower tiers."""

    reasons = []
    if not replay_succeeded:
        reasons.append("replay_failed")
    if not persistence_succeeded:
        reasons.append("step_persistence_failed")
    if not baseline_integrity_passed:
        reasons.append("baseline_integrity_failed")
    if candidate_bytes_equal_target:
        reasons.append("candidate_bytes_equal_target")
    if not candidate_valid:
        reasons.append("candidate_invalid")
    expected_kind_present = (
        candidate_has_solid
        if target_kind == "solid"
        else candidate_has_shell and not candidate_has_solid
    )
    if target_kind == "open_shell" and candidate_has_solid:
        reasons.append("fabricated_solid_for_open_shell")
    elif not candidate_kind_matches or not expected_kind_present:
        reasons.append("candidate_kind_mismatch")
    if reasons:
        return {"classification": "unsupported_or_incomplete", "reasons": reasons}

    if target_kind == "open_shell":
        return {
            "classification": "approximation",
            "reasons": ["open_shell_equivalence_unproved"],
        }

    material = stages.get("material", {})
    strict_material = (
        True
        if material.get("status") == "passed"
        and material.get("gate_passed") is True
        and material.get("strict_point_set_equal") is True
        else False
        if material.get("strict_point_set_equal") is False
        else None
    )
    if strict_material is not True:
        return {
            "classification": "approximation",
            "reasons": [
                "strict_material_point_set_differs"
                if strict_material is False
                else "strict_material_equality_unproved"
            ],
        }
    if not strict_topology_requested:
        return {
            "classification": "geometry_equivalent",
            "reasons": ["strict_topology_not_requested"],
        }

    strict = stages.get("strict", {})
    if strict.get("status") == "passed" and strict.get("gate_passed") is True:
        if parameter_representation_required:
            if parameter_representation_passed is True:
                return {"classification": "exact_brep", "reasons": []}
            return {
                "classification": "geometry_equivalent",
                "reasons": [
                    "parameter_representation_differs"
                    if parameter_representation_passed is False
                    else "parameter_representation_unproved"
                ],
            }
        return {"classification": "exact_brep", "reasons": []}
    if strict.get("status") == "failed":
        report = strict.get("report")
        if isinstance(report, Mapping):
            if report.get("same_geometric_point_set") is not True:
                return {
                    "classification": "geometry_equivalent",
                    "reasons": ["strict_stage_conflicts_with_material_proof"],
                }
            return {
                "classification": "geometry_equivalent",
                "reasons": ["strict_topology_differs"],
            }
    return {
        "classification": "geometry_equivalent",
        "reasons": ["strict_topology_unproved"],
    }


__all__ = [
    "classify_benchmark_result",
    "inspect_benchmark_step",
    "run_comparison_bundle",
]
