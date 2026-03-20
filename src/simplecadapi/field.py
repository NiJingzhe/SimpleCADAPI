"""Scalar field utilities for implicit modeling."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable, Tuple

import numpy as np


@dataclass(frozen=True)
class ScalarField:
    """Lightweight scalar field node for implicit modeling."""

    op: str
    params: dict[str, Any]
    children: Tuple["ScalarField", ...] = ()


def make_sphere_rscalarfield(
    center: Tuple[float, float, float], radius: float
) -> ScalarField:
    """Create a spherical scalar field.

    Args:
        center: Sphere center coordinates `(x, y, z)`.
        radius: Sphere radius.

    Returns:
        ScalarField: Sphere scalar field.
    """
    if radius <= 0:
        raise ValueError("radius 必须大于 0")
    return ScalarField("sphere", {"center": center, "radius": float(radius)})


def make_ellipsoid_rscalarfield(
    center: Tuple[float, float, float], radii: Tuple[float, float, float]
) -> ScalarField:
    """Create an ellipsoid scalar field.

    Args:
        center: Ellipsoid center coordinates `(x, y, z)`.
        radii: Radii `(rx, ry, rz)`.

    Returns:
        ScalarField: Ellipsoid scalar field.
    """
    rx, ry, rz = radii
    if rx <= 0 or ry <= 0 or rz <= 0:
        raise ValueError("radii 必须为正数")
    return ScalarField("ellipsoid", {"center": center, "radii": radii})


def make_box_rscalarfield(
    center: Tuple[float, float, float], size: Tuple[float, float, float]
) -> ScalarField:
    """Create an axis-aligned box scalar field.

    Args:
        center: Box center coordinates `(x, y, z)`.
        size: Box size `(sx, sy, sz)`.

    Returns:
        ScalarField: Box scalar field.
    """
    sx, sy, sz = size
    if sx <= 0 or sy <= 0 or sz <= 0:
        raise ValueError("size 必须为正数")
    return ScalarField("box", {"center": center, "size": size})


def make_capsule_rscalarfield(
    p0: Tuple[float, float, float],
    p1: Tuple[float, float, float],
    radius: float,
) -> ScalarField:
    """Create a capsule scalar field.

    Args:
        p0: First endpoint coordinates.
        p1: Second endpoint coordinates.
        radius: Capsule radius.

    Returns:
        ScalarField: Capsule scalar field.
    """
    if radius <= 0:
        raise ValueError("radius 必须大于 0")
    return ScalarField("capsule", {"p0": p0, "p1": p1, "radius": float(radius)})


def union_rscalarfield(*fields: ScalarField) -> ScalarField:
    """Create a union scalar field.

    Args:
        *fields: Input scalar fields.

    Returns:
        ScalarField: Union scalar field.
    """
    if not fields:
        raise ValueError("union_rscalarfield 至少需要一个输入")
    return ScalarField("union", {}, tuple(fields))


def intersect_rscalarfield(*fields: ScalarField) -> ScalarField:
    """Create an intersection scalar field.

    Args:
        *fields: Input scalar fields.

    Returns:
        ScalarField: Intersection scalar field.
    """
    if not fields:
        raise ValueError("intersect_rscalarfield 至少需要一个输入")
    return ScalarField("intersect", {}, tuple(fields))


def subtract_rscalarfield(a: ScalarField, b: ScalarField) -> ScalarField:
    """Create a subtraction scalar field.

    Args:
        a: Minuend scalar field.
        b: Subtrahend scalar field.

    Returns:
        ScalarField: Subtraction scalar field.
    """
    return ScalarField("subtract", {}, (a, b))


def smooth_union_rscalarfield(a: ScalarField, b: ScalarField, k: float) -> ScalarField:
    """Create a smooth union scalar field.

    Args:
        a: Scalar field A.
        b: Scalar field B.
        k: Smoothing factor, which must be positive.

    Returns:
        ScalarField: Smooth union scalar field.
    """
    if k <= 0:
        raise ValueError("k 必须为正")
    return ScalarField("smooth_union", {"k": float(k)}, (a, b))


def smooth_subtract_rscalarfield(
    a: ScalarField, b: ScalarField, k: float
) -> ScalarField:
    """Create a smooth subtraction scalar field.

    Args:
        a: Minuend scalar field.
        b: Subtrahend scalar field.
        k: Smoothing factor, which must be positive.

    Returns:
        ScalarField: Smooth subtraction scalar field.
    """
    if k <= 0:
        raise ValueError("k 必须为正")
    return ScalarField("smooth_subtract", {"k": float(k)}, (a, b))


def translate_rscalarfield(
    field: ScalarField, offset: Tuple[float, float, float]
) -> ScalarField:
    """Translate a scalar field.

    Args:
        field: Input scalar field.
        offset: Translation vector `(dx, dy, dz)`.

    Returns:
        ScalarField: Translated scalar field.
    """
    return ScalarField("translate", {"offset": offset}, (field,))


def scale_rscalarfield(
    field: ScalarField, factors: Tuple[float, float, float]
) -> ScalarField:
    """Scale a scalar field around the origin.

    Args:
        field: Input scalar field.
        factors: Scale factors `(sx, sy, sz)`.

    Returns:
        ScalarField: Scaled scalar field.
    """
    sx, sy, sz = factors
    if sx == 0 or sy == 0 or sz == 0:
        raise ValueError("scale 系数不能为 0")
    return ScalarField("scale", {"factors": factors}, (field,))


def rotate_rscalarfield(
    field: ScalarField,
    axis: Tuple[float, float, float],
    angle_degrees: float,
) -> ScalarField:
    """Rotate a scalar field around the origin.

    Args:
        field: Input scalar field.
        axis: Rotation axis vector `(x, y, z)`.
        angle_degrees: Rotation angle in degrees.

    Returns:
        ScalarField: Rotated scalar field.
    """
    return ScalarField(
        "rotate", {"axis": axis, "angle": float(angle_degrees)}, (field,)
    )


def eval_rscalar(field: ScalarField, x: float, y: float, z: float) -> float:
    """Evaluate a scalar field at a single point.

    Args:
        field: Scalar field.
        x: X coordinate.
        y: Y coordinate.
        z: Z coordinate.

    Returns:
        float: Field value.
    """
    value = eval_rarray(field, np.array([[x]]), np.array([[y]]), np.array([[z]]))
    return float(value.reshape(-1)[0])


def eval_rarray(
    field: ScalarField, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
) -> np.ndarray:
    """Evaluate a scalar field on arrays of points.

    Args:
        field: Scalar field.
        xs: Array of X coordinates.
        ys: Array of Y coordinates.
        zs: Array of Z coordinates.

    Returns:
        np.ndarray: Array of field values.
    """
    return _eval_node(field, np.asarray(xs), np.asarray(ys), np.asarray(zs))


def bounds_rbbox(
    field: ScalarField,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Compute the axis-aligned bounding box of a scalar field.

    Args:
        field: Scalar field.

    Returns:
        Tuple[min_xyz, max_xyz]: Bounding box.
    """
    return _bounds_node(field)


def _rotation_matrix(
    axis: Tuple[float, float, float], angle_degrees: float
) -> np.ndarray:
    ax = np.array(axis, dtype=float)
    norm = np.linalg.norm(ax)
    if norm == 0:
        raise ValueError("axis 不能为零向量")
    ax = ax / norm
    angle = math.radians(angle_degrees)
    c = math.cos(angle)
    s = math.sin(angle)
    x, y, z = ax
    return np.array(
        [
            [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
        ],
        dtype=float,
    )


def _apply_rotation(xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, rot: np.ndarray):
    flat = np.stack([xs, ys, zs], axis=0).reshape(3, -1)
    rotated = rot @ flat
    reshaped = rotated.reshape((3,) + xs.shape)
    return reshaped[0], reshaped[1], reshaped[2]


def _eval_node(
    field: ScalarField, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
) -> np.ndarray:
    op = field.op
    params = field.params

    if op == "sphere":
        cx, cy, cz = params["center"]
        r = params["radius"]
        return (xs - cx) ** 2 + (ys - cy) ** 2 + (zs - cz) ** 2 - r * r

    if op == "ellipsoid":
        cx, cy, cz = params["center"]
        rx, ry, rz = params["radii"]
        return (
            ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 + ((zs - cz) / rz) ** 2 - 1.0
        )

    if op == "box":
        cx, cy, cz = params["center"]
        sx, sy, sz = params["size"]
        hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
        dx = np.abs(xs - cx) - hx
        dy = np.abs(ys - cy) - hy
        dz = np.abs(zs - cz) - hz
        return np.maximum.reduce([dx, dy, dz])

    if op == "capsule":
        p0 = np.array(params["p0"], dtype=float)
        p1 = np.array(params["p1"], dtype=float)
        r = params["radius"]
        d = p1 - p0
        denom = float(np.dot(d, d))
        if denom == 0:
            return (
                np.sqrt((xs - p0[0]) ** 2 + (ys - p0[1]) ** 2 + (zs - p0[2]) ** 2) - r
            )
        px = xs - p0[0]
        py = ys - p0[1]
        pz = zs - p0[2]
        t = (px * d[0] + py * d[1] + pz * d[2]) / denom
        t = np.clip(t, 0.0, 1.0)
        qx = p0[0] + t * d[0]
        qy = p0[1] + t * d[1]
        qz = p0[2] + t * d[2]
        return np.sqrt((xs - qx) ** 2 + (ys - qy) ** 2 + (zs - qz) ** 2) - r

    if op == "union":
        values = [_eval_node(child, xs, ys, zs) for child in field.children]
        return np.minimum.reduce(values)

    if op == "intersect":
        values = [_eval_node(child, xs, ys, zs) for child in field.children]
        return np.maximum.reduce(values)

    if op == "subtract":
        a, b = field.children
        return np.maximum(_eval_node(a, xs, ys, zs), -_eval_node(b, xs, ys, zs))

    if op == "smooth_union":
        a, b = field.children
        k = params["k"]
        fa = _eval_node(a, xs, ys, zs)
        fb = _eval_node(b, xs, ys, zs)
        h = np.clip(0.5 + 0.5 * (fb - fa) / k, 0.0, 1.0)
        return fb * (1 - h) + fa * h - k * h * (1 - h)

    if op == "smooth_subtract":
        a, b = field.children
        k = params["k"]
        fa = _eval_node(a, xs, ys, zs)
        fb = _eval_node(b, xs, ys, zs)
        h = np.clip(0.5 + 0.5 * (fb + fa) / k, 0.0, 1.0)
        return fa * h - fb * (1 - h) + k * h * (1 - h)

    if op == "translate":
        dx, dy, dz = params["offset"]
        child = field.children[0]
        return _eval_node(child, xs - dx, ys - dy, zs - dz)

    if op == "scale":
        sx, sy, sz = params["factors"]
        child = field.children[0]
        scale = min(abs(sx), abs(sy), abs(sz))
        return _eval_node(child, xs / sx, ys / sy, zs / sz) * scale

    if op == "rotate":
        child = field.children[0]
        rot = _rotation_matrix(params["axis"], params["angle"])
        inv_rot = rot.T
        rx, ry, rz = _apply_rotation(xs, ys, zs, inv_rot)
        return _eval_node(child, rx, ry, rz)

    raise ValueError(f"未知的标量场操作: {op}")


def _bounds_node(
    field: ScalarField,
) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    op = field.op
    params = field.params

    if op == "sphere":
        cx, cy, cz = params["center"]
        r = params["radius"]
        return (cx - r, cy - r, cz - r), (cx + r, cy + r, cz + r)

    if op == "ellipsoid":
        cx, cy, cz = params["center"]
        rx, ry, rz = params["radii"]
        return (cx - rx, cy - ry, cz - rz), (cx + rx, cy + ry, cz + rz)

    if op == "box":
        cx, cy, cz = params["center"]
        sx, sy, sz = params["size"]
        hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
        return (cx - hx, cy - hy, cz - hz), (cx + hx, cy + hy, cz + hz)

    if op == "capsule":
        p0 = np.array(params["p0"], dtype=float)
        p1 = np.array(params["p1"], dtype=float)
        r = params["radius"]
        mins = np.minimum(p0, p1) - r
        maxs = np.maximum(p0, p1) + r
        return tuple(mins.tolist()), tuple(maxs.tolist())

    if op == "union":
        bounds = [_bounds_node(child) for child in field.children]
        mins = np.min([b[0] for b in bounds], axis=0)
        maxs = np.max([b[1] for b in bounds], axis=0)
        return tuple(mins.tolist()), tuple(maxs.tolist())

    if op == "intersect":
        bounds = [_bounds_node(child) for child in field.children]
        mins = np.max([b[0] for b in bounds], axis=0)
        maxs = np.min([b[1] for b in bounds], axis=0)
        return tuple(mins.tolist()), tuple(maxs.tolist())

    if op == "subtract":
        return _bounds_node(field.children[0])

    if op == "smooth_union":
        return _bounds_node(union_rscalarfield(*field.children))

    if op == "smooth_subtract":
        return _bounds_node(field.children[0])

    if op == "translate":
        (xmin, ymin, zmin), (xmax, ymax, zmax) = _bounds_node(field.children[0])
        dx, dy, dz = params["offset"]
        return (xmin + dx, ymin + dy, zmin + dz), (xmax + dx, ymax + dy, zmax + dz)

    if op == "scale":
        (xmin, ymin, zmin), (xmax, ymax, zmax) = _bounds_node(field.children[0])
        sx, sy, sz = params["factors"]
        mins = np.array([xmin * sx, ymin * sy, zmin * sz], dtype=float)
        maxs = np.array([xmax * sx, ymax * sy, zmax * sz], dtype=float)
        return tuple(np.minimum(mins, maxs).tolist()), tuple(
            np.maximum(mins, maxs).tolist()
        )

    if op == "rotate":
        (xmin, ymin, zmin), (xmax, ymax, zmax) = _bounds_node(field.children[0])
        corners = np.array(
            [
                [xmin, ymin, zmin],
                [xmax, ymin, zmin],
                [xmax, ymax, zmin],
                [xmin, ymax, zmin],
                [xmin, ymin, zmax],
                [xmax, ymin, zmax],
                [xmax, ymax, zmax],
                [xmin, ymax, zmax],
            ],
            dtype=float,
        )
        rot = _rotation_matrix(params["axis"], params["angle"])
        rotated = (rot @ corners.T).T
        mins = rotated.min(axis=0)
        maxs = rotated.max(axis=0)
        return tuple(mins.tolist()), tuple(maxs.tolist())

    raise ValueError(f"未知的标量场操作: {op}")
