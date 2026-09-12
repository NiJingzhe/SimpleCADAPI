"""Circle-fit diagnostics; a small residual does not establish a full circle."""

import math
import numpy as np


def fit_circle_diagnostics(points, *, min_coverage_degrees=270.0, min_axis_ratio=1e-6):
    result = {
        "status": "degenerate",
        "center": None,
        "radius": None,
        "relative_rms": None,
        "residual_rms_mm": None,
        "residual_max_mm": None,
        "coverage_degrees": None,
        "max_gap_degrees": None,
        "axis_ratio": None,
        "condition_number": None,
        "min_coverage_degrees": min_coverage_degrees,
        "min_axis_ratio": min_axis_ratio,
        "error_bound_mm": None,
    }
    data = np.asarray(points, dtype=float)
    if (
        data.ndim != 2
        or data.shape[1] != 2
        or len(data) < 3
        or not np.isfinite(data).all()
    ):
        return {**result, "reason": "need at least three finite 2D points"}
    if len(np.unique(data, axis=0)) < 3:
        return {**result, "reason": "fewer than three distinct points"}
    offset = data.mean(axis=0)  # Translation for conditioning, never the fitted center.
    local = data - offset
    scale = float(np.sqrt(np.mean(np.sum(local * local, axis=1))))
    if scale <= 0:
        return {**result, "reason": "zero spatial extent"}
    local /= scale
    singular = np.linalg.svd(local, compute_uv=False)
    axis_ratio = float(singular[-1] / singular[0])
    result["axis_ratio"] = axis_ratio
    if axis_ratio < min_axis_ratio:
        return {**result, "reason": "collinear or nearly collinear sample geometry"}
    design = np.column_stack((2.0 * local, np.ones(len(local))))
    coefficients, _, rank, sv = np.linalg.lstsq(
        design, np.sum(local * local, axis=1), rcond=None
    )
    result["condition_number"] = float(sv[0] / sv[-1]) if sv[-1] > 0 else None
    radius_sq = float(coefficients[2] + np.dot(coefficients[:2], coefficients[:2]))
    if rank < 3 or radius_sq <= 0:
        return {**result, "reason": "rank-deficient or nonpositive fitted radius"}
    center = offset + coefficients[:2] * scale
    radius = math.sqrt(radius_sq) * scale
    errors = np.linalg.norm(data - center, axis=1) - radius
    rms = float(np.sqrt(np.mean(errors * errors)))
    angles = np.sort(
        np.unique(
            np.mod(
                np.arctan2(data[:, 1] - center[1], data[:, 0] - center[0]), 2 * math.pi
            )
        )
    )
    gap = float(np.max(np.diff(np.r_[angles, angles[0] + 2 * math.pi])))
    coverage = 360.0 - math.degrees(gap)
    return {
        **result,
        "center": center.tolist(),
        "radius": radius,
        "relative_rms": rms / radius,
        "residual_rms_mm": rms,
        "residual_max_mm": float(np.max(np.abs(errors))),
        "coverage_degrees": coverage,
        "max_gap_degrees": math.degrees(gap),
        "status": (
            "candidate" if coverage >= min_coverage_degrees else "insufficient_coverage"
        ),
        "reason": (
            "fit is a candidate, not dimensional proof"
            if coverage >= min_coverage_degrees
            else "samples cover only a partial arc"
        ),
    }


def fit_circle_legacy(points):
    """Keep the historical four-value helper for existing numerical audit scripts."""
    fit = fit_circle_diagnostics(points)
    if fit["radius"] is None:
        return 0.0, 0.0, 0.0, float("inf")
    return *fit["center"], fit["radius"], fit["relative_rms"]
