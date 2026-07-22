"""Strict preflight for the two closed Scene 1.0 GLB profiles."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Any, Literal

from .canonical import canonical_json_bytes, parse_strict_json
from .resources import BASE_LIMITS, SceneResourceLimits


@dataclass(frozen=True)
class GlbInfo:
    kind: Literal["triangle", "line"]
    vertex_count: int
    index_count: int
    primitive_count: int
    decoded_buffer_bytes: int
    position_bounds: tuple[tuple[float, float, float], tuple[float, float, float]]


def _require_keys(value: Any, expected: set[str], context: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{context} fields do not match closed GLB profile")


def _integer(value: Any, context: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > 9_007_199_254_740_991
    ):
        raise ValueError(f"{context} must be a non-negative safe integer")
    return value


def _vec3(value: Any, context: str) -> tuple[float, float, float]:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or any(
            isinstance(component, bool) or not isinstance(component, (int, float))
            for component in value
        )
    ):
        raise ValueError(f"{context} must be a three-number array")
    result = tuple(float(component) for component in value)
    if not all(math.isfinite(component) for component in result):
        raise ValueError(f"{context} must contain finite values")
    return result  # type: ignore[return-value]


def profile_f32_bits(value: float) -> int:
    """Convert one binary64 value to canonical profile binary32 bits."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("f32 input must be a finite number")
    source = float(value)
    if not math.isfinite(source):
        raise ValueError("f32 input must be a finite number")
    try:
        encoded = struct.pack("<f", source)
    except OverflowError as exc:
        raise ValueError("f32 conversion overflowed") from exc
    bits = struct.unpack("<I", encoded)[0]
    if bits & 0x7F800000 == 0x7F800000:
        raise ValueError("f32 conversion overflowed")
    return 0 if bits == 0x80000000 else bits


def profile_f32(value: float) -> float:
    """Convert one value with the profile's binary32 and zero-sign rules."""

    return struct.unpack("<f", struct.pack("<I", profile_f32_bits(value)))[0]


def profile_cross(
    left: tuple[float, float, float] | list[float],
    right: tuple[float, float, float] | list[float],
) -> tuple[float, float, float]:
    """Evaluate the profile cross product in fixed binary64 operation order."""

    a = _vec3(list(left), "cross left")
    b = _vec3(list(right), "cross right")
    p1x, p2x = a[1] * b[2], a[2] * b[1]
    p1y, p2y = a[2] * b[0], a[0] * b[2]
    p1z, p2z = a[0] * b[1], a[1] * b[0]
    result = (p1x - p2x, p1y - p2y, p1z - p2z)
    if not all(math.isfinite(component) for component in result):
        raise ValueError("cross product produced a non-finite value")
    return result


def profile_normalize(
    value: tuple[float, float, float] | list[float],
) -> tuple[float, float, float]:
    """Normalize a vector using the profile's fixed binary64/binary32 steps."""

    vector = _vec3(list(value), "normalize input")
    squared = vector[0] * vector[0] + vector[1] * vector[1]
    squared = squared + vector[2] * vector[2]
    if not math.isfinite(squared) or squared <= 0:
        raise ValueError("normalize input has zero or non-finite length")
    length = math.sqrt(squared)
    result = tuple(profile_f32(component / length) for component in vector)
    norm_squared = result[0] * result[0] + result[1] * result[1]
    norm_squared = norm_squared + result[2] * result[2]
    norm = math.sqrt(norm_squared)
    if not 1.0 - 1e-6 <= norm <= 1.0 + 1e-6:
        raise ValueError("normalized binary32 vector is outside the profile tolerance")
    return result  # type: ignore[return-value]


def preflight_glb_counts(
    kind: Literal["triangle", "line"],
    vertex_count: int,
    index_count: int,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> int:
    """Validate kind-specific accessor counts before decoding GLB buffers."""

    vertex_count = _integer(vertex_count, "POSITION count")
    vertex_limit = (
        limits.triangle_vertices_per_asset
        if kind == "triangle"
        else limits.line_vertices_per_asset
    )
    if vertex_count == 0 or vertex_count > vertex_limit:
        raise ValueError("GLB vertex count is empty or exceeds resource limit")
    index_count = _integer(index_count, "index count")
    divisor = 3 if kind == "triangle" else 2
    primitive_count = index_count // divisor
    primitive_limit = (
        limits.triangles_per_asset
        if kind == "triangle"
        else limits.line_segments_per_asset
    )
    if index_count == 0 or index_count % divisor or primitive_count > primitive_limit:
        raise ValueError("GLB index count is invalid or exceeds resource limit")
    return primitive_count


def preflight_glb(
    data: bytes | bytearray | memoryview,
    *,
    expected_kind: Literal["triangle", "line"] | None = None,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> GlbInfo:
    """Validate exact Scene GLB JSON/BIN layout before a renderer sees bytes."""

    view = memoryview(data)
    if view.nbytes > limits.one_member_bytes:
        raise ValueError("GLB exceeds resource limit")
    raw = view.tobytes()
    if len(raw) < 28:
        raise ValueError("truncated GLB")
    magic, version, total_length = struct.unpack_from("<III", raw, 0)
    if magic != 0x46546C67 or version != 2 or total_length != len(raw):
        raise ValueError("invalid GLB header")
    json_length, json_type = struct.unpack_from("<II", raw, 12)
    if json_type != 0x4E4F534A or json_length % 4:
        raise ValueError("invalid GLB JSON chunk header")
    json_start = 20
    json_end = json_start + json_length
    if json_end + 8 > len(raw):
        raise ValueError("truncated GLB JSON chunk")
    json_padded = raw[json_start:json_end]
    json_bytes = json_padded.rstrip(b" ")
    if json_padded != json_bytes + b" " * ((-len(json_bytes)) % 4):
        raise ValueError("GLB JSON padding must use the minimal ASCII-space suffix")
    document = parse_strict_json(json_bytes)
    if not isinstance(document, dict) or canonical_json_bytes(document) != json_bytes:
        raise ValueError("GLB JSON chunk must be RFC 8785 canonical")
    bin_length, bin_type = struct.unpack_from("<II", raw, json_end)
    if bin_type != 0x004E4942 or bin_length % 4 or json_end + 8 + bin_length != len(raw):
        raise ValueError("invalid GLB BIN chunk header")
    bin_data = raw[json_end + 8 :]

    _require_keys(
        document,
        {"accessors", "asset", "bufferViews", "buffers", "meshes", "nodes", "scene", "scenes"},
        "GLB root",
    )
    if document["asset"] != {"generator": "SimpleCAD Scene GLB Profile 1", "version": "2.0"}:
        raise ValueError("GLB asset record does not match Scene profile")
    if (
        _integer(document["scene"], "GLB default scene") != 0
        or not isinstance(document["nodes"], list)
        or len(document["nodes"]) != 1
        or not isinstance(document["scenes"], list)
        or len(document["scenes"]) != 1
    ):
        raise ValueError("GLB scene/node skeleton does not match Scene profile")
    node = document["nodes"][0]
    scene = document["scenes"][0]
    _require_keys(node, {"mesh"}, "GLB node")
    _require_keys(scene, {"nodes"}, "GLB scene")
    if (
        _integer(node["mesh"], "GLB node mesh") != 0
        or scene["nodes"] != [0]
        or any(
            isinstance(node_index, bool) or not isinstance(node_index, int)
            for node_index in scene["nodes"]
        )
    ):
        raise ValueError("GLB scene/node skeleton does not match Scene profile")
    if not isinstance(document["meshes"], list) or len(document["meshes"]) != 1:
        raise ValueError("GLB must contain exactly one mesh")
    mesh = document["meshes"][0]
    _require_keys(mesh, {"primitives"}, "GLB mesh")
    if not isinstance(mesh["primitives"], list) or len(mesh["primitives"]) != 1:
        raise ValueError("GLB must contain exactly one primitive")
    primitive = mesh["primitives"][0]
    accessors = document["accessors"]
    views = document["bufferViews"]
    buffers = document["buffers"]
    if not isinstance(accessors, list) or not isinstance(views, list):
        raise ValueError("GLB accessors/bufferViews skeleton is invalid")
    if (
        not isinstance(buffers, list)
        or len(buffers) != 1
        or not isinstance(buffers[0], dict)
    ):
        raise ValueError("GLB accessors/bufferViews/buffer skeleton is invalid")
    _require_keys(buffers[0], {"byteLength"}, "GLB buffer")
    buffer_byte_length = _integer(buffers[0]["byteLength"], "GLB buffer byteLength")

    _require_keys(primitive, {"attributes", "indices", "mode"}, "GLB primitive")
    attributes = primitive["attributes"]
    if not isinstance(attributes, dict):
        raise ValueError("GLB primitive attributes are invalid")
    attribute_indices = {
        name: _integer(accessor, f"GLB {name} attribute accessor")
        for name, accessor in attributes.items()
    }
    primitive_indices = _integer(primitive["indices"], "GLB primitive index accessor")
    primitive_mode = _integer(primitive["mode"], "GLB primitive mode")
    if attribute_indices == {"NORMAL": 1, "POSITION": 0} and primitive_indices == 2 and primitive_mode == 4:
        kind: Literal["triangle", "line"] = "triangle"
        accessor_count = view_count = 3
    elif attribute_indices == {"POSITION": 0} and primitive_indices == 1 and primitive_mode == 1:
        kind = "line"
        accessor_count = view_count = 2
    else:
        raise ValueError("GLB primitive does not match triangle or line profile")
    if expected_kind is not None and kind != expected_kind:
        raise ValueError(f"expected {expected_kind} GLB, got {kind}")
    if len(accessors) != accessor_count or len(views) != view_count:
        raise ValueError("GLB accessor/bufferView count mismatch")

    position = accessors[0]
    _require_keys(position, {"bufferView", "componentType", "count", "max", "min", "type"}, "POSITION accessor")
    vertex_count = _integer(position["count"], "POSITION count")
    if (
        _integer(position["bufferView"], "POSITION bufferView") != 0
        or _integer(position["componentType"], "POSITION componentType") != 5126
        or position["type"] != "VEC3"
    ):
        raise ValueError("invalid POSITION accessor")
    minimum = _vec3(position["min"], "POSITION min")
    maximum = _vec3(position["max"], "POSITION max")
    if any(low > high for low, high in zip(minimum, maximum)):
        raise ValueError("POSITION min exceeds max")

    if kind == "triangle":
        normal = accessors[1]
        _require_keys(normal, {"bufferView", "componentType", "count", "type"}, "NORMAL accessor")
        if (
            _integer(normal["bufferView"], "NORMAL bufferView") != 1
            or _integer(normal["componentType"], "NORMAL componentType") != 5126
            or _integer(normal["count"], "NORMAL count") != vertex_count
            or normal["type"] != "VEC3"
        ):
            raise ValueError("invalid NORMAL accessor")
        index = accessors[2]
        index_view = 2
    else:
        index = accessors[1]
        index_view = 1
    _require_keys(index, {"bufferView", "componentType", "count", "type"}, "index accessor")
    index_count = _integer(index["count"], "index count")
    primitive_count = preflight_glb_counts(
        kind, vertex_count, index_count, limits=limits
    )
    component_type = 5123 if vertex_count <= 65536 else 5125
    if (
        _integer(index["bufferView"], "index bufferView") != index_view
        or _integer(index["componentType"], "index componentType") != component_type
        or index["type"] != "SCALAR"
    ):
        raise ValueError("invalid GLB index accessor")

    expected_offset = 0
    for index_number, view in enumerate(views):
        _require_keys(view, {"buffer", "byteLength", "byteOffset", "target"}, f"bufferView[{index_number}]")
        view_buffer = _integer(view["buffer"], f"bufferView[{index_number}].buffer")
        view_offset = _integer(view["byteOffset"], f"bufferView[{index_number}].byteOffset")
        view_length = _integer(view["byteLength"], f"bufferView[{index_number}].byteLength")
        view_target = _integer(view["target"], f"bufferView[{index_number}].target")
        if view_buffer != 0 or view_offset != expected_offset:
            raise ValueError("GLB bufferView offset mismatch")
        expected_target = 34962 if index_number < index_view else 34963
        if view_target != expected_target:
            raise ValueError("GLB bufferView target mismatch")
        if index_number < index_view:
            expected_length = 12 * vertex_count
        else:
            expected_length = index_count * (2 if component_type == 5123 else 4)
        if view_length != expected_length:
            raise ValueError("GLB bufferView byteLength mismatch")
        expected_offset += expected_length
        expected_offset = (expected_offset + 3) & ~3
    unpadded_length = views[-1]["byteOffset"] + views[-1]["byteLength"]
    if buffer_byte_length != unpadded_length:
        raise ValueError("GLB buffer byteLength mismatch")
    if bin_length != ((unpadded_length + 3) & ~3):
        raise ValueError("GLB BIN chunk length mismatch")
    if any(bin_data[unpadded_length:]):
        raise ValueError("GLB BIN padding must be zero")

    position_bytes = bin_data[: 12 * vertex_count]
    values = struct.unpack("<" + "f" * (3 * vertex_count), position_bytes)
    positions = list(zip(values[0::3], values[1::3], values[2::3]))
    if not all(math.isfinite(component) for point in positions for component in point):
        raise ValueError("GLB POSITION contains non-finite values")
    position_bits = [
        struct.unpack_from("<III", position_bytes, index * 12)
        for index in range(vertex_count)
    ]
    if any(component == 0x80000000 for point in position_bits for component in point):
        raise ValueError("GLB float buffers must encode zero with positive sign")
    actual_min = tuple(min(point[axis] for point in positions) for axis in range(3))
    actual_max = tuple(max(point[axis] for point in positions) for axis in range(3))
    if minimum != actual_min or maximum != actual_max:
        raise ValueError("POSITION accessor bounds do not match buffer")
    if kind == "triangle":
        normal_offset = views[1]["byteOffset"]
        normal_values = struct.unpack_from("<" + "f" * (3 * vertex_count), bin_data, normal_offset)
        normal_bits = [
            struct.unpack_from("<III", bin_data, normal_offset + index * 12)
            for index in range(vertex_count)
        ]
        if any(component == 0x80000000 for vector in normal_bits for component in vector):
            raise ValueError("GLB float buffers must encode zero with positive sign")
        for start in range(0, len(normal_values), 3):
            vector = normal_values[start : start + 3]
            norm = math.sqrt(sum(component * component for component in vector))
            if not all(math.isfinite(component) for component in vector) or not 1.0 - 1e-6 <= norm <= 1.0 + 1e-6:
                raise ValueError("GLB NORMAL must be finite and normalized")
    index_offset = views[index_view]["byteOffset"]
    index_format = "H" if component_type == 5123 else "I"
    indices = struct.unpack_from("<" + index_format * index_count, bin_data, index_offset)
    if max(indices) >= vertex_count or len(set(indices)) != vertex_count:
        raise ValueError("GLB indices must be in range and reference every vertex")
    if kind == "triangle":
        triangles: list[tuple[int, int, int]] = []
        for start in range(0, index_count, 3):
            triple = indices[start : start + 3]
            rotations = (triple, triple[1:] + triple[:1], triple[2:] + triple[:2])
            if triple != min(rotations):
                raise ValueError("GLB triangle indices are not in canonical cyclic rotation")
            triangles.append(triple)
            a, b, c = (positions[index] for index in triple)
            ab = tuple(b[axis] - a[axis] for axis in range(3))
            ac = tuple(c[axis] - a[axis] for axis in range(3))
            cross = (
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            )
            if a == b or b == c or a == c or cross == (0.0, 0.0, 0.0):
                raise ValueError("GLB contains a collapsed triangle")
        if triangles != sorted(triangles):
            raise ValueError("GLB triangle records are not canonically sorted")
    else:
        segments: list[tuple[int, int]] = []
        for start in range(0, index_count, 2):
            pair = indices[start : start + 2]
            if pair[0] >= pair[1]:
                raise ValueError("GLB line indices are not in canonical endpoint order")
            segments.append(pair)
            if positions[pair[0]] == positions[pair[1]]:
                raise ValueError("GLB contains a collapsed line segment")
        if segments != sorted(set(segments)):
            raise ValueError("GLB line records are not sorted and unique")
    return GlbInfo(
        kind=kind,
        vertex_count=vertex_count,
        index_count=index_count,
        primitive_count=primitive_count,
        decoded_buffer_bytes=2 * sum(view["byteLength"] for view in views),
        position_bounds=(minimum, maximum),
    )
