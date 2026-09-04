"""Training tier assignment (SFTC.md §6, feature-semantic coverage)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from .feature_semantics import FeatureSemanticsScore
from .geometry import ValidationResult
from .parameters import ParameterScore


@dataclass
class TrainingTier:
    training_tier: str = "reject"
    reasons: list[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assign_training_tier(
    *,
    quality: str,
    conversion_status: str,
    validation: ValidationResult,
    structure: FeatureSemanticsScore,
    parameters: ParameterScore,
    replay_ok: bool = False,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
    param_match_threshold: float = 0.8,
) -> TrainingTier:
    """Map layered scores to training_tier A|B|C|reject."""
    reasons: list[str] = []

    exec_ok = validation.scad.valid
    if conversion_status == "error" or not exec_ok:
        return TrainingTier(training_tier="reject", reasons=["exec_fail"])

    vol = validation.volume_rel_error
    bbox = validation.bbox_rel_error
    coverage = structure.feature_coverage
    has_critical_unsupported = bool(structure.unsupported_semantics) or bool(
        structure.unsupported_count and coverage < 1.0 and quality == "rejected"
    )
    # Treat replay unsupported notes as critical only when conversion not ok
    if conversion_status != "ok" and structure.unsupported_count:
        has_critical_unsupported = True
        reasons.append("unsupported_semantics")

    geometry_a = (
        validation.cq.valid
        and validation.scad.valid
        and (vol is None or vol <= volume_threshold)
        and (bbox is None or bbox <= bbox_threshold)
    )
    geometry_b = (
        validation.cq.valid
        and validation.scad.valid
        and (vol is None or vol <= 0.05)
    )

    if (
        geometry_a
        and coverage >= 0.9
        and not has_critical_unsupported
        and replay_ok
        and parameters.param_match_rate >= param_match_threshold
    ):
        return TrainingTier(training_tier="A", reasons=reasons)

    if geometry_b and coverage >= 0.7:
        if not geometry_a:
            reasons.append("geometry_soft")
        if coverage < 0.9:
            reasons.append(f"feature_coverage={coverage:.3f}")
        if parameters.param_match_rate < param_match_threshold:
            reasons.append(f"param_match={parameters.param_match_rate:.3f}")
        return TrainingTier(training_tier="B", reasons=reasons)

    reasons.append("partial_structure_or_geometry")
    return TrainingTier(training_tier="C", reasons=reasons)
