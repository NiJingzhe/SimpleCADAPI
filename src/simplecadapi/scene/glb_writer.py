"""Exact GLB writer for the Scene 1.0 OCP render profile."""

from __future__ import annotations

import struct

from .canonical import canonical_json_bytes
from .glb import preflight_glb
from .render_mesh import RenderEdgeMesh, RenderMesh


def write_triangle_glb(mesh: RenderMesh) -> bytes:
    positions = b"".join(struct.pack("<fff", *point) for point in mesh.positions)
    normals = b"".join(struct.pack("<fff", *normal) for normal in mesh.normals)
    index_component_type, index_format = _index_format(len(mesh.positions))
    indices = b"".join(struct.pack(index_format, index) for index in mesh.indices)
    return _write_glb(
        kind="triangle",
        positions=positions,
        normals=normals,
        indices=indices,
        index_component_type=index_component_type,
        index_view=2,
        index_count=len(mesh.indices),
        bounds=mesh.bounds,
    )


def write_line_glb(mesh: RenderEdgeMesh) -> bytes:
    positions = b"".join(struct.pack("<fff", *point) for point in mesh.positions)
    index_component_type, index_format = _index_format(len(mesh.positions))
    indices = b"".join(struct.pack(index_format, index) for index in mesh.indices)
    return _write_glb(
        kind="line",
        positions=positions,
        normals=None,
        indices=indices,
        index_component_type=index_component_type,
        index_view=1,
        index_count=len(mesh.indices),
        bounds=mesh.bounds,
    )


def _write_glb(
    *,
    kind: str,
    positions: bytes,
    normals: bytes | None,
    indices: bytes,
    index_component_type: int,
    index_view: int,
    index_count: int,
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> bytes:
    vertex_count = len(positions) // 12
    bin_data = bytearray(positions)
    views = [
        {"buffer": 0, "byteLength": len(positions), "byteOffset": 0, "target": 34962}
    ]
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": vertex_count,
            "max": list(bounds[1]),
            "min": list(bounds[0]),
            "type": "VEC3",
        }
    ]
    if kind == "triangle":
        assert normals is not None
        _pad4(bin_data)
        normal_offset = len(bin_data)
        bin_data.extend(normals)
        views.append(
            {"buffer": 0, "byteLength": len(normals), "byteOffset": normal_offset, "target": 34962}
        )
        accessors.append(
            {"bufferView": 1, "componentType": 5126, "count": vertex_count, "type": "VEC3"}
        )
    _pad4(bin_data)
    index_offset = len(bin_data)
    bin_data.extend(indices)
    views.append(
        {"buffer": 0, "byteLength": len(indices), "byteOffset": index_offset, "target": 34963}
    )
    accessors.append(
        {
            "bufferView": index_view,
            "componentType": index_component_type,
            "count": index_count,
            "type": "SCALAR",
        }
    )
    primitive = (
        {"attributes": {"NORMAL": 1, "POSITION": 0}, "indices": 2, "mode": 4}
        if kind == "triangle"
        else {"attributes": {"POSITION": 0}, "indices": 1, "mode": 1}
    )
    document = {
        "accessors": accessors,
        "asset": {"generator": "SimpleCAD Scene GLB Profile 1", "version": "2.0"},
        "bufferViews": views,
        "buffers": [{"byteLength": len(bin_data)}],
        "meshes": [{"primitives": [primitive]}],
        "nodes": [{"mesh": 0}],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
    }
    json_bytes = canonical_json_bytes(document)
    json_chunk = json_bytes + b" " * ((-len(json_bytes)) % 4)
    bin_chunk = bytes(bin_data) + b"\0" * ((-len(bin_data)) % 4)
    result = b"".join(
        (
            struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)),
            struct.pack("<II", len(json_chunk), 0x4E4F534A),
            json_chunk,
            struct.pack("<II", len(bin_chunk), 0x004E4942),
            bin_chunk,
        )
    )
    preflight_glb(result, expected_kind=kind)  # type: ignore[arg-type]
    return result


def _index_format(vertex_count: int) -> tuple[int, str]:
    return (5123, "<H") if vertex_count <= 65536 else (5125, "<I")


def _pad4(data: bytearray) -> None:
    data.extend(b"\0" * ((-len(data)) % 4))


__all__ = ["write_line_glb", "write_triangle_glb"]
