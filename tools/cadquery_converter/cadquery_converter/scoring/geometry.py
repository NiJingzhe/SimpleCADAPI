"""Geometry-layer metrics and quality classification (CQ / SFTC / model.json)."""

from __future__ import annotations

import math
import tempfile
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class GeometryMetrics:
    volume: Optional[float] = None
    bbox: Optional[tuple[float, float, float, float, float, float]] = None
    valid: bool = False
    error: str = ""


@dataclass
class ValidationResult:
    cq: GeometryMetrics = field(default_factory=GeometryMetrics)
    scad: GeometryMetrics = field(default_factory=GeometryMetrics)
    json_replay: GeometryMetrics = field(default_factory=GeometryMetrics)
    volume_rel_error: Optional[float] = None
    bbox_rel_error: Optional[float] = None
    bbox_sorted_rel_error: Optional[float] = None
    center_shift_rel: Optional[float] = None
    json_volume_rel_error: Optional[float] = None
    json_bbox_rel_error: Optional[float] = None
    sftc_json_volume_rel_error: Optional[float] = None
    quality: str = "rejected"
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _bbox_rel_error(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> float:
    dims_a = (a[3] - a[0], a[4] - a[1], a[5] - a[2])
    dims_b = (b[3] - b[0], b[4] - b[1], b[5] - b[2])
    errors = []
    for da, db in zip(dims_a, dims_b):
        denom = max(abs(da), abs(db), 1e-9)
        errors.append(abs(da - db) / denom)
    return max(errors)


def _bbox_sorted_rel_error(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> float:
    """Compare AABB extents after sorting — invariant to axis permutation.

    Inspired by BenchCAD Appendix M (rotation-invariant IoU): detects shape-size
    agreement even when the solid sits in a different base workplane/frame.
    This is a *diagnostic* companion to axis-aligned bbox_rel_error, not a
    replacement for fixing frame bugs in conversion.
    """
    dims_a = sorted((abs(a[3] - a[0]), abs(a[4] - a[1]), abs(a[5] - a[2])))
    dims_b = sorted((abs(b[3] - b[0]), abs(b[4] - b[1]), abs(b[5] - b[2])))
    errors = []
    for da, db in zip(dims_a, dims_b):
        denom = max(abs(da), abs(db), 1e-9)
        errors.append(abs(da - db) / denom)
    return max(errors)


def _center_shift(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> float:
    """Relative center displacement vs max extent (translation diagnostic)."""
    ca = ((a[0] + a[3]) / 2.0, (a[1] + a[4]) / 2.0, (a[2] + a[5]) / 2.0)
    cb = ((b[0] + b[3]) / 2.0, (b[1] + b[4]) / 2.0, (b[2] + b[5]) / 2.0)
    shift = math.sqrt(sum((x - y) ** 2 for x, y in zip(ca, cb)))
    extent = max(abs(a[3] - a[0]), abs(a[4] - a[1]), abs(a[5] - a[2]), 1e-9)
    return shift / extent


def _rel_volume_error(reference: float, candidate: float) -> float:
    return abs(reference - candidate) / max(abs(reference), 1e-9)


def run_cadquery_metrics(source: str) -> GeometryMetrics:
    metrics = GeometryMetrics()
    try:
        import cadquery as cq
    except ImportError:
        metrics.error = "cadquery not installed"
        return metrics

    namespace: Dict[str, Any] = {"cq": cq}
    cleaned = source.replace("show_object(", "# show_object(")
    try:
        exec(compile(cleaned, "<cadquery>", "exec"), namespace, namespace)
        result = namespace.get("result")
        if result is None:
            metrics.error = "CadQuery result missing"
            return metrics
        shape = result.val()
        metrics.volume = float(shape.Volume())
        bbox = shape.BoundingBox()
        metrics.bbox = (
            float(bbox.xmin),
            float(bbox.ymin),
            float(bbox.zmin),
            float(bbox.xmax),
            float(bbox.ymax),
            float(bbox.zmax),
        )
        metrics.valid = math.isfinite(metrics.volume) and metrics.volume > 0
        if not metrics.valid:
            metrics.error = "invalid CadQuery volume"
    except Exception as exc:
        metrics.error = f"{type(exc).__name__}: {exc}"
    return metrics


def run_sftc_metrics(source: str) -> GeometryMetrics:
    metrics = GeometryMetrics()
    try:
        import simplecadapi as scad
        from simplecadapi.kernel.ocp_properties import bounding_box
    except ImportError as exc:
        metrics.error = f"simplecadapi unavailable: {exc}"
        return metrics

    namespace: Dict[str, Any] = {"scad": scad, "Path": Path, "ql": scad.ql}
    try:
        with tempfile.TemporaryDirectory(prefix="sftc_val_") as tmp:
            del tmp
            exec(compile(source, "<sftc>", "exec"), namespace, namespace)
            build_model = namespace.get("build_model")
            if build_model is None:
                metrics.error = "build_model() missing"
                return metrics
            result = build_model()
            solid = result.value if hasattr(result, "value") else result
            metrics.volume = float(solid.get_volume())
            bbox = bounding_box(solid.wrapped)
            metrics.bbox = (bbox.xmin, bbox.ymin, bbox.zmin, bbox.xmax, bbox.ymax, bbox.zmax)
            metrics.valid = math.isfinite(metrics.volume) and metrics.volume > 0
            if not metrics.valid:
                metrics.error = "invalid SimpleCAD volume"
    except Exception as exc:
        metrics.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}"
    return metrics


def run_json_replay_metrics(model_json: str) -> GeometryMetrics:
    metrics = GeometryMetrics()
    try:
        import simplecadapi as scad
        from simplecadapi.kernel.ocp_properties import bounding_box
    except ImportError as exc:
        metrics.error = f"simplecadapi unavailable: {exc}"
        return metrics

    try:
        results = scad.replay_model_json(model_json, strict=True)
        if not results:
            metrics.error = "model.json replay returned no shapes"
            return metrics
        solid = results[-1]
        metrics.volume = float(solid.get_volume())
        bbox = bounding_box(solid.wrapped)
        metrics.bbox = (bbox.xmin, bbox.ymin, bbox.zmin, bbox.xmax, bbox.ymax, bbox.zmax)
        metrics.valid = math.isfinite(metrics.volume) and metrics.volume > 0
        if not metrics.valid:
            metrics.error = "invalid replayed volume"
    except Exception as exc:
        metrics.error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=2)}"
    return metrics


def _compute_geometry_errors(validation: ValidationResult) -> None:
    cq = validation.cq
    scad = validation.scad
    json_replay = validation.json_replay

    if cq.valid and scad.valid:
        validation.volume_rel_error = _rel_volume_error(cq.volume or 0.0, scad.volume or 0.0)
        if cq.bbox and scad.bbox:
            validation.bbox_rel_error = _bbox_rel_error(cq.bbox, scad.bbox)
            validation.bbox_sorted_rel_error = _bbox_sorted_rel_error(cq.bbox, scad.bbox)
            validation.center_shift_rel = _center_shift(cq.bbox, scad.bbox)

    if cq.valid and json_replay.valid:
        validation.json_volume_rel_error = _rel_volume_error(
            cq.volume or 0.0,
            json_replay.volume or 0.0,
        )
        if cq.bbox and json_replay.bbox:
            validation.json_bbox_rel_error = _bbox_rel_error(cq.bbox, json_replay.bbox)

    if scad.valid and json_replay.valid:
        validation.sftc_json_volume_rel_error = _rel_volume_error(
            scad.volume or 0.0,
            json_replay.volume or 0.0,
        )


def classify_quality(
    *,
    conversion_status: str,
    unsupported: list[str],
    validation: ValidationResult,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
    allow_partial_unsupported: bool = True,
) -> ValidationResult:
    """Quality tiers for legacy static conversion (CQ vs SFTC only)."""
    reasons: list[str] = []

    if conversion_status == "error":
        reasons.append("conversion_error")
        validation.quality = "rejected"
        validation.reasons = reasons
        return validation

    if not validation.cq.valid:
        reasons.append(f"cadquery_failed:{validation.cq.error}")
    if not validation.scad.valid:
        reasons.append(f"simplecad_failed:{validation.scad.error}")

    _compute_geometry_errors(validation)

    if validation.cq.valid and validation.scad.valid:
        if validation.volume_rel_error is not None and validation.volume_rel_error > volume_threshold:
            reasons.append(f"volume_rel_error={validation.volume_rel_error:.4f}")
        if validation.bbox_rel_error is not None and validation.bbox_rel_error > bbox_threshold:
            reasons.append(f"bbox_rel_error={validation.bbox_rel_error:.4f}")

    if unsupported:
        if not allow_partial_unsupported:
            reasons.append("unsupported_ops")
        elif conversion_status == "partial":
            reasons.append("partial_conversion")

    if not validation.cq.valid or not validation.scad.valid:
        validation.quality = "rejected"
    elif reasons and any(
        reason.startswith("volume_rel_error") or reason.startswith("bbox_rel_error")
        for reason in reasons
    ):
        validation.quality = "rejected"
    elif reasons and all(
        reason in {"partial_conversion"} or reason.startswith("cadquery_failed")
        for reason in reasons
    ):
        validation.quality = "partial"
    elif reasons:
        validation.quality = "partial"
    else:
        validation.quality = "accepted"

    validation.reasons = reasons
    return validation


def classify_traced_quality(
    *,
    conversion_status: str,
    unsupported: list[str],
    replay_ok: bool,
    validation: ValidationResult,
    has_model_json: bool,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
    partial_volume_threshold: float = 0.10,
) -> ValidationResult:
    """Quality tiers for traced pipeline: CQ vs SFTC vs model.json replay."""
    reasons: list[str] = []

    if conversion_status == "error":
        reasons.append("conversion_error")
        validation.quality = "rejected"
        validation.reasons = reasons
        return validation

    if not validation.cq.valid:
        reasons.append(f"cadquery_failed:{validation.cq.error}")
    if not validation.scad.valid:
        reasons.append(f"sftc_failed:{validation.scad.error}")
    if has_model_json and not validation.json_replay.valid:
        reasons.append(f"json_replay_failed:{validation.json_replay.error}")
    if has_model_json and not replay_ok:
        reasons.append("model_json_replay_not_ok")

    if unsupported:
        reasons.append("unsupported_ops")

    _compute_geometry_errors(validation)

    hard_geometry_fail = False
    soft_geometry_fail = False

    if validation.cq.valid and validation.scad.valid:
        if validation.volume_rel_error is not None:
            if validation.volume_rel_error > partial_volume_threshold:
                hard_geometry_fail = True
            elif validation.volume_rel_error > volume_threshold:
                soft_geometry_fail = True
                reasons.append(f"volume_rel_error={validation.volume_rel_error:.4f}")
        if validation.bbox_rel_error is not None:
            if validation.bbox_rel_error > bbox_threshold:
                # If sorted extents still match, this is likely a spatial-frame /
                # axis-permutation issue (BenchCAD Appendix M), not a size miss.
                sorted_ok = (
                    validation.bbox_sorted_rel_error is not None
                    and validation.bbox_sorted_rel_error <= bbox_threshold
                )
                if sorted_ok:
                    soft_geometry_fail = True
                    reasons.append(
                        f"frame_mismatch_bbox={validation.bbox_rel_error:.4f}"
                        f"|sorted={validation.bbox_sorted_rel_error:.4f}"
                    )
                else:
                    soft_geometry_fail = True
                    reasons.append(f"bbox_rel_error={validation.bbox_rel_error:.4f}")

    if has_model_json and validation.cq.valid and validation.json_replay.valid:
        if validation.json_volume_rel_error is not None:
            if validation.json_volume_rel_error > partial_volume_threshold:
                hard_geometry_fail = True
            elif validation.json_volume_rel_error > volume_threshold:
                soft_geometry_fail = True
                reasons.append(f"json_volume_rel_error={validation.json_volume_rel_error:.4f}")
        if validation.json_bbox_rel_error is not None and validation.json_bbox_rel_error > bbox_threshold:
            soft_geometry_fail = True
            reasons.append(f"json_bbox_rel_error={validation.json_bbox_rel_error:.4f}")

    if (
        has_model_json
        and validation.scad.valid
        and validation.json_replay.valid
        and validation.sftc_json_volume_rel_error is not None
        and validation.sftc_json_volume_rel_error > volume_threshold
    ):
        soft_geometry_fail = True
        reasons.append(f"sftc_json_volume_rel_error={validation.sftc_json_volume_rel_error:.4f}")

    exec_fail = (
        not validation.cq.valid
        or not validation.scad.valid
        or (has_model_json and not validation.json_replay.valid)
    )

    if exec_fail or hard_geometry_fail:
        validation.quality = "rejected"
    elif (
        conversion_status == "ok"
        and not unsupported
        and replay_ok
        and not soft_geometry_fail
        and validation.cq.valid
        and validation.scad.valid
        and (not has_model_json or validation.json_replay.valid)
    ):
        validation.quality = "accepted"
    elif validation.cq.valid and validation.scad.valid and not hard_geometry_fail:
        validation.quality = "partial"
    else:
        validation.quality = "rejected"

    validation.reasons = reasons
    return validation


def validate_conversion(
    cq_source: str,
    sftc_source: str,
    *,
    conversion_status: str,
    unsupported: Optional[list[str]] = None,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
) -> ValidationResult:
    validation = ValidationResult(
        cq=run_cadquery_metrics(cq_source),
        scad=run_sftc_metrics(sftc_source),
    )
    return classify_quality(
        conversion_status=conversion_status,
        unsupported=list(unsupported or []),
        validation=validation,
        volume_threshold=volume_threshold,
        bbox_threshold=bbox_threshold,
    )


def validate_traced_conversion(
    cq_source: str,
    sftc_source: str,
    *,
    model_json: Optional[str] = None,
    conversion_status: str,
    unsupported: Optional[list[str]] = None,
    replay_ok: bool = False,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
    partial_volume_threshold: float = 0.10,
) -> ValidationResult:
    validation = ValidationResult(
        cq=run_cadquery_metrics(cq_source),
        scad=run_sftc_metrics(sftc_source),
    )
    has_model_json = model_json is not None
    if has_model_json:
        validation.json_replay = run_json_replay_metrics(model_json)
    return classify_traced_quality(
        conversion_status=conversion_status,
        unsupported=list(unsupported or []),
        replay_ok=replay_ok,
        validation=validation,
        has_model_json=has_model_json,
        volume_threshold=volume_threshold,
        bbox_threshold=bbox_threshold,
        partial_volume_threshold=partial_volume_threshold,
    )
