"""Math helpers for CAD-friendly curve parameterization."""

from __future__ import annotations

from dataclasses import dataclass
import math as _math
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import numpy as np


PointTuple = Tuple[float, ...]


def _as_sample_array(
    sample_points: Iterable[Sequence[float]], *, duplicate_tolerance: float
) -> np.ndarray:
    if duplicate_tolerance < 0.0 or not _math.isfinite(float(duplicate_tolerance)):
        raise ValueError("duplicate_tolerance must be a finite non-negative number")

    raw_points = list(sample_points)
    if not raw_points:
        raise ValueError("sample_points must contain at least two distinct points")

    converted: List[PointTuple] = []
    dimension: Optional[int] = None
    for index, point in enumerate(raw_points):
        try:
            values = tuple(float(value) for value in point)
        except Exception as exc:
            raise ValueError(f"sample point {index} is not a numeric sequence") from exc
        if dimension is None:
            dimension = len(values)
            if dimension not in {2, 3}:
                raise ValueError("sample points must be 2D or 3D")
        elif len(values) != dimension:
            raise ValueError("all sample points must have the same dimension")
        if not all(_math.isfinite(value) for value in values):
            raise ValueError("all sample point coordinates must be finite")
        converted.append(values)

    deduped: List[PointTuple] = []
    for point in converted:
        if not deduped:
            deduped.append(point)
            continue
        previous = deduped[-1]
        distance = _math.sqrt(sum((a - b) ** 2 for a, b in zip(point, previous)))
        if distance <= duplicate_tolerance:
            continue
        deduped.append(point)

    if len(deduped) < 2:
        raise ValueError("sample_points must contain at least two distinct points")
    return np.asarray(deduped, dtype=float)


def _chord_length_parameters(points: np.ndarray) -> np.ndarray:
    deltas = np.linalg.norm(np.diff(points, axis=0), axis=1)
    total = float(np.sum(deltas))
    if total <= 0.0 or not _math.isfinite(total):
        raise ValueError("sample_points must span a non-zero chord length")
    parameters = np.concatenate(([0.0], np.cumsum(deltas) / total))
    parameters[-1] = 1.0
    return parameters


def _full_knot_vector(degree: int, interior_knots: Sequence[float]) -> Tuple[float, ...]:
    return (
        tuple(0.0 for _ in range(degree + 1))
        + tuple(float(knot) for knot in sorted(interior_knots))
        + tuple(1.0 for _ in range(degree + 1))
    )


def _validate_interior_knots(interior_knots: Sequence[float], *, knot_tolerance: float) -> Tuple[float, ...]:
    validated: List[float] = []
    for knot in sorted(float(value) for value in interior_knots):
        if not _math.isfinite(knot):
            raise ValueError("adaptive knot values must be finite")
        if knot <= knot_tolerance or knot >= 1.0 - knot_tolerance:
            continue
        if validated and abs(knot - validated[-1]) <= knot_tolerance:
            continue
        validated.append(knot)
    return tuple(validated)


def _bspline_basis_row(parameter: float, degree: int, knots: Sequence[float]) -> np.ndarray:
    control_count = len(knots) - degree - 1
    if control_count <= 0:
        raise ValueError("invalid knot vector/control count combination")

    u = min(max(float(parameter), float(knots[degree])), float(knots[-degree - 1]))
    if u >= float(knots[-degree - 1]):
        row = np.zeros(control_count, dtype=float)
        row[-1] = 1.0
        return row

    basis = np.zeros(len(knots) - 1, dtype=float)
    for index in range(len(basis)):
        if float(knots[index]) <= u < float(knots[index + 1]):
            basis[index] = 1.0

    active = basis
    for current_degree in range(1, degree + 1):
        next_basis = np.zeros(len(knots) - 1 - current_degree, dtype=float)
        for index in range(len(next_basis)):
            left_den = float(knots[index + current_degree] - knots[index])
            right_den = float(knots[index + current_degree + 1] - knots[index + 1])
            left = 0.0
            right = 0.0
            if left_den > 0.0:
                left = (u - float(knots[index])) / left_den * active[index]
            if right_den > 0.0:
                right = (float(knots[index + current_degree + 1]) - u) / right_den * active[index + 1]
            next_basis[index] = left + right
        active = next_basis
    return active[:control_count]


def _basis_matrix(parameters: Sequence[float], degree: int, knots: Sequence[float]) -> np.ndarray:
    return np.vstack([_bspline_basis_row(float(parameter), degree, knots) for parameter in parameters])


def _straight_line_result(
    points: np.ndarray,
    parameters: np.ndarray,
    *,
    tolerance: float,
    fairing: float,
) -> "BSplineFitResult":
    start = points[0]
    end = points[-1]
    delta = end - start
    control_points = np.vstack(
        [
            start,
            start + delta / 3.0,
            start + 2.0 * delta / 3.0,
            end,
        ]
    )
    knots = _full_knot_vector(3, ())
    fitted = _basis_matrix(parameters, 3, knots) @ control_points
    errors = np.linalg.norm(fitted - points, axis=1)
    return BSplineFitResult(
        degree=3,
        control_points=_array_to_points(control_points),
        knots=tuple(float(knot) for knot in knots),
        sample_parameters=tuple(float(value) for value in parameters),
        max_error=float(np.max(errors)) if len(errors) else 0.0,
        rms_error=float(np.sqrt(np.mean(errors**2))) if len(errors) else 0.0,
        tolerance=float(tolerance),
        fairing=float(fairing),
        iterations=0,
        converged=True,
    )


def _array_to_points(values: np.ndarray) -> Tuple[PointTuple, ...]:
    return tuple(tuple(float(component) for component in row) for row in values.tolist())


def _fit_for_knots(
    points: np.ndarray,
    parameters: np.ndarray,
    *,
    degree: int,
    interior_knots: Sequence[float],
    fairing: float,
    tolerance: float,
    iterations: int,
) -> "BSplineFitResult":
    knots = _full_knot_vector(degree, interior_knots)
    basis = _basis_matrix(parameters, degree, knots)
    control_count = basis.shape[1]
    dimension = points.shape[1]

    controls = np.zeros((control_count, dimension), dtype=float)
    controls[0, :] = points[0, :]
    controls[-1, :] = points[-1, :]

    unknown_indices = list(range(1, control_count - 1))
    unknown_map = {control_index: index for index, control_index in enumerate(unknown_indices)}
    fixed_rhs = (
        np.outer(basis[:, 0], controls[0, :])
        + np.outer(basis[:, -1], controls[-1, :])
    )
    matrix = basis[:, unknown_indices]
    rhs = points - fixed_rhs

    if fairing > 0.0 and unknown_indices:
        fairing_rows: List[np.ndarray] = []
        fairing_rhs: List[np.ndarray] = []
        scale = _math.sqrt(float(fairing))
        for start_index in range(control_count - 2):
            row = np.zeros(len(unknown_indices), dtype=float)
            target = np.zeros(dimension, dtype=float)
            for control_index, coefficient in (
                (start_index, 1.0),
                (start_index + 1, -2.0),
                (start_index + 2, 1.0),
            ):
                mapped = unknown_map.get(control_index)
                if mapped is None:
                    target -= coefficient * controls[control_index, :]
                else:
                    row[mapped] += coefficient
            fairing_rows.append(row * scale)
            fairing_rhs.append(target * scale)
        if fairing_rows:
            matrix = np.vstack((matrix, np.vstack(fairing_rows)))
            rhs = np.vstack((rhs, np.vstack(fairing_rhs)))

    if unknown_indices:
        solved, *_unused = np.linalg.lstsq(matrix, rhs, rcond=None)
        for control_index, solved_index in unknown_map.items():
            controls[control_index, :] = solved[solved_index, :]

    fitted = basis @ controls
    errors = np.linalg.norm(fitted - points, axis=1)
    max_error = float(np.max(errors)) if len(errors) else 0.0
    rms_error = float(np.sqrt(np.mean(errors**2))) if len(errors) else 0.0

    return BSplineFitResult(
        degree=int(degree),
        control_points=_array_to_points(controls),
        knots=tuple(float(knot) for knot in knots),
        sample_parameters=tuple(float(value) for value in parameters),
        max_error=max_error,
        rms_error=rms_error,
        tolerance=float(tolerance),
        fairing=float(fairing),
        iterations=int(iterations),
        converged=max_error <= float(tolerance),
    )


def _insert_adaptive_knot(
    interior_knots: Sequence[float],
    parameters: np.ndarray,
    errors: np.ndarray,
    *,
    knot_tolerance: float,
) -> Tuple[float, ...]:
    current = _validate_interior_knots(interior_knots, knot_tolerance=knot_tolerance)
    boundaries = (0.0,) + current + (1.0,)

    best_span: Optional[Tuple[float, float, int, float]] = None
    for left, right in zip(boundaries, boundaries[1:]):
        if right - left <= 2.0 * knot_tolerance:
            continue
        mask = (parameters > left + knot_tolerance) & (parameters < right - knot_tolerance)
        if not np.any(mask):
            span_error = -1.0
            local_index = -1
        else:
            masked_indices = np.nonzero(mask)[0]
            local_offset = int(np.argmax(errors[masked_indices]))
            local_index = int(masked_indices[local_offset])
            span_error = float(errors[local_index])
        if best_span is None or span_error > best_span[3] or (
            span_error == best_span[3] and (right - left) > (best_span[1] - best_span[0])
        ):
            best_span = (float(left), float(right), local_index, span_error)

    if best_span is None:
        return current

    left, right, local_index, _span_error = best_span
    if local_index >= 0:
        candidate = float(parameters[local_index])
    else:
        candidate = 0.5 * (left + right)
    candidate = min(max(candidate, left + knot_tolerance), right - knot_tolerance)
    if any(abs(candidate - knot) <= knot_tolerance for knot in current):
        candidate = 0.5 * (left + right)
    if candidate <= knot_tolerance or candidate >= 1.0 - knot_tolerance:
        candidate = 0.5 * (left + right)
    if any(abs(candidate - knot) <= knot_tolerance for knot in current):
        for left, right in sorted(
            zip(boundaries, boundaries[1:]), key=lambda span: span[1] - span[0], reverse=True
        ):
            if right - left > 2.0 * knot_tolerance:
                candidate = 0.5 * (left + right)
                break
    return _validate_interior_knots((*current, candidate), knot_tolerance=knot_tolerance)


def _prune_knots(
    points: np.ndarray,
    parameters: np.ndarray,
    interior_knots: Sequence[float],
    *,
    degree: int,
    fairing: float,
    tolerance: float,
    knot_tolerance: float,
    iterations: int,
) -> Tuple[Tuple[float, ...], "BSplineFitResult"]:
    current = _validate_interior_knots(interior_knots, knot_tolerance=knot_tolerance)
    current_result = _fit_for_knots(
        points,
        parameters,
        degree=degree,
        interior_knots=current,
        fairing=fairing,
        tolerance=tolerance,
        iterations=iterations,
    )
    changed = True
    while changed and current:
        changed = False
        best_candidate: Optional[Tuple[Tuple[float, ...], BSplineFitResult]] = None
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1 :]
            result = _fit_for_knots(
                points,
                parameters,
                degree=degree,
                interior_knots=candidate,
                fairing=fairing,
                tolerance=tolerance,
                iterations=iterations,
            )
            if result.max_error <= tolerance:
                if best_candidate is None or result.max_error < best_candidate[1].max_error:
                    best_candidate = (candidate, result)
        if best_candidate is not None:
            current, current_result = best_candidate
            changed = True
    return current, current_result


@dataclass(frozen=True)
class BSplineFitResult:
    """Result from fitting a cubic B-spline to sampled curve points.

    The result stores a complete, normalized B-spline definition suitable for
    passing into the exact B-spline edge/wire APIs: cubic degree, control
    points, and a full clamped knot vector.
    """

    degree: int
    control_points: Tuple[PointTuple, ...]
    knots: Tuple[float, ...]
    sample_parameters: Tuple[float, ...]
    max_error: float
    rms_error: float
    tolerance: float
    fairing: float
    iterations: int
    converged: bool

    @property
    def control_count(self) -> int:
        """Number of fitted B-spline control points."""

        return len(self.control_points)

    @property
    def dimension(self) -> int:
        """Coordinate dimension of each fitted control point."""

        return len(self.control_points[0]) if self.control_points else 0

    @property
    def unique_knots(self) -> Tuple[float, ...]:
        """Return knot values with repeated entries collapsed."""

        unique: List[float] = []
        for knot in self.knots:
            if not unique or abs(float(knot) - unique[-1]) > 1e-12:
                unique.append(float(knot))
        return tuple(unique)

    @property
    def multiplicities(self) -> Tuple[int, ...]:
        """Return knot multiplicities aligned with `unique_knots`."""

        if not self.knots:
            return ()
        multiplicities: List[int] = []
        current = float(self.knots[0])
        count = 0
        for knot in self.knots:
            value = float(knot)
            if abs(value - current) <= 1e-12:
                count += 1
                continue
            multiplicities.append(count)
            current = value
            count = 1
        multiplicities.append(count)
        return tuple(multiplicities)

    def evaluate(self, parameter: float) -> PointTuple:
        """Evaluate the fitted B-spline at a normalized parameter in `[0, 1]`."""

        controls = np.asarray(self.control_points, dtype=float)
        row = _bspline_basis_row(float(parameter), int(self.degree), self.knots)
        point = row @ controls
        return tuple(float(component) for component in point.tolist())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the fit result."""

        return {
            "degree": int(self.degree),
            "control_points": [list(point) for point in self.control_points],
            "knots": list(self.knots),
            "unique_knots": list(self.unique_knots),
            "multiplicities": list(self.multiplicities),
            "sample_parameters": list(self.sample_parameters),
            "max_error": float(self.max_error),
            "rms_error": float(self.rms_error),
            "tolerance": float(self.tolerance),
            "fairing": float(self.fairing),
            "iterations": int(self.iterations),
            "converged": bool(self.converged),
        }


def fit_cubic_bspline_control_points(
    sample_points: Sequence[Sequence[float]],
    *,
    tolerance: float = 1e-3,
    max_control_points: Optional[int] = None,
    fairing: float = 1e-6,
    duplicate_tolerance: float = 1e-12,
    knot_tolerance: float = 1e-9,
    raise_on_failure: bool = True,
) -> BSplineFitResult:
    """Fit a minimal cubic B-spline control polygon to sampled curve points.

    Uses chord-length parameterization, cubic clamped B-spline least squares,
    second-difference fairing regularization, and adaptive simple knot insertion
    until the maximum sample error is within `tolerance`. Only simple interior
    knots are inserted, so a cubic result remains C2-continuous at every interior
    knot.

    Args:
        sample_points: Ordered 2D or 3D points sampled along the intended curve.
            Consecutive duplicate points within `duplicate_tolerance` are ignored.
        tolerance: Maximum allowed Euclidean fitting error at the input samples.
        max_control_points: Upper bound for fitted control points. Defaults to the
            cleaned sample count, with a cubic minimum of four controls.
        fairing: Non-negative second-difference regularization weight. Larger
            values prefer smoother control polygons while still respecting the
            error tolerance when possible.
        duplicate_tolerance: Distance threshold for removing consecutive duplicate
            sample points before chord-length parameterization.
        knot_tolerance: Normalized parameter spacing threshold used to avoid
            duplicate or near-boundary interior knots.
        raise_on_failure: Raise `ValueError` when the tolerance cannot be reached
            within `max_control_points`. If false, return the best non-converged
            result instead.

    Returns:
        `BSplineFitResult` containing cubic degree, control points, a full clamped
        knot vector, knot multiplicities, sample parameters, and fitting error.

    Raises:
        ValueError: If inputs are invalid, or if the tolerance cannot be met and
            `raise_on_failure=True`.

    Examples:
        ```python
        from simplecadapi.math import fit_cubic_bspline_control_points

        samples = [(0.0, 0.0, 0.0), (1.0, 0.4, 0.0), (2.0, 0.0, 0.0)]
        fit = fit_cubic_bspline_control_points(samples, tolerance=0.01)
        print(fit.control_points)
        print(fit.knots, fit.multiplicities)
        ```
    """

    tolerance = float(tolerance)
    fairing = float(fairing)
    knot_tolerance = float(knot_tolerance)
    if tolerance <= 0.0 or not _math.isfinite(tolerance):
        raise ValueError("tolerance must be a finite positive number")
    if fairing < 0.0 or not _math.isfinite(fairing):
        raise ValueError("fairing must be a finite non-negative number")
    if knot_tolerance <= 0.0 or not _math.isfinite(knot_tolerance):
        raise ValueError("knot_tolerance must be a finite positive number")

    points = _as_sample_array(sample_points, duplicate_tolerance=float(duplicate_tolerance))
    parameters = _chord_length_parameters(points)
    degree = 3

    if len(points) == 2:
        result = _straight_line_result(
            points,
            parameters,
            tolerance=tolerance,
            fairing=fairing,
        )
        if result.max_error <= tolerance or not raise_on_failure:
            return result
        raise ValueError("failed to fit a straight cubic B-spline within tolerance")

    default_max = max(degree + 1, len(points))
    max_controls = default_max if max_control_points is None else int(max_control_points)
    if max_controls < degree + 1:
        raise ValueError("max_control_points must be at least 4 for a cubic B-spline")

    interior_knots: Tuple[float, ...] = ()
    best_result: Optional[BSplineFitResult] = None
    max_insertions = max_controls - (degree + 1)

    for iteration in range(max_insertions + 1):
        result = _fit_for_knots(
            points,
            parameters,
            degree=degree,
            interior_knots=interior_knots,
            fairing=fairing,
            tolerance=tolerance,
            iterations=iteration,
        )
        if best_result is None or result.max_error < best_result.max_error:
            best_result = result
        if result.max_error <= tolerance:
            _pruned_knots, pruned_result = _prune_knots(
                points,
                parameters,
                interior_knots,
                degree=degree,
                fairing=fairing,
                tolerance=tolerance,
                knot_tolerance=knot_tolerance,
                iterations=iteration,
            )
            return pruned_result
        if iteration >= max_insertions:
            break

        basis = _basis_matrix(parameters, degree, result.knots)
        fitted = basis @ np.asarray(result.control_points, dtype=float)
        errors = np.linalg.norm(fitted - points, axis=1)
        next_knots = _insert_adaptive_knot(
            interior_knots,
            parameters,
            errors,
            knot_tolerance=knot_tolerance,
        )
        if len(next_knots) == len(interior_knots):
            break
        interior_knots = next_knots

    assert best_result is not None
    if not raise_on_failure:
        return BSplineFitResult(
            degree=best_result.degree,
            control_points=best_result.control_points,
            knots=best_result.knots,
            sample_parameters=best_result.sample_parameters,
            max_error=best_result.max_error,
            rms_error=best_result.rms_error,
            tolerance=best_result.tolerance,
            fairing=best_result.fairing,
            iterations=best_result.iterations,
            converged=False,
        )
    raise ValueError(
        "failed to fit a cubic B-spline within tolerance "
        f"{tolerance:g}; best max_error={best_result.max_error:g} with "
        f"{best_result.control_count} control points"
    )


__all__ = ["BSplineFitResult", "fit_cubic_bspline_control_points"]
