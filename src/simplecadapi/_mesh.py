"""Internal mesh companion data for SimpleCAD geometry.

This module intentionally stays out of the public API. Users should not need to
extract or manage meshes directly; future structural checks will consume this
cache internally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple

import numpy as np

from .kernel.ocp_mesh import tessellate_face


DEFAULT_LINEAR_TOLERANCE = 0.35
DEFAULT_ANGULAR_TOLERANCE = 0.22
MESH_RUNTIME_KEY = "mesh.default"
MESH_ERROR_RUNTIME_KEY = "mesh.error"


@dataclass(frozen=True)
class FaceTriangleRange:
    """Internal mapping from a source face to a contiguous triangle range."""

    face_index: int
    start: int
    count: int
    source_topo_id: str | None = None


@dataclass(frozen=True)
class TriMesh:
    """Internal triangle mesh data attached to OCP-backed solids."""

    vertices: np.ndarray
    triangles: np.ndarray
    face_triangle_ranges: Tuple[FaceTriangleRange, ...]
    linear_tolerance: float = DEFAULT_LINEAR_TOLERANCE
    angular_tolerance: float = DEFAULT_ANGULAR_TOLERANCE

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices, dtype=float)
        triangles = np.asarray(self.triangles, dtype=np.int64)

        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise ValueError("TriMesh vertices must have shape (n, 3)")
        if triangles.ndim != 2 or triangles.shape[1] != 3:
            raise ValueError("TriMesh triangles must have shape (m, 3)")
        if not np.all(np.isfinite(vertices)):
            raise ValueError("TriMesh vertices must be finite")
        if len(triangles) and (
            int(triangles.min()) < 0 or int(triangles.max()) >= len(vertices)
        ):
            raise ValueError("TriMesh triangle indices are out of bounds")

        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "triangles", triangles)

    @property
    def vertex_count(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def triangle_count(self) -> int:
        return int(self.triangles.shape[0])

    @property
    def bounds(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        if self.vertex_count == 0:
            zero = (0.0, 0.0, 0.0)
            return zero, zero
        lower = self.vertices.min(axis=0)
        upper = self.vertices.max(axis=0)
        return tuple(float(v) for v in lower), tuple(float(v) for v in upper)


def build_solid_trimesh(
    solid: Any,
    *,
    linear_tolerance: float = DEFAULT_LINEAR_TOLERANCE,
    angular_tolerance: float = DEFAULT_ANGULAR_TOLERANCE,
) -> TriMesh:
    """Build an internal triangle mesh from an OCP-backed Solid wrapper."""

    all_vertices: list[tuple[float, float, float]] = []
    all_triangles: list[tuple[int, int, int]] = []
    face_ranges: list[FaceTriangleRange] = []

    for face_index, face in enumerate(solid.get_faces()):
        start = len(all_triangles)
        vertices, triangles = tessellate_face(
            face.wrapped,
            tolerance=linear_tolerance,
            angular_tolerance=angular_tolerance,
        )
        vertex_offset = len(all_vertices)
        all_vertices.extend((float(x), float(y), float(z)) for x, y, z in vertices)
        all_triangles.extend(
            (
                int(a) + vertex_offset,
                int(b) + vertex_offset,
                int(c) + vertex_offset,
            )
            for a, b, c in triangles
        )
        face_ranges.append(
            FaceTriangleRange(
                face_index=face_index,
                start=start,
                count=len(all_triangles) - start,
                source_topo_id=getattr(face, "topo_id", None),
            )
        )

    return TriMesh(
        vertices=np.asarray(all_vertices, dtype=float).reshape((-1, 3)),
        triangles=np.asarray(all_triangles, dtype=np.int64).reshape((-1, 3)),
        face_triangle_ranges=tuple(face_ranges),
        linear_tolerance=float(linear_tolerance),
        angular_tolerance=float(angular_tolerance),
    )


def attach_default_mesh(solid: Any) -> None:
    """Attach the default internal mesh cache to a Solid wrapper if possible."""

    try:
        mesh = build_solid_trimesh(solid)
    except Exception as exc:
        _set_runtime(solid, MESH_ERROR_RUNTIME_KEY, str(exc))
        return

    _set_runtime(solid, MESH_RUNTIME_KEY, mesh)
    _set_runtime(solid, MESH_ERROR_RUNTIME_KEY, None)


def cached_mesh(solid: Any) -> TriMesh | None:
    """Return the internal mesh cache for tests and future checkers."""

    mesh = _get_runtime(solid, MESH_RUNTIME_KEY, None)
    return mesh if isinstance(mesh, TriMesh) else None


def mesh_error(solid: Any) -> str | None:
    """Return the internal mesh diagnostic for tests and future checkers."""

    value = _get_runtime(solid, MESH_ERROR_RUNTIME_KEY, None)
    return str(value) if value else None


def _set_runtime(shape: Any, key: str, value: Any) -> None:
    setter = getattr(shape, "_set_runtime", None)
    if callable(setter):
        setter(key, value)


def _get_runtime(shape: Any, key: str, default: Any) -> Any:
    getter = getattr(shape, "_get_runtime", None)
    if callable(getter):
        return getter(key, default)
    return default
