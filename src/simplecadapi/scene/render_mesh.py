"""Deterministic Scene 1.0 render and CAD-edge mesh construction."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from typing import Iterable, Sequence

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_TangentialDeflection
from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

from .._mesh import DEFAULT_ANGULAR_TOLERANCE, TriMesh, cached_mesh, mesh_error
from ..core import Solid
from ..kernel.ocp_properties import bounding_box
from ..scene.glb import profile_cross, profile_f32, profile_f32_bits, profile_normalize


ASSET_TO_SCENE = [1000, 0, 0, 0, 0, 0, -1000, 0, 0, 1000, 0, 0, 0, 0, 0, 1]


@dataclass(frozen=True, slots=True)
class CanonicalTriangleBlock:
    entity_id: str
    render_key: bytes
    block_bytes: bytes
    vertex_keys: tuple[bytes, ...]
    positions: tuple[tuple[float, float, float], ...]
    normals: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]


@dataclass(frozen=True, slots=True)
class CanonicalEdgeBlock:
    entity_id: str
    render_key: bytes
    block_bytes: bytes
    position_keys: tuple[bytes, ...]
    positions: tuple[tuple[float, float, float], ...]
    segments: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class RenderGroup:
    entity_id: str
    first_index: int
    index_count: int


@dataclass(frozen=True, slots=True)
class RenderMesh:
    positions: tuple[tuple[float, float, float], ...]
    normals: tuple[tuple[float, float, float], ...]
    indices: tuple[int, ...]
    groups: tuple[RenderGroup, ...]
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    blocks: tuple[CanonicalTriangleBlock, ...]


@dataclass(frozen=True, slots=True)
class RenderEdgeMesh:
    positions: tuple[tuple[float, float, float], ...]
    indices: tuple[int, ...]
    groups: tuple[RenderGroup, ...]
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    blocks: tuple[CanonicalEdgeBlock, ...]
    degenerate_entity_ids: tuple[str, ...]


def cad_to_gltf(point: Sequence[float] | object) -> tuple[float, float, float]:
    """Convert CAD mm/+Z coordinates to glTF m/+Y coordinates."""

    if hasattr(point, "X") and hasattr(point, "Y") and hasattr(point, "Z"):
        point = (float(point.X()), float(point.Y()), float(point.Z()))
    return (
        profile_f32(float(point[0]) / 1000.0),  # type: ignore[index]
        profile_f32(float(point[2]) / 1000.0),  # type: ignore[index]
        profile_f32(-float(point[1]) / 1000.0),  # type: ignore[index]
    )


def cad_direction_to_gltf(direction: Sequence[float]) -> tuple[float, float, float]:
    return cad_to_gltf(direction)


def build_render_mesh(
    solid: Solid,
    *,
    face_entity_ids: Sequence[str],
    linear_tolerance: float,
    angular_tolerance: float,
) -> RenderMesh:
    faces = solid.get_faces()
    if len(faces) != len(face_entity_ids):
        raise ValueError("face entity count does not match the solid topology")
    mesh = cached_mesh(
        solid,
        linear_tolerance=linear_tolerance,
        angular_tolerance=angular_tolerance,
    )
    if mesh is None:
        detail = mesh_error(solid) or "unknown evaluated mesh error"
        raise ValueError(f"solid evaluated mesh is unavailable: {detail}")
    blocks = tuple(
        _triangle_block(
            mesh,
            face_range=mesh.face_triangle_ranges[face_index],
            entity_id=entity_id,
        )
        for face_index, entity_id in enumerate(face_entity_ids)
    )
    ordered = tuple(sorted(blocks, key=lambda item: (item.render_key, item.block_bytes, item.entity_id.encode("utf-8"))))
    positions: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    indices: list[int] = []
    groups: list[RenderGroup] = []
    for block in ordered:
        offset = len(positions)
        positions.extend(block.positions)
        normals.extend(block.normals)
        indices.extend(offset + index for triangle in block.triangles for index in triangle)
        groups.append(
            RenderGroup(
                entity_id=block.entity_id,
                first_index=len(indices) - len(block.triangles) * 3,
                index_count=len(block.triangles) * 3,
            )
        )
    return RenderMesh(
        positions=tuple(positions),
        normals=tuple(normals),
        indices=tuple(indices),
        groups=tuple(sorted(groups, key=lambda item: item.first_index)),
        bounds=_bounds(positions),
        blocks=ordered,
    )


def build_edge_mesh(
    solid: Solid,
    *,
    edge_entity_ids: Sequence[str],
    linear_tolerance: float,
    angular_tolerance: float = DEFAULT_ANGULAR_TOLERANCE,
) -> RenderEdgeMesh:
    edges = solid.get_edges()
    if len(edges) != len(edge_entity_ids):
        raise ValueError("edge entity count does not match the solid topology")
    blocks = tuple(
        _edge_block(
            edge.wrapped,
            entity_id=entity_id,
            linear_tolerance=linear_tolerance,
            angular_tolerance=angular_tolerance,
        )
        for edge, entity_id in zip(edges, edge_entity_ids)
    )
    rendered = tuple(
        sorted(
            (block for block in blocks if block.segments),
            key=lambda item: (item.render_key, item.block_bytes, item.entity_id.encode("utf-8")),
        )
    )
    positions: list[tuple[float, float, float]] = []
    indices: list[int] = []
    groups: list[RenderGroup] = []
    for block in rendered:
        offset = len(positions)
        positions.extend(block.positions)
        indices.extend(offset + index for segment in block.segments for index in segment)
        groups.append(
            RenderGroup(
                entity_id=block.entity_id,
                first_index=len(indices) - len(block.segments) * 2,
                index_count=len(block.segments) * 2,
            )
        )
    return RenderEdgeMesh(
        positions=tuple(positions),
        indices=tuple(indices),
        groups=tuple(sorted(groups, key=lambda item: item.first_index)),
        bounds=_bounds(positions),
        blocks=rendered,
        degenerate_entity_ids=tuple(
            sorted((block.entity_id for block in blocks if not block.segments), key=lambda value: value.encode("utf-8"))
        ),
    )


def solid_asset_bounds(solid: Solid) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    box = bounding_box(solid.wrapped)
    return (
        (float(box.xmin), float(box.ymin), float(box.zmin)),
        (float(box.xmax), float(box.ymax), float(box.zmax)),
    )


def _prepare_shape(shape, *, force_forward: bool):
    oriented = shape.Oriented(TopAbs_FORWARD) if force_forward else shape
    location = oriented.Location()
    unlocated = oriented.Located(TopLoc_Location(), False)
    if location.IsIdentity():
        return unlocated
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform

    builder = BRepBuilderAPI_Transform(unlocated, location.Transformation(), True, False)
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP location bake failed")
    return builder.Shape()


def _triangle_block(
    mesh: TriMesh,
    *,
    face_range,
    entity_id: str,
) -> CanonicalTriangleBlock:
    vertex_records: dict[bytes, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
    triangle_keys: list[tuple[bytes, bytes, bytes]] = []
    triangle_start = face_range.start
    triangle_end = triangle_start + face_range.count
    for triangle_index in range(triangle_start, triangle_end):
        node_indices = tuple(int(index) for index in mesh.triangles[triangle_index])
        positions = tuple(cad_to_gltf(mesh.vertices[index]) for index in node_indices)
        if len(set(_position_key(position) for position in positions)) != 3:
            continue
        cross = profile_cross(
            tuple(positions[1][axis] - positions[0][axis] for axis in range(3)),
            tuple(positions[2][axis] - positions[0][axis] for axis in range(3)),
        )
        if all(component == 0.0 for component in cross):
            continue
        fallback_normal = profile_normalize(cross)
        keys: list[bytes] = []
        for corner in range(3):
            raw_normal = tuple(
                float(value) for value in mesh.corner_normals[triangle_index, corner]
            )
            normal = (
                fallback_normal
                if all(component == 0.0 for component in raw_normal)
                else profile_normalize(cad_direction_to_gltf(raw_normal))
            )
            position = positions[corner]
            key = _vertex_key(position, normal)
            vertex_records[key] = (position, normal)
            keys.append(key)
        triangle_keys.append(_least_cyclic_rotation(tuple(keys)))
    if not triangle_keys:
        raise ValueError(f"face {entity_id} has no non-degenerate triangle")
    unique_keys = sorted(set(key for triangle in triangle_keys for key in triangle))
    key_to_index = {key: index for index, key in enumerate(unique_keys)}
    triangles = tuple(sorted(tuple(key_to_index[key] for key in triangle) for triangle in triangle_keys))
    decoded = tuple(vertex_records[key] for key in unique_keys)
    vertex_bytes = b"".join(unique_keys)
    index_format = "<H" if len(unique_keys) <= 65536 else "<I"
    index_bytes = b"".join(struct.pack(index_format, index) for triangle in triangles for index in triangle)
    block_bytes = vertex_bytes + index_bytes
    return CanonicalTriangleBlock(
        entity_id=entity_id,
        render_key=hashlib.sha256(b"\x01" + block_bytes).digest(),
        block_bytes=block_bytes,
        vertex_keys=tuple(unique_keys),
        positions=tuple(item[0] for item in decoded),
        normals=tuple(item[1] for item in decoded),
        triangles=triangles,
    )


def _edge_block(
    edge,
    *,
    entity_id: str,
    linear_tolerance: float,
    angular_tolerance: float,
) -> CanonicalEdgeBlock:
    prepared = TopoDS.Edge_s(_prepare_shape(edge, force_forward=True))
    adaptor = BRepAdaptor_Curve(prepared)
    try:
        sampler = GCPnts_TangentialDeflection(
            adaptor,
            adaptor.FirstParameter(),
            adaptor.LastParameter(),
            float(angular_tolerance),
            float(linear_tolerance),
            2,
            1e-9,
            1e-7,
        )
    except Exception as exc:
        raise ValueError(f"edge {entity_id} discretization failed") from exc
    positions = tuple(
        cad_to_gltf(sampler.Value(index))
        for index in range(1, sampler.NbPoints() + 1)
    )
    segments = [
        (_position_key(positions[index]), _position_key(positions[index + 1]))
        for index in range(len(positions) - 1)
        if _position_key(positions[index]) != _position_key(positions[index + 1])
    ]
    position_keys = sorted(set(key for segment in segments for key in segment))
    key_to_index = {key: index for index, key in enumerate(position_keys)}
    canonical_segments = tuple(sorted(set((min(key_to_index[a], key_to_index[b]), max(key_to_index[a], key_to_index[b])) for a, b in segments)))
    decoded_positions = tuple(_decode_position(key) for key in position_keys)
    index_format = "<H" if len(position_keys) <= 65536 else "<I"
    index_bytes = b"".join(struct.pack(index_format, index) for segment in canonical_segments for index in segment)
    block_bytes = b"".join(position_keys) + index_bytes
    return CanonicalEdgeBlock(
        entity_id=entity_id,
        render_key=hashlib.sha256(b"\x02" + block_bytes).digest(),
        block_bytes=block_bytes,
        position_keys=tuple(position_keys),
        positions=decoded_positions,
        segments=canonical_segments,
    )


def _position_key(position: Sequence[float]) -> bytes:
    return struct.pack("<III", *(profile_f32_bits(float(value)) for value in position))


def _vertex_key(position: Sequence[float], normal: Sequence[float]) -> bytes:
    return _position_key(position) + struct.pack("<III", *(profile_f32_bits(float(value)) for value in normal))


def _decode_position(key: bytes) -> tuple[float, float, float]:
    return tuple(struct.unpack("<f", struct.pack("<I", bits))[0] for bits in struct.unpack("<III", key))  # type: ignore[return-value]


def _decode_vertex(key: bytes) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return _decode_position(key[:12]), _decode_position(key[12:])


def _least_cyclic_rotation(values: tuple[bytes, bytes, bytes]) -> tuple[bytes, bytes, bytes]:
    return min((values, values[1:] + values[:1], values[2:] + values[:2]))


def _bounds(points: Iterable[Sequence[float]]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    points = tuple(points)
    if not points:
        raise ValueError("render mesh cannot be empty")
    return (
        tuple(min(float(point[axis]) for point in points) for axis in range(3)),
        tuple(max(float(point[axis]) for point in points) for axis in range(3)),
    )  # type: ignore[return-value]


__all__ = [
    "ASSET_TO_SCENE",
    "CanonicalEdgeBlock",
    "CanonicalTriangleBlock",
    "RenderEdgeMesh",
    "RenderGroup",
    "RenderMesh",
    "build_edge_mesh",
    "build_render_mesh",
    "cad_direction_to_gltf",
    "cad_to_gltf",
    "solid_asset_bounds",
]
