"""Rigid placement values and frame composition helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from .._internal.semantic import SemanticValueMixin, _finite_float

Vec3 = Tuple[float, float, float]
_AXIS_TOLERANCE = 1e-9
_ORTHOGONAL_TOLERANCE = 1e-7

def _vec3(value: Any, *, field_name: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field_name} must be a 3-element tuple or list")
    return (
        _finite_float(value[0], field_name=f"{field_name}[0]"),
        _finite_float(value[1], field_name=f"{field_name}[1]"),
        _finite_float(value[2], field_name=f"{field_name}[2]"),
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(value: Vec3) -> float:
    return math.sqrt(_dot(value, value))


def _normalize_axis(value: Any, *, field_name: str) -> Vec3:
    vec = _vec3(value, field_name=field_name)
    length = _norm(vec)
    if length <= _AXIS_TOLERANCE:
        raise ValueError(f"{field_name} must be a non-zero vector")
    return (vec[0] / length, vec[1] / length, vec[2] / length)


@dataclass(frozen=True)
class Placement(SemanticValueMixin):
    """Right-handed placement mapping child-local coordinates to parent coordinates."""

    origin: Vec3
    x_axis: Vec3 = (1.0, 0.0, 0.0)
    y_axis: Vec3 = (0.0, 1.0, 0.0)
    z_axis: Vec3 = (0.0, 0.0, 1.0)
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        origin = _vec3(self.origin, field_name="origin")
        x_axis = _normalize_axis(self.x_axis, field_name="x_axis")
        y_axis = _normalize_axis(self.y_axis, field_name="y_axis")
        dot = abs(_dot(x_axis, y_axis))
        if dot > _ORTHOGONAL_TOLERANCE:
            raise ValueError("x_axis and y_axis must be orthogonal")
        z_axis = _cross(x_axis, y_axis)
        z_norm = _norm(z_axis)
        if z_norm <= _AXIS_TOLERANCE:
            raise ValueError("x_axis and y_axis must define a right-handed frame")
        z_axis = (z_axis[0] / z_norm, z_axis[1] / z_norm, z_axis[2] / z_norm)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)
        object.__setattr__(self, "z_axis", z_axis)

    def transform_point(self, point: Vec3) -> Vec3:
        local = _vec3(point, field_name="point")
        return (
            self.origin[0]
            + local[0] * self.x_axis[0]
            + local[1] * self.y_axis[0]
            + local[2] * self.z_axis[0],
            self.origin[1]
            + local[0] * self.x_axis[1]
            + local[1] * self.y_axis[1]
            + local[2] * self.z_axis[1],
            self.origin[2]
            + local[0] * self.x_axis[2]
            + local[1] * self.y_axis[2]
            + local[2] * self.z_axis[2],
        )

    def transform_vector(self, vector: Vec3) -> Vec3:
        local = _vec3(vector, field_name="vector")
        return (
            local[0] * self.x_axis[0]
            + local[1] * self.y_axis[0]
            + local[2] * self.z_axis[0],
            local[0] * self.x_axis[1]
            + local[1] * self.y_axis[1]
            + local[2] * self.z_axis[1],
            local[0] * self.x_axis[2]
            + local[1] * self.y_axis[2]
            + local[2] * self.z_axis[2],
        )

    def compose(self, child: "Placement") -> "Placement":
        if not isinstance(child, Placement):
            raise TypeError("child must be a Placement")
        return Placement(
            origin=self.transform_point(child.origin),
            x_axis=self.transform_vector(child.x_axis),
            y_axis=self.transform_vector(child.y_axis),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": list(self.origin),
            "x_axis": list(self.x_axis),
            "y_axis": list(self.y_axis),
            "z_axis": list(self.z_axis),
        }


def identity_placement() -> Placement:
    return Placement((0.0, 0.0, 0.0))


def compose_placements(parent: Placement, child: Placement) -> Placement:
    if not isinstance(parent, Placement):
        raise TypeError("parent must be a Placement")
    return parent.compose(child)


def inverse_placement(placement: Placement) -> Placement:
    if not isinstance(placement, Placement):
        raise TypeError("placement must be a Placement")
    origin = placement.origin
    x_axis = placement.x_axis
    y_axis = placement.y_axis
    z_axis = placement.z_axis
    return Placement(
        origin=(-_dot(origin, x_axis), -_dot(origin, y_axis), -_dot(origin, z_axis)),
        x_axis=(x_axis[0], y_axis[0], z_axis[0]),
        y_axis=(x_axis[1], y_axis[1], z_axis[1]),
    )


def relative_placement(base: Placement, target: Placement) -> Placement:
    return inverse_placement(base).compose(target)


def rotate_z_placement(angle_degrees: float) -> Placement:
    angle = math.radians(_finite_float(angle_degrees, field_name="angle_degrees"))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return Placement((0.0, 0.0, 0.0), x_axis=(cos_a, sin_a, 0.0), y_axis=(-sin_a, cos_a, 0.0))


def translate_z_placement(distance: float) -> Placement:
    return Placement((0.0, 0.0, _finite_float(distance, field_name="distance")))


__all__ = [
    "Placement",
    "compose_placements",
    "identity_placement",
    "inverse_placement",
    "relative_placement",
    "rotate_z_placement",
    "translate_z_placement",
]
