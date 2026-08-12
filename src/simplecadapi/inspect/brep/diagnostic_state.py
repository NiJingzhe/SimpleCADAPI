"""Full comparison diagnostics grouped by plausible common root causes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class _ComparisonLike(Protocol):
    target: str | None
    candidate: str | None
    diagnostics: dict[str, Any]
    same_geometric_point_set: bool
    geometry_labelled_incidence_graph_isomorphic: bool

    @property
    def hard_gate_passed(self) -> bool: ...


@dataclass(frozen=True)
class _Check:
    code: str
    domain: str
    root_cause: str
    root_cause_title: str
    failed: bool
    expected: Any
    actual: Any
    possible_causes: tuple[str, ...]
    affected_api_stages: tuple[str, ...]
    severity: str = "blocking"


def _comparison_header(comparison: _ComparisonLike) -> dict[str, Any]:
    return {
        "target": comparison.target,
        "candidate": comparison.candidate,
        "hard_gate_passed": comparison.hard_gate_passed,
    }


def _iteration_policy() -> dict[str, bool]:
    return {
        "all_errors_reported": True,
        "group_by_common_root_cause": True,
        "single_error_only": False,
        "single_code_change_only": False,
        "fresh_direct_replay_export_compare_required": True,
    }


def _unavailable_state(comparison: _ComparisonLike) -> dict[str, Any]:
    error = {
        "error_id": "error.0001",
        "code": "diagnostics_unavailable",
        "domain": "comparison",
        "severity": "blocking",
        "location": "comparison",
        "expected": "complete comparison diagnostics",
        "actual": None,
        "possible_causes": [
            "BRepComparison was constructed manually instead of by compare_steps/compare_shapes"
        ],
        "affected_api_stages": ["comparison"],
        "code_locations": [],
        "root_cause_group": "comparison_evidence",
    }
    group = {
        "group_id": "root_cause.comparison_evidence",
        "title": "comparison evidence is incomplete",
        "error_ids": [error["error_id"]],
        "error_codes": [error["code"]],
        "possible_causes": list(error["possible_causes"]),
        "affected_api_stages": list(error["affected_api_stages"]),
        "code_locations": [],
        "change_policy": "Regenerate comparison.json before changing reconstruction code.",
    }
    return {
        "schema": "simplecadapi.diagnostic_state.v1",
        "comparison": _comparison_header(comparison),
        "errors": [error],
        "root_cause_groups": [group],
        "regressions": [],
        "change_group": None,
        "iteration_policy": _iteration_policy(),
    }


def _checks(comparison: _ComparisonLike) -> tuple[_Check, ...]:
    diagnostics = comparison.diagnostics
    return (
        _Check(
            code="target_step_invalid",
            domain="input",
            root_cause="target_integrity",
            root_cause_title="target STEP integrity",
            failed=not diagnostics["step_validity"]["target"],
            expected=True,
            actual=diagnostics["step_validity"]["target"],
            possible_causes=(
                "the original STEP BREP is invalid and requires human review",
            ),
            affected_api_stages=("step_read", "inspection"),
        ),
        _Check(
            code="candidate_step_invalid",
            domain="replay_export",
            root_cause="candidate_generation",
            root_cause_title="candidate generation or export",
            failed=not diagnostics["step_validity"]["candidate"],
            expected=diagnostics["step_validity"]["target"],
            actual=diagnostics["step_validity"]["candidate"],
            possible_causes=("Direct, replay, or export_step produced an invalid BREP",),
            affected_api_stages=("direct", "replay", "export_step"),
        ),
        _Check(
            code="bounding_box_mismatch",
            domain="placement",
            root_cause="datum_scale_placement",
            root_cause_title="datum, scale, profile plane, axis, or placement",
            failed=not diagnostics["bounding_box"]["equal"],
            expected=diagnostics["bounding_box"]["target"],
            actual=diagnostics["bounding_box"]["candidate"],
            possible_causes=(
                "datum, unit conversion, profile plane, axis, or placement is wrong",
            ),
            affected_api_stages=("step_read", "reconstruction", "transform"),
        ),
        _Check(
            code="material_point_set_mismatch",
            domain="material",
            root_cause="material_construction",
            root_cause_title="material construction",
            failed=not comparison.same_geometric_point_set,
            expected={"target_minus_candidate": 0.0, "candidate_minus_target": 0.0},
            actual=diagnostics["boolean_difference"],
            possible_causes=(
                "one or more additive or subtractive regions are missing or extra",
                "a shared upstream profile, axis, or section family is wrong",
            ),
            affected_api_stages=("reconstruction", "boolean", "loft", "sweep"),
        ),
        _Check(
            code="topology_count_mismatch",
            domain="topology",
            root_cause="topology_construction",
            root_cause_title="topology construction and feature ordering",
            failed=not diagnostics["topology_counts"]["equal"],
            expected=diagnostics["topology_counts"]["target"],
            actual=diagnostics["topology_counts"]["candidate"],
            possible_causes=(
                "profile segmentation, operation order, primitive seam, or Boolean cleanup differs",
            ),
            affected_api_stages=("profile", "reconstruction", "boolean", "export_step"),
        ),
        _Check(
            code="face_edge_topology_mismatch",
            domain="topology",
            root_cause="topology_construction",
            root_cause_title="topology construction and feature ordering",
            failed=not comparison.geometry_labelled_incidence_graph_isomorphic,
            expected="geometry-labelled incidence graph isomorphic",
            actual="graph mismatch",
            possible_causes=(
                "operation order, trimming, seam placement, or local connectivity differs",
            ),
            affected_api_stages=("reconstruction", "topology_edit", "boolean", "export_step"),
        ),
        _Check(
            code="surface_type_mismatch",
            domain="carrier_geometry",
            root_cause="carrier_selection",
            root_cause_title="surface and curve carrier selection",
            failed=not diagnostics["surface_types"]["equal"],
            expected=diagnostics["surface_types"]["target"],
            actual=diagnostics["surface_types"]["candidate"],
            possible_causes=(
                "the selected surface family or construction operation is wrong",
            ),
            affected_api_stages=("inspection", "reconstruction", "surface"),
        ),
        _Check(
            code="curve_type_mismatch",
            domain="carrier_geometry",
            root_cause="carrier_selection",
            root_cause_title="surface and curve carrier selection",
            failed=not diagnostics["curve_types"]["equal"],
            expected=diagnostics["curve_types"]["target"],
            actual=diagnostics["curve_types"]["candidate"],
            possible_causes=(
                "the selected profile edge type or segmentation is wrong",
            ),
            affected_api_stages=("inspection", "profile", "reconstruction"),
        ),
    )


def build_diagnostic_state(comparison: _ComparisonLike) -> dict[str, Any]:
    """Return every failed comparison check grouped by plausible common cause."""
    if not comparison.diagnostics:
        return _unavailable_state(comparison)

    errors: list[dict[str, Any]] = []
    group_metadata: dict[str, tuple[str, list[str]]] = {}
    for check in _checks(comparison):
        if not check.failed:
            continue
        error_id = f"error.{len(errors) + 1:04d}"
        errors.append(
            {
                "error_id": error_id,
                "code": check.code,
                "domain": check.domain,
                "severity": check.severity,
                "location": "global",
                "expected": check.expected,
                "actual": check.actual,
                "possible_causes": list(check.possible_causes),
                "affected_api_stages": list(check.affected_api_stages),
                "code_locations": [],
                "root_cause_group": check.root_cause,
            }
        )
        _, error_ids = group_metadata.setdefault(
            check.root_cause,
            (check.root_cause_title, []),
        )
        error_ids.append(error_id)

    by_id = {error["error_id"]: error for error in errors}
    groups: list[dict[str, Any]] = []
    for root_cause, (title, error_ids) in group_metadata.items():
        grouped_errors = [by_id[error_id] for error_id in error_ids]
        groups.append(
            {
                "group_id": f"root_cause.{root_cause}",
                "title": title,
                "error_ids": error_ids,
                "error_codes": [error["code"] for error in grouped_errors],
                "possible_causes": list(
                    dict.fromkeys(
                        cause
                        for error in grouped_errors
                        for cause in error["possible_causes"]
                    )
                ),
                "affected_api_stages": list(
                    dict.fromkeys(
                        stage
                        for error in grouped_errors
                        for stage in error["affected_api_stages"]
                    )
                ),
                "code_locations": [],
                "change_policy": (
                    "Change any number of related operations or code locations needed "
                    "to address this common cause, then rerun Direct, strict replay, "
                    "STEP export, and the complete comparison."
                ),
            }
        )

    return {
        "schema": "simplecadapi.diagnostic_state.v1",
        "comparison": _comparison_header(comparison),
        "errors": errors,
        "root_cause_groups": groups,
        "regressions": [],
        "change_group": None,
        "iteration_policy": _iteration_policy(),
    }


__all__ = ["build_diagnostic_state"]
