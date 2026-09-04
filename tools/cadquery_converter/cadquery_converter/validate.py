"""Validate converted SFTC code against CadQuery ground truth.

Geometry helpers live in ``scoring.geometry``; this module re-exports them for
backward compatibility with existing imports.
"""

from __future__ import annotations

from .scoring.geometry import (
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
]
