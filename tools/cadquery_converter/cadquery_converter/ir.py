"""Plane frames and numeric helpers for CadQuery lowering."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

Number = float
Vec3 = Tuple[float, float, float]


@dataclass
class ParameterSpec:
    name: str
    default: Number
    unit: str = "mm"
    comment: str = ""


@dataclass
class FeatureStep:
    index: int
    kind: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeatureProgram:
    graph_id: str
    stem: str = ""
    family: str = ""
    source_plane: str = "XY"
    parameters: List[ParameterSpec] = field(default_factory=list)
    steps: List[FeatureStep] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


PLANE_TABLE: Dict[str, Dict[str, Vec3]] = {
    "XY": {
        "normal": (0.0, 0.0, 1.0),
        "u": (1.0, 0.0, 0.0),
        "v": (0.0, 1.0, 0.0),
        "extrude": (0.0, 0.0, 1.0),
    },
    "XZ": {
        "normal": (0.0, -1.0, 0.0),
        "u": (1.0, 0.0, 0.0),
        "v": (0.0, 0.0, 1.0),
        "extrude": (0.0, -1.0, 0.0),
    },
    "YZ": {
        "normal": (1.0, 0.0, 0.0),
        "u": (0.0, 1.0, 0.0),
        "v": (0.0, 0.0, 1.0),
        "extrude": (1.0, 0.0, 0.0),
    },
}


def plane_vectors(name: str) -> Dict[str, Vec3]:
    return PLANE_TABLE.get(str(name).upper(), PLANE_TABLE["XY"])


def add_vec(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def scale_vec(v: Vec3, s: float) -> Vec3:
    return (v[0] * s, v[1] * s, v[2] * s)


def local_to_global(plane: str, origin: Vec3, local: Vec3) -> Vec3:
    frame = plane_vectors(plane)
    u, v, n = frame["u"], frame["v"], frame["normal"]
    return add_vec(
        origin,
        (
            local[0] * u[0] + local[1] * v[0] + local[2] * n[0],
            local[0] * u[1] + local[1] * v[1] + local[2] * n[1],
            local[0] * u[2] + local[1] * v[2] + local[2] * n[2],
        ),
    )


def point_on_plane(plane: str, origin: Vec3, xy: Tuple[float, float], z: float = 0.0) -> Vec3:
    return local_to_global(plane, origin, (xy[0], xy[1], z))


def fmt_num(value: Number) -> str:
    if isinstance(value, float):
        # Keep enough digits that tilted 3D wires stay coplanar after round-trip.
        text = f"{value:.12g}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return str(value)


def fmt_vec(vec: Sequence[float]) -> str:
    return f"({', '.join(fmt_num(float(v)) for v in vec)})"


def regular_polygon_points(
    n_sides: int,
    diameter: float,
    plane: str,
    origin: Vec3,
) -> List[Vec3]:
    radius = float(diameter) / 2.0
    points: List[Vec3] = []
    for index in range(int(n_sides)):
        angle = 2.0 * math.pi * index / float(n_sides)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        points.append(point_on_plane(plane, origin, (x, y), 0.0))
    return points
