"""Layered conversion scoring: geometry + feature semantics + parameters + tiers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .geometry import (
    GeometryMetrics,
    ValidationResult,
    classify_quality,
    classify_traced_quality,
    run_cadquery_metrics,
    run_json_replay_metrics,
    run_sftc_metrics,
    validate_conversion,
    validate_traced_conversion,
)


def score_conversion(
    *,
    conversion_status: str,
    unsupported: Optional[List[str]] = None,
    replay_ok: bool = False,
    validation: Optional[ValidationResult] = None,
    feature_manifest: Optional[Dict[str, Any]] = None,
    sftc_source: str = "",
    has_model_json: bool = False,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
    partial_volume_threshold: float = 0.10,
) -> Dict[str, Any]:
    """Compose geometry quality + feature/param scores + training_tier."""
    from .feature_semantics import score_feature_semantics
    from .parameters import score_parameters
    from .tiers import assign_training_tier

    unsupported = list(unsupported or [])
    validation = validation or ValidationResult()
    validation = classify_traced_quality(
        conversion_status=conversion_status,
        unsupported=unsupported,
        replay_ok=replay_ok,
        validation=validation,
        has_model_json=has_model_json,
        volume_threshold=volume_threshold,
        bbox_threshold=bbox_threshold,
        partial_volume_threshold=partial_volume_threshold,
    )

    structure = score_feature_semantics(feature_manifest or {}, unsupported=unsupported)
    parameters = score_parameters(sftc_source, feature_manifest or {})
    tiers = assign_training_tier(
        quality=validation.quality,
        conversion_status=conversion_status,
        validation=validation,
        structure=structure,
        parameters=parameters,
        replay_ok=replay_ok,
        volume_threshold=volume_threshold,
        bbox_threshold=bbox_threshold,
    )
    return {
        "quality": validation.quality,
        "training_tier": tiers.training_tier,
        "validation": validation.to_dict(),
        "structure": structure.to_dict(),
        "parameters": parameters.to_dict(),
        "tiers": tiers.to_dict(),
    }


__all__ = [
    "GeometryMetrics",
    "ValidationResult",
    "classify_quality",
    "classify_traced_quality",
    "run_cadquery_metrics",
    "run_sftc_metrics",
    "run_json_replay_metrics",
    "validate_conversion",
    "validate_traced_conversion",
    "score_conversion",
]
