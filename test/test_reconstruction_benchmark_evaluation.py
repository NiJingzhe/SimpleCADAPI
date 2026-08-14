from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

import simplecadapi as scad
from simplecadapi.inverse_engineer.brep import evaluation as benchmark_evaluation
from simplecadapi.kernel.ocp_export import export_step_shapes


def _config(*, target_kind: str = "solid") -> SimpleNamespace:
    return SimpleNamespace(
        target_kind=target_kind,
        stage_timeout_seconds=30.0,
        material_timeout_seconds=90.0,
        global_max_bbox_delta=1.0e-6,
        global_max_centroid_distance=1.0e-6,
        global_max_relative_volume_error=1.0e-6,
        global_max_relative_area_error=1.0e-6,
        strict_material_tolerance=1.0e-9,
        material_max_relative_difference=1.0e-6,
        material_boolean_tolerance=0.01,
        boundary_linear_deflection=1.0,
        boundary_max_samples=32,
        boundary_max_hausdorff=1.0e-6,
        boundary_max_p95=1.0e-6,
        sections=(),
        strict_enabled=True,
        strict_geometric_tolerance=1.0e-7,
    )


def _global_stage() -> dict:
    return {
        "status": "completed",
        "gate_passed": None,
        "elapsed_seconds": 0.01,
        "report": {
            "bounding_box": {"max_absolute_coordinate_delta": 0.0},
            "centroid": {"distance": 0.0},
            "surface_area": {"relative_delta": 0.0},
            "material_body_count": {"delta": 0},
            "volume": {
                "target": 24.0,
                "current": 24.0,
                "absolute_delta": 0.0,
                "relative_delta": 0.0,
            },
        },
        "report_path": None,
        "error": None,
    }


def _strict_material_report(*, supported: bool = True) -> dict:
    return {
        "method": "bidirectional_cut" if supported else "common_volume",
        "missing_material": {"volume": 0.0},
        "excess_material": {"volume": 0.0},
        "boolean_result_valid": True,
        "strict_equality_supported": supported,
        "volume_balance": {"valid": True},
    }


def _classify(**overrides):
    arguments = {
        "replay_succeeded": True,
        "persistence_succeeded": True,
        "baseline_integrity_passed": True,
        "candidate_bytes_equal_target": False,
        "candidate_valid": True,
        "target_kind": "solid",
        "candidate_kind_matches": True,
        "candidate_has_solid": True,
        "candidate_has_shell": True,
        "stages": {},
        "strict_topology_requested": False,
        "parameter_representation_required": False,
        "parameter_representation_passed": None,
    }
    arguments.update(overrides)
    return benchmark_evaluation.classify_benchmark_result(**arguments)


def test_comparison_bundle_requests_strict_bidirectional_material(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []

    def fake_stage(**kwargs):
        requests.append(kwargs["request"])
        if kwargs["name"] == "global":
            return _global_stage()
        if kwargs["name"] == "material":
            assert kwargs["timeout_seconds"] == 90.0
            assert kwargs["request"]["options"] == {
                "boolean_tolerance": None,
                "include_components": True,
            }
            return {
                "status": "completed",
                "gate_passed": None,
                "elapsed_seconds": 0.01,
                "report": _strict_material_report(),
                "report_path": None,
                "error": None,
            }
        raise AssertionError(kwargs["name"])

    monkeypatch.setattr(benchmark_evaluation, "_stage", fake_stage)
    stages = benchmark_evaluation.run_comparison_bundle(
        _config(),
        target_path=tmp_path / "target.step",
        candidate_path=tmp_path / "candidate.step",
        output_directory=tmp_path / "evaluation",
    )

    assert [request["task"] for request in requests] == ["global", "material"]
    assert stages["material"]["strict_point_set_equal"] is True


def test_identical_solids_produce_real_strict_material_proof(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.step"
    candidate = tmp_path / "candidate.step"
    export_step_shapes(
        [BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()],
        str(target),
    )
    export_step_shapes(
        [BRepPrimAPI_MakeBox(2.0, 3.0, 4.0).Shape()],
        str(candidate),
    )

    stages = benchmark_evaluation.run_comparison_bundle(
        _config(),
        target_path=target,
        candidate_path=candidate,
        output_directory=tmp_path / "evaluation",
    )

    material = stages["material"]
    assert material["status"] == "passed"
    assert material["strict_point_set_equal"] is True
    assert material["report"]["method"] == "bidirectional_cut"
    assert material["report"]["strict_equality_supported"] is True
    assert material["report"]["boolean_result_valid"] is True
    assert material["report"]["volume_balance"]["valid"] is True


def test_non_strict_material_estimate_cannot_prove_point_set_equality(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_stage(**kwargs):
        if kwargs["name"] == "global":
            return _global_stage()
        return {
            "status": "completed",
            "gate_passed": None,
            "elapsed_seconds": 0.01,
            "report": _strict_material_report(supported=False),
            "report_path": None,
            "error": None,
        }

    monkeypatch.setattr(benchmark_evaluation, "_stage", fake_stage)
    stages = benchmark_evaluation.run_comparison_bundle(
        _config(),
        target_path=tmp_path / "target.step",
        candidate_path=tmp_path / "candidate.step",
        output_directory=tmp_path / "evaluation",
    )

    assert stages["material"]["strict_point_set_equal"] is None
    assert stages["material"]["checks"]["strict_equality_supported"] is False


def test_valid_strict_material_residual_proves_point_sets_differ(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _strict_material_report()
    report["missing_material"]["volume"] = 0.01

    def fake_stage(**kwargs):
        if kwargs["name"] == "global":
            return _global_stage()
        return {
            "status": "completed",
            "gate_passed": None,
            "elapsed_seconds": 0.01,
            "report": report,
            "report_path": None,
            "error": None,
        }

    monkeypatch.setattr(benchmark_evaluation, "_stage", fake_stage)
    stages = benchmark_evaluation.run_comparison_bundle(
        _config(),
        target_path=tmp_path / "target.step",
        candidate_path=tmp_path / "candidate.step",
        output_directory=tmp_path / "evaluation",
    )

    assert stages["material"]["strict_point_set_equal"] is False


def test_material_proof_survives_unavailable_global_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_stage(**kwargs):
        if kwargs["name"] == "global":
            return {
                "status": "error",
                "gate_passed": False,
                "elapsed_seconds": 0.01,
                "report": None,
                "report_path": None,
                "error": "global worker failed",
            }
        return {
            "status": "completed",
            "gate_passed": None,
            "elapsed_seconds": 0.01,
            "report": _strict_material_report(),
            "report_path": None,
            "error": None,
        }

    monkeypatch.setattr(benchmark_evaluation, "_stage", fake_stage)
    stages = benchmark_evaluation.run_comparison_bundle(
        _config(),
        target_path=tmp_path / "target.step",
        candidate_path=tmp_path / "candidate.step",
        output_directory=tmp_path / "evaluation",
    )

    assert stages["global"]["status"] == "error"
    assert stages["material"]["status"] == "passed"
    assert stages["material"]["strict_point_set_equal"] is True
    assert stages["material"]["relative_total_difference"] is None


def test_material_timeout_leaves_valid_solid_as_approximation() -> None:
    result = _classify(
        stages={
            "global": {"status": "passed", "gate_passed": True},
            "material": {
                "status": "error",
                "gate_passed": False,
                "error": "evaluation stage timed out",
            },
        },
    )

    assert result == {
        "classification": "approximation",
        "reasons": ["strict_material_equality_unproved"],
    }


def test_failed_material_stage_cannot_claim_strict_equality() -> None:
    result = _classify(
        stages={
            "material": {
                "status": "error",
                "gate_passed": False,
                "strict_point_set_equal": True,
            },
            "strict": {"status": "passed", "gate_passed": True},
        },
        strict_topology_requested=True,
    )

    assert result == {
        "classification": "approximation",
        "reasons": ["strict_material_equality_unproved"],
    }


def test_valid_open_shell_is_approximation_when_equivalence_is_unproved() -> None:
    result = _classify(
        target_kind="open_shell",
        candidate_has_solid=False,
        candidate_has_shell=True,
        stages={
            "global": {"status": "passed", "gate_passed": True},
            "material": {"status": "not_applicable", "gate_passed": True},
            "strict": {"status": "not_applicable", "gate_passed": False},
        },
    )

    assert result == {
        "classification": "approximation",
        "reasons": ["open_shell_equivalence_unproved"],
    }


def test_real_open_shell_reloads_and_classifies_without_fabricating_material(
    tmp_path: Path,
) -> None:
    lower = scad.make_circle_rwire(center=(0.0, 0.0, 0.0), radius=2.0)
    upper = scad.make_circle_rwire(center=(0.0, 0.0, 2.0), radius=1.0)
    shell = scad.loft_rshell(sections=[lower, upper])
    candidate = tmp_path / "candidate.step"
    export_step_shapes([shell.wrapped], str(candidate))

    inspection = benchmark_evaluation.inspect_benchmark_step(
        candidate,
        name="open-shell-inspection",
        output_directory=tmp_path / "evaluation",
        timeout_seconds=30.0,
    )
    report = inspection["report"]
    result = _classify(
        candidate_valid=inspection["status"] == "passed",
        target_kind="open_shell",
        candidate_has_solid=bool(report["counts"]["solid"]),
        candidate_has_shell=bool(report["counts"]["shell"]),
        stages={
            "global": {"status": "passed", "gate_passed": True},
            "material": {"status": "not_applicable", "gate_passed": True},
        },
    )

    assert report["counts"]["solid"] == 0
    assert report["counts"]["shell"] == 1
    assert result == {
        "classification": "approximation",
        "reasons": ["open_shell_equivalence_unproved"],
    }


def test_inspection_accepts_valid_multi_root_step(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.step"
    export_step_shapes(
        [
            BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(),
            BRepPrimAPI_MakeBox(2.0, 2.0, 2.0).Shape(),
        ],
        str(candidate),
    )

    inspection = benchmark_evaluation.inspect_benchmark_step(
        candidate,
        name="multi-root-inspection",
        output_directory=tmp_path / "evaluation",
        timeout_seconds=30.0,
    )

    assert inspection["status"] == "passed"
    assert inspection["report"]["counts"]["solid"] == 2


def test_strict_comparison_accepts_identical_multi_root_steps(tmp_path: Path) -> None:
    target = tmp_path / "target.step"
    candidate = tmp_path / "candidate.step"
    shapes = [
        BRepPrimAPI_MakeBox(1.0, 1.0, 1.0).Shape(),
        BRepPrimAPI_MakeBox(2.0, 2.0, 2.0).Shape(),
    ]
    export_step_shapes(shapes, str(target))
    export_step_shapes(shapes, str(candidate))

    stages = benchmark_evaluation.run_comparison_bundle(
        _config(),
        target_path=target,
        candidate_path=candidate,
        output_directory=tmp_path / "evaluation",
        strict_topology=True,
    )

    assert stages["material"]["strict_point_set_equal"] is True
    assert stages["strict"]["status"] == "passed"
    assert stages["strict"]["report"]["hard_gate_passed"] is True


def test_open_shell_target_rejects_a_fabricated_solid() -> None:
    result = _classify(
        target_kind="open_shell",
        candidate_has_solid=True,
        candidate_has_shell=True,
        stages={"global": {"status": "passed", "gate_passed": True}},
    )

    assert result == {
        "classification": "unsupported_or_incomplete",
        "reasons": ["fabricated_solid_for_open_shell"],
    }


def test_strict_topology_failure_does_not_erase_proven_geometry_equivalence() -> None:
    result = _classify(
        stages={
            "global": {"status": "passed", "gate_passed": True},
            "material": {
                "status": "passed",
                "gate_passed": True,
                "strict_point_set_equal": True,
            },
            "strict": {"status": "error", "gate_passed": False},
        },
        strict_topology_requested=True,
    )

    assert result == {
        "classification": "geometry_equivalent",
        "reasons": ["strict_topology_unproved"],
    }


def test_missing_parameter_representation_does_not_erase_geometry_equivalence() -> None:
    result = _classify(
        stages={
            "global": {"status": "passed", "gate_passed": True},
            "material": {
                "status": "passed",
                "gate_passed": True,
                "strict_point_set_equal": True,
            },
            "strict": {
                "status": "passed",
                "gate_passed": True,
                "report": {"hard_gate_passed": True},
            },
        },
        strict_topology_requested=True,
        parameter_representation_required=True,
        parameter_representation_passed=None,
    )

    assert result == {
        "classification": "geometry_equivalent",
        "reasons": ["parameter_representation_unproved"],
    }


def test_open_shell_target_requires_a_shell_candidate() -> None:
    result = _classify(
        target_kind="open_shell",
        candidate_kind_matches=False,
        candidate_has_solid=False,
        candidate_has_shell=False,
        stages={"global": {"status": "passed", "gate_passed": True}},
    )

    assert result == {
        "classification": "unsupported_or_incomplete",
        "reasons": ["candidate_kind_mismatch"],
    }


def test_solid_target_requires_a_solid_candidate() -> None:
    result = _classify(
        candidate_kind_matches=False,
        candidate_has_solid=False,
        candidate_has_shell=True,
        stages={"global": {"status": "passed", "gate_passed": True}},
    )

    assert result == {
        "classification": "unsupported_or_incomplete",
        "reasons": ["candidate_kind_mismatch"],
    }


def test_candidate_kind_evidence_must_agree_with_shape_counts() -> None:
    result = _classify(
        target_kind="open_shell",
        candidate_kind_matches=True,
        candidate_has_solid=False,
        candidate_has_shell=False,
    )

    assert result == {
        "classification": "unsupported_or_incomplete",
        "reasons": ["candidate_kind_mismatch"],
    }


def test_strict_material_conflict_does_not_erase_prior_material_proof() -> None:
    result = _classify(
        stages={
            "global": {"status": "passed", "gate_passed": True},
            "material": {
                "status": "passed",
                "gate_passed": True,
                "strict_point_set_equal": True,
            },
            "strict": {
                "status": "failed",
                "gate_passed": False,
                "report": {
                    "same_geometric_point_set": False,
                    "hard_gate_passed": False,
                },
            },
        },
        strict_topology_requested=True,
    )

    assert result == {
        "classification": "geometry_equivalent",
        "reasons": ["strict_stage_conflicts_with_material_proof"],
    }


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"persistence_succeeded": False}, "step_persistence_failed"),
        ({"baseline_integrity_passed": False}, "baseline_integrity_failed"),
        ({"candidate_bytes_equal_target": True}, "candidate_bytes_equal_target"),
    ],
)
def test_missing_submission_evidence_blocks_classification(override, reason) -> None:
    result = _classify(**override)

    assert result["classification"] == "unsupported_or_incomplete"
    assert reason in result["reasons"]


def test_required_parameter_representation_can_reach_exact_brep() -> None:
    result = _classify(
        stages={
            "material": {
                "status": "passed",
                "gate_passed": True,
                "strict_point_set_equal": True,
            },
            "strict": {"status": "passed", "gate_passed": True},
        },
        strict_topology_requested=True,
        parameter_representation_required=True,
        parameter_representation_passed=True,
    )

    assert result == {"classification": "exact_brep", "reasons": []}


def test_stage_resolves_relative_output_before_switching_worker_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    output = Path("evaluation")
    output.mkdir()

    def fake_run(command, **kwargs):
        request_path = Path(command[-2])
        report_path = Path(command[-1])
        assert request_path.is_absolute()
        assert report_path.is_absolute()
        assert request_path.parent == report_path.parent
        assert request_path.parent.parent == (tmp_path / "evaluation")
        report_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(benchmark_evaluation.subprocess, "run", fake_run)
    result = benchmark_evaluation._stage(
        name="global",
        request={"task": "global"},
        output_directory=output,
        timeout_seconds=1.0,
        python_executable="python",
    )

    assert result["status"] == "completed"


def test_stage_rejects_path_traversal_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="filename-safe"):
        benchmark_evaluation._stage(
            name="../escaped",
            request={"task": "global"},
            output_directory=tmp_path,
            timeout_seconds=1.0,
            python_executable="python",
        )


def test_stage_writes_inside_fresh_exclusive_subdirectories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "evaluation"
    output.mkdir()
    report_directories = []

    def fake_run(command, **kwargs):
        report_path = Path(command[-1])
        report_directories.append(report_path.parent)
        report_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(benchmark_evaluation.subprocess, "run", fake_run)
    for _ in range(2):
        benchmark_evaluation._stage(
            name="global",
            request={"task": "global"},
            output_directory=output,
            timeout_seconds=1.0,
            python_executable="python",
        )

    assert len(set(report_directories)) == 2
    assert all(path.parent == output for path in report_directories)
