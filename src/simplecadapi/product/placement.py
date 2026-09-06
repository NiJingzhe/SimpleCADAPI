"""Rigid placement values and frame composition helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

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

    @classmethod
    def from_exact_frame(
        cls,
        origin: Vec3,
        x_axis: Vec3,
        y_axis: Vec3,
        z_axis: Vec3,
    ) -> "Placement":
        """Build a Placement that keeps durable-boundary components verbatim.

        Tick frames are validated in tick space and must survive a
        reconstruct -> re-tick cycle bit-exactly, so orthonormality is
        checked (never recomputed) here.  Residual axis error stays below
        1e-9, far inside solver tolerances.
        """
        origin_value = _vec3(origin, field_name="origin")
        x_value = _vec3(x_axis, field_name="x_axis")
        y_value = _vec3(y_axis, field_name="y_axis")
        z_value = _vec3(z_axis, field_name="z_axis")
        for name, axis in (("x_axis", x_value), ("y_axis", y_value), ("z_axis", z_value)):
            if abs(_norm(axis) - 1.0) > 2.0e-6:
                raise ValueError(f"{name} must be a unit vector")
        for name, dot in (
            ("x_axis/y_axis", _dot(x_value, y_value)),
            ("x_axis/z_axis", _dot(x_value, z_value)),
            ("y_axis/z_axis", _dot(y_value, z_value)),
        ):
            if abs(dot) > 2.0e-6:
                raise ValueError(f"{name} must be orthogonal")
        if _dot(_cross(x_value, y_value), z_value) <= 0.9:
            raise ValueError("axes must define a right-handed frame")
        instance = cls.__new__(cls)
        object.__setattr__(instance, "origin", origin_value)
        object.__setattr__(instance, "x_axis", x_value)
        object.__setattr__(instance, "y_axis", y_value)
        object.__setattr__(instance, "z_axis", z_value)
        object.__setattr__(instance, "_metadata", {})
        object.__setattr__(instance, "_runtime", {})
        return instance

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


_POSITION_CHUNK_MM = 1.0e-9
_DIRECTION_CHUNK = 1.0e-9
_FRAME_KEYS = ("origin", "x_axis", "y_axis", "z_axis")
_TICK_UNIT_LENGTH = 1.0 / _DIRECTION_CHUNK


def _quantize_tick(value: float, chunk: float) -> int:
    return round(float(value) / chunk)

def _is_tick_vector(values: Any) -> bool:
    return (
        isinstance(values, (list, tuple))
        and len(values) == 3
        and all(isinstance(item, int) and not isinstance(item, bool) for item in values)
    )
def placement_ticks(value: Any) -> Dict[str, Any]:
    """Return the integer-tick identity form of a placement frame.

    Tick frames are the only representation that is hashed or persisted:
    they are exact integers, so canonical JSON bytes and content hashes are
    stable across save/load cycles regardless of floating-point noise.  The
    stored ``z_axis`` is authoritative (derived once from ``x_axis ×
    y_axis`` by :class:`Placement` at write time) and is never recomputed.
    """
    if isinstance(value, Mapping) and all(
        _is_tick_vector(value.get(key)) for key in _FRAME_KEYS
    ):
        return validate_placement_ticks(value)
    placement = value if isinstance(value, Placement) else Placement(**dict(value))
    return {
        "origin": [_quantize_tick(item, _POSITION_CHUNK_MM) for item in placement.origin],
        "x_axis": [_quantize_tick(item, _DIRECTION_CHUNK) for item in placement.x_axis],
        "y_axis": [_quantize_tick(item, _DIRECTION_CHUNK) for item in placement.y_axis],
        "z_axis": [_quantize_tick(item, _DIRECTION_CHUNK) for item in placement.z_axis],
    }


def placement_frame_mm(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a millimetre float frame from a tick (or legacy float) frame."""
    return placement_from_canonical(value).to_dict()


def validate_placement_ticks(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate a persisted tick frame with exact integer arithmetic."""
    if not isinstance(value, Mapping) or set(value) != set(_FRAME_KEYS):
        raise ValueError("tick frame fields must be exactly origin/x_axis/y_axis/z_axis")
    for key in _FRAME_KEYS:
        if not _is_tick_vector(value[key]):
            raise ValueError(f"{key} must be three integer ticks")
    squared = {
        name: sum(item * item for item in value[name])
        for name in ("x_axis", "y_axis", "z_axis")
    }
    max_error = 2.0e-6 * _TICK_UNIT_LENGTH
    for name, total in squared.items():
        low = (_TICK_UNIT_LENGTH - max_error) ** 2
        high = (_TICK_UNIT_LENGTH + max_error) ** 2
        if not low <= total <= high:
            raise ValueError(f"{name} must be a unit direction in tick form")
    dot = sum(a * b for a, b in zip(value["x_axis"], value["y_axis"]))
    if abs(dot) > 2.0e-6 * _TICK_UNIT_LENGTH**2:
        raise ValueError("x_axis and y_axis must be orthogonal in tick form")
    x, y, z = value["x_axis"], value["y_axis"], value["z_axis"]
    handedness = (
        (x[1] * y[2] - x[2] * y[1]) * z[0]
        + (x[2] * y[0] - x[0] * y[2]) * z[1]
        + (x[0] * y[1] - x[1] * y[0]) * z[2]
    )
    if handedness <= int(0.9 * _TICK_UNIT_LENGTH**3):
        raise ValueError("x_axis and y_axis must define a right-handed frame")
    return {key: list(value[key]) for key in _FRAME_KEYS}


def canonical_frame(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Tick form of a frame: persisted ticks validate in place, floats upgrade."""
    if isinstance(value, Mapping) and all(
        _is_tick_vector(value.get(key)) for key in _FRAME_KEYS
    ):
        return validate_placement_ticks(value)
    return placement_ticks(value)


def placement_from_canonical(value: Mapping[str, Any]) -> Placement:
    """Rebuild a runtime Placement from a tick frame (or a legacy float frame)."""
    if all(_is_tick_vector(value.get(key)) for key in _FRAME_KEYS):
        return Placement.from_exact_frame(
            tuple(item * _POSITION_CHUNK_MM for item in value["origin"]),
            tuple(item * _DIRECTION_CHUNK for item in value["x_axis"]),
            tuple(item * _DIRECTION_CHUNK for item in value["y_axis"]),
            tuple(item * _DIRECTION_CHUNK for item in value["z_axis"]),
        )
    frame = {key: tuple(value[key]) for key in _FRAME_KEYS if key in value}
    return Placement(**frame)


def compose_placements(parent: Placement, child: Placement) -> Placement:
    if not isinstance(parent, Placement):
        raise TypeError("parent must be a Placement")
    return parent.compose(child)


def identity_placement() -> Placement:
    return Placement((0.0, 0.0, 0.0))



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
    "placement_ticks",
    "validate_placement_ticks",
    "canonical_frame",
    "placement_from_canonical",
    "compose_placements",
    "identity_placement",
    "inverse_placement",
    "relative_placement",
    "rotate_z_placement",
    "translate_z_placement",
]
