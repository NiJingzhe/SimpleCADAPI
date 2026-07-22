"""GLB and ZIP fixture construction, mutation, and case records."""

from __future__ import annotations

import binascii
import struct
import zlib
from copy import deepcopy
from typing import Callable

from simplecadapi.scene import (
    canonical_json_bytes,
    canonical_zip_bytes,
    parse_strict_json,
    preflight_glb,
    preflight_zip_bytes,
)

from .common import JsonObject, b64


LOCAL = struct.Struct("<IHHHHHIIIHH")
CENTRAL = struct.Struct("<IHHHHHHIIIHHHHHII")
EOCD = struct.Struct("<IHHHHIIH")


def _f32(value: float) -> float:
    result = struct.unpack("<f", struct.pack("<f", value))[0]
    return 0.0 if result == 0 else result


def glb(
    kind: str,
    positions: list[tuple[float, float, float]],
    indices: list[int],
    normals: list[tuple[float, float, float]] | None = None,
) -> bytes:
    positions = [tuple(_f32(component) for component in point) for point in positions]
    position_bytes = b"".join(struct.pack("<fff", *point) for point in positions)
    chunks = [position_bytes]
    views = [
        {"buffer": 0, "byteLength": len(position_bytes), "byteOffset": 0, "target": 34962}
    ]
    accessors = [
        {
            "bufferView": 0,
            "componentType": 5126,
            "count": len(positions),
            "max": [max(point[axis] for point in positions) for axis in range(3)],
            "min": [min(point[axis] for point in positions) for axis in range(3)],
            "type": "VEC3",
        }
    ]
    if kind == "triangle":
        assert normals is not None
        normals = [tuple(_f32(component) for component in vector) for vector in normals]
        normal_bytes = b"".join(struct.pack("<fff", *vector) for vector in normals)
        views.append(
            {
                "buffer": 0,
                "byteLength": len(normal_bytes),
                "byteOffset": len(position_bytes),
                "target": 34962,
            }
        )
        accessors.append(
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": len(normals),
                "type": "VEC3",
            }
        )
        chunks.append(normal_bytes)
        index_view = 2
        attributes = {"NORMAL": 1, "POSITION": 0}
        mode = 4
    else:
        index_view = 1
        attributes = {"POSITION": 0}
        mode = 1
    prefix = b"".join(chunks)
    prefix += b"\0" * ((-len(prefix)) % 4)
    component_type = 5123 if len(positions) <= 65536 else 5125
    index_format = "H" if component_type == 5123 else "I"
    index_bytes = struct.pack("<" + index_format * len(indices), *indices)
    views.append(
        {
            "buffer": 0,
            "byteLength": len(index_bytes),
            "byteOffset": len(prefix),
            "target": 34963,
        }
    )
    accessors.append(
        {
            "bufferView": index_view,
            "componentType": component_type,
            "count": len(indices),
            "type": "SCALAR",
        }
    )
    unpadded_bin = prefix + index_bytes
    document = {
        "accessors": accessors,
        "asset": {"generator": "SimpleCAD Scene GLB Profile 1", "version": "2.0"},
        "bufferViews": views,
        "buffers": [{"byteLength": len(unpadded_bin)}],
        "meshes": [
            {"primitives": [{"attributes": attributes, "indices": index_view, "mode": mode}]}
        ],
        "nodes": [{"mesh": 0}],
        "scene": 0,
        "scenes": [{"nodes": [0]}],
    }
    json_bytes = canonical_json_bytes(document)
    json_chunk = json_bytes + b" " * ((-len(json_bytes)) % 4)
    bin_chunk = unpadded_bin + b"\0" * ((-len(unpadded_bin)) % 4)
    total_length = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return b"".join(
        (
            struct.pack("<III", 0x46546C67, 2, total_length),
            struct.pack("<II", len(json_chunk), 0x4E4F534A),
            json_chunk,
            struct.pack("<II", len(bin_chunk), 0x004E4942),
            bin_chunk,
        )
    )


def replace_glb_json(data: bytes, mutate: Callable[[JsonObject], None]) -> bytes:
    json_length = struct.unpack_from("<I", data, 12)[0]
    document = parse_strict_json(data[20 : 20 + json_length].rstrip(b" "))
    mutate(document)
    replacement = canonical_json_bytes(document)
    replacement += b" " * ((-len(replacement)) % 4)
    bin_header = 20 + json_length
    bin_chunk = data[bin_header:]
    return b"".join(
        (
            struct.pack(
                "<III", 0x46546C67, 2, 12 + 8 + len(replacement) + len(bin_chunk)
            ),
            struct.pack("<II", len(replacement), 0x4E4F534A),
            replacement,
            bin_chunk,
        )
    )


def _deflate_zip(members: dict[str, bytes]) -> bytes:
    local_parts: list[bytes] = []
    central_parts: list[bytes] = []
    local_offset = 0
    for name in sorted(members, key=lambda value: value.encode("ascii")):
        name_bytes = name.encode("ascii")
        payload = members[name]
        compressor = zlib.compressobj(level=9, wbits=-zlib.MAX_WBITS)
        compressed = compressor.compress(payload) + compressor.flush()
        crc = binascii.crc32(payload) & 0xFFFFFFFF
        local_header = LOCAL.pack(
            0x04034B50,
            20,
            0x0800,
            8,
            0,
            0x0021,
            crc,
            len(compressed),
            len(payload),
            len(name_bytes),
            0,
        )
        local_parts.extend((local_header, name_bytes, compressed))
        central_parts.extend(
            (
                CENTRAL.pack(
                    0x02014B50,
                    0x0314,
                    20,
                    0x0800,
                    8,
                    0,
                    0x0021,
                    crc,
                    len(compressed),
                    len(payload),
                    len(name_bytes),
                    0,
                    0,
                    0,
                    0,
                    0x81A40000,
                    local_offset,
                ),
                name_bytes,
            )
        )
        local_offset += len(local_header) + len(name_bytes) + len(compressed)
    central = b"".join(central_parts)
    return b"".join(local_parts) + central + EOCD.pack(
        0x06054B50,
        0,
        0,
        len(members),
        len(members),
        len(central),
        local_offset,
        0,
    )


def _replace_u16(data: bytes, offset: int, value: int) -> bytes:
    result = bytearray(data)
    struct.pack_into("<H", result, offset, value)
    return bytes(result)


def _replace_u32(data: bytes, offset: int, value: int) -> bytes:
    result = bytearray(data)
    struct.pack_into("<I", result, offset, value)
    return bytes(result)


def _glb_bin_start(data: bytes) -> int:
    return 28 + struct.unpack_from("<I", data, 12)[0]


def _replace_glb_bin_u32(data: bytes, relative_offset: int, value: int) -> bytes:
    return _replace_u32(data, _glb_bin_start(data) + relative_offset, value)


def _set_path(value: object, path: tuple[object, ...], replacement: object) -> None:
    current = value
    for part in path[:-1]:
        current = current[part]  # type: ignore[index]
    current[path[-1]] = replacement  # type: ignore[index]


def _add_path(value: object, path: tuple[object, ...], key: str, item: object) -> None:
    current = value
    for part in path:
        current = current[part]  # type: ignore[index]
    current[key] = item  # type: ignore[index]


def _append_path(value: object, path: tuple[object, ...], item: object) -> None:
    current = value
    for part in path:
        current = current[part]  # type: ignore[index]
    current.append(item)  # type: ignore[attr-defined]


def _nonminimal_glb_json_padding(data: bytes) -> bytes:
    json_length = struct.unpack_from("<I", data, 12)[0]
    json_end = 20 + json_length
    result = data[:json_end] + b"    " + data[json_end:]
    result = _replace_u32(result, 8, len(result))
    return _replace_u32(result, 12, json_length + 4)


def _append_glb_bin_word(data: bytes, value: int = 0) -> bytes:
    json_length = struct.unpack_from("<I", data, 12)[0]
    bin_header = 20 + json_length
    bin_length = struct.unpack_from("<I", data, bin_header)[0]
    result = data + struct.pack("<I", value)
    result = _replace_u32(result, 8, len(result))
    return _replace_u32(result, bin_header, bin_length + 4)


def _f32_from_bits(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value))[0]


def _glb_case(
    name: str,
    payload: bytes,
    expected_kind: str,
    valid: bool,
) -> dict[str, object]:
    try:
        info = preflight_glb(payload, expected_kind=expected_kind)
        error = None
        actual_valid = True
        actual_kind = info.kind
    except ValueError as exc:
        error = str(exc)
        actual_valid = False
        actual_kind = None
    assert actual_valid == valid, name
    return {
        "error": error,
        "expected_kind": expected_kind,
        "kind": actual_kind,
        "name": name,
        "payload_base64": b64(payload),
        "valid": valid,
    }


def _zip_case(
    name: str,
    payload: bytes,
    valid: bool,
    used_deflate: bool | None,
) -> dict[str, object]:
    try:
        info = preflight_zip_bytes(payload)
        error = None
        actual_valid = True
        actual_deflate = info.used_deflate
    except ValueError as exc:
        error = str(exc)
        actual_valid = False
        actual_deflate = None
    assert actual_valid == valid, name
    assert actual_deflate == used_deflate, name
    return {
        "error": error,
        "name": name,
        "payload_base64": b64(payload),
        "used_deflate": used_deflate,
        "valid": valid,
    }


def _zip_layout(data: bytes) -> tuple[list[tuple[int, int, int]], int, int]:
    eocd = len(data) - EOCD.size
    count = struct.unpack_from("<H", data, eocd + 10)[0]
    central = struct.unpack_from("<I", data, eocd + 16)[0]
    entries: list[tuple[int, int, int]] = []
    cursor = central
    for _index in range(count):
        name_length = struct.unpack_from("<H", data, cursor + 28)[0]
        extra_length = struct.unpack_from("<H", data, cursor + 30)[0]
        comment_length = struct.unpack_from("<H", data, cursor + 32)[0]
        local_offset = struct.unpack_from("<I", data, cursor + 42)[0]
        entries.append((cursor, local_offset, name_length))
        cursor += CENTRAL.size + name_length + extra_length + comment_length
    return entries, central, eocd


def _replace_zip_name(data: bytes, index: int, name: bytes) -> bytes:
    entries, _central, _eocd = _zip_layout(data)
    central_offset, local_offset, name_length = entries[index]
    assert len(name) == name_length
    assert struct.unpack_from("<H", data, local_offset + 26)[0] == name_length
    result = bytearray(data)
    result[local_offset + LOCAL.size : local_offset + LOCAL.size + name_length] = name
    result[central_offset + CENTRAL.size : central_offset + CENTRAL.size + name_length] = name
    return bytes(result)


def _zip_with_prefix(data: bytes) -> bytes:
    entries, central, eocd = _zip_layout(data)
    result = bytearray(b"x" + data)
    for central_offset, local_offset, _name_length in entries:
        struct.pack_into("<I", result, central_offset + 1 + 42, local_offset + 1)
    struct.pack_into("<I", result, eocd + 1 + 16, central + 1)
    return bytes(result)


def _zip_with_local_gap(data: bytes) -> bytes:
    _entries, central, eocd = _zip_layout(data)
    result = bytearray(data[:central] + b"x" + data[central:])
    struct.pack_into("<I", result, eocd + 1 + 16, central + 1)
    return bytes(result)


def build_binary_cases(
    triangle_glb: bytes,
    line_glb: bytes,
    members: dict[str, bytes],
) -> tuple[bytes, bytes, list[dict[str, object]], list[dict[str, object]]]:
    canonical_zip = canonical_zip_bytes(members)
    deflate_zip = _deflate_zip(members)
    string_bounds_glb = replace_glb_json(
        triangle_glb,
        lambda document: document["accessors"][0]["min"].__setitem__(0, "0"),
    )
    boolean_scene_glb = replace_glb_json(
        triangle_glb, lambda document: document.__setitem__("scene", False)
    )
    simple_triangle = glb(
        "triangle",
        [(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        [0, 1, 2],
        [(0, 0, 1)] * 3,
    )
    float_extreme_line = glb(
        "line",
        [
            (
                _f32_from_bits(0xFF7FFFFF),
                _f32_from_bits(0x80000001),
                _f32_from_bits(0x007FFFFF),
            ),
            (
                _f32_from_bits(0x80800000),
                0.0,
                _f32_from_bits(0x00000001),
            ),
            (
                _f32_from_bits(0x00800000),
                _f32_from_bits(0x007FFFFF),
                _f32_from_bits(0x7F7FFFFF),
            ),
        ],
        [0, 1, 1, 2],
    )

    glb_payloads: list[tuple[str, bytes, str, bool]] = [
        ("valid_triangle", triangle_glb, "triangle", True),
        ("valid_line", line_glb, "line", True),
        ("valid_float32_finite_extremes", float_extreme_line, "line", True),
        ("string_accessor_bounds", string_bounds_glb, "triangle", False),
        ("boolean_scene_index", boolean_scene_glb, "triangle", False),
    ]
    for name, base, path, key, value in (
        ("root_extensions_used", triangle_glb, (), "extensionsUsed", []),
        ("asset_extras", triangle_glb, ("asset",), "extras", {}),
        ("node_name", triangle_glb, ("nodes", 0), "name", "node"),
        ("scene_name", triangle_glb, ("scenes", 0), "name", "scene"),
        ("mesh_name", triangle_glb, ("meshes", 0), "name", "mesh"),
        (
            "primitive_material",
            triangle_glb,
            ("meshes", 0, "primitives", 0),
            "material",
            0,
        ),
        ("buffer_uri", triangle_glb, ("buffers", 0), "uri", "buffer.bin"),
        ("buffer_view_byte_stride", triangle_glb, ("bufferViews", 0), "byteStride", 12),
        ("position_accessor_byte_offset", triangle_glb, ("accessors", 0), "byteOffset", 0),
        ("normal_accessor_normalized", triangle_glb, ("accessors", 1), "normalized", False),
        ("index_accessor_sparse", triangle_glb, ("accessors", 2), "sparse", {}),
    ):
        glb_payloads.append(
            (
                name,
                replace_glb_json(
                    base,
                    lambda document, path=path, key=key, value=value: _add_path(
                        document, path, key, value
                    ),
                ),
                "triangle",
                False,
            )
        )
    for name, base, path, value, kind in (
        ("empty_position_accessor", line_glb, ("accessors", 0, "count"), 0, "line"),
        ("empty_index_accessor", line_glb, ("accessors", 1, "count"), 0, "line"),
        (
            "wrong_triangle_mode",
            triangle_glb,
            ("meshes", 0, "primitives", 0, "mode"),
            1,
            "triangle",
        ),
        (
            "wrong_position_component_type",
            triangle_glb,
            ("accessors", 0, "componentType"),
            5125,
            "triangle",
        ),
        ("wrong_normal_count", triangle_glb, ("accessors", 1, "count"), 1, "triangle"),
        (
            "wrong_index_component_type",
            triangle_glb,
            ("accessors", 2, "componentType"),
            5125,
            "triangle",
        ),
        ("buffer_view_gap", triangle_glb, ("bufferViews", 1, "byteOffset"), 4, "triangle"),
        (
            "buffer_view_wrong_target",
            triangle_glb,
            ("bufferViews", 0, "target"),
            34963,
            "triangle",
        ),
        (
            "buffer_view_wrong_length",
            triangle_glb,
            ("bufferViews", 0, "byteLength"),
            4,
            "triangle",
        ),
    ):
        glb_payloads.append(
            (
                name,
                replace_glb_json(
                    base,
                    lambda document, path=path, value=value: _set_path(
                        document, path, value
                    ),
                ),
                kind,
                False,
            )
        )
    glb_payloads.extend(
        (
            ("bad_glb_magic", _replace_u32(triangle_glb, 0, 0), "triangle", False),
            ("bad_glb_version", _replace_u32(triangle_glb, 4, 1), "triangle", False),
            (
                "bad_glb_total_length",
                _replace_u32(triangle_glb, 8, len(triangle_glb) + 4),
                "triangle",
                False,
            ),
            ("bad_json_chunk_type", _replace_u32(triangle_glb, 16, 0), "triangle", False),
            (
                "nonminimal_json_padding",
                _nonminimal_glb_json_padding(triangle_glb),
                "triangle",
                False,
            ),
            (
                "bad_bin_chunk_type",
                _replace_u32(
                    triangle_glb,
                    24 + struct.unpack_from("<I", triangle_glb, 12)[0],
                    0,
                ),
                "triangle",
                False,
            ),
            (
                "extra_accessor",
                replace_glb_json(
                    triangle_glb,
                    lambda document: _append_path(
                        document,
                        ("accessors",),
                        deepcopy(document["accessors"][0]),
                    ),
                ),
                "triangle",
                False,
            ),
            (
                "buffer_unpadded_length",
                replace_glb_json(
                    triangle_glb,
                    lambda document: _set_path(
                        document,
                        ("buffers", 0, "byteLength"),
                        document["buffers"][0]["byteLength"] + 4,
                    ),
                ),
                "triangle",
                False,
            ),
            ("bin_extra_zero_word", _append_glb_bin_word(triangle_glb), "triangle", False),
            (
                "bin_nonzero_padding",
                simple_triangle[:-1] + b"\x01",
                "triangle",
                False,
            ),
            (
                "position_negative_zero",
                _replace_glb_bin_u32(simple_triangle, 0, 0x80000000),
                "triangle",
                False,
            ),
            (
                "position_positive_infinity",
                _replace_glb_bin_u32(simple_triangle, 0, 0x7F800000),
                "triangle",
                False,
            ),
            (
                "position_negative_infinity",
                _replace_glb_bin_u32(simple_triangle, 0, 0xFF800000),
                "triangle",
                False,
            ),
            (
                "position_quiet_nan",
                _replace_glb_bin_u32(simple_triangle, 0, 0x7FC00000),
                "triangle",
                False,
            ),
            (
                "normal_negative_zero",
                _replace_glb_bin_u32(simple_triangle, 36, 0x80000000),
                "triangle",
                False,
            ),
            (
                "normal_nonfinite",
                _replace_glb_bin_u32(simple_triangle, 44, 0x7FC00000),
                "triangle",
                False,
            ),
            (
                "normal_norm_below_lower_limit",
                _replace_glb_bin_u32(simple_triangle, 44, 0x3F7FFFEF),
                "triangle",
                False,
            ),
            (
                "normal_norm_above_upper_limit",
                _replace_glb_bin_u32(simple_triangle, 44, 0x3F800009),
                "triangle",
                False,
            ),
        )
    )
    valid_normal_boundaries = _replace_glb_bin_u32(simple_triangle, 44, 0x3F7FFFF0)
    valid_normal_boundaries = _replace_glb_bin_u32(valid_normal_boundaries, 56, 0x3F800008)
    glb_payloads.append(
        ("valid_normal_norm_inner_neighbors", valid_normal_boundaries, "triangle", True)
    )

    tiny_zip = canonical_zip_bytes({"other.json": b"x", "scene.json": b"{}"})
    tiny_entries, tiny_central, tiny_eocd = _zip_layout(tiny_zip)
    first_central, first_local, _first_name_length = tiny_entries[0]
    first_payload = first_local + LOCAL.size + struct.unpack_from("<H", tiny_zip, first_local + 26)[0]
    crc_zip = bytearray(tiny_zip)
    crc_zip[first_payload] ^= 1
    exact_ratio_zip = _deflate_zip({"scene.json": b"a" * 1200})
    over_ratio_zip = _deflate_zip({"scene.json": b"a" * 1201})
    zip_payloads: list[tuple[str, bytes, bool, bool | None]] = [
        ("canonical_stored", canonical_zip, True, False),
        ("allowlisted_deflate", deflate_zip, True, True),
        ("exact_member_compression_ratio", exact_ratio_zip, True, True),
        ("over_member_compression_ratio", over_ratio_zip, False, None),
        ("crc_mismatch", bytes(crc_zip), False, None),
        ("trailing_data", tiny_zip + b"x", False, None),
        ("leading_prefix", _zip_with_prefix(tiny_zip), False, None),
        ("local_record_gap", _zip_with_local_gap(tiny_zip), False, None),
        ("case_collision", _replace_zip_name(tiny_zip, 0, b"SCENE.JSON"), False, None),
        ("path_traversal", _replace_zip_name(tiny_zip, 0, b"a/../b.txt"), False, None),
        ("backslash_name", _replace_zip_name(tiny_zip, 0, b"other\\json"), False, None),
        ("nul_name", _replace_zip_name(tiny_zip, 0, b"other.\0son"), False, None),
        ("bad_eocd_signature", _replace_u32(tiny_zip, tiny_eocd, 0), False, None),
        ("eocd_comment", _replace_u16(tiny_zip, tiny_eocd + 20, 1), False, None),
        ("multi_disk", _replace_u16(tiny_zip, tiny_eocd + 4, 1), False, None),
        (
            "member_count_over_limit",
            _replace_u16(
                _replace_u16(tiny_zip, tiny_eocd + 8, 50_001),
                tiny_eocd + 10,
                50_001,
            ),
            False,
            None,
        ),
        (
            "central_offset_mismatch",
            _replace_u32(tiny_zip, tiny_eocd + 16, tiny_central + 1),
            False,
            None,
        ),
        ("bad_central_signature", _replace_u32(tiny_zip, first_central, 0), False, None),
        ("central_made_by", _replace_u16(tiny_zip, first_central + 4, 20), False, None),
        ("central_needed", _replace_u16(tiny_zip, first_central + 6, 45), False, None),
        ("central_flags", _replace_u16(tiny_zip, first_central + 8, 0x0808), False, None),
        ("central_method", _replace_u16(tiny_zip, first_central + 10, 99), False, None),
        ("central_time", _replace_u16(tiny_zip, first_central + 12, 1), False, None),
        ("central_date", _replace_u16(tiny_zip, first_central + 14, 0), False, None),
        ("central_extra", _replace_u16(tiny_zip, first_central + 30, 1), False, None),
        ("central_comment", _replace_u16(tiny_zip, first_central + 32, 1), False, None),
        ("central_disk_start", _replace_u16(tiny_zip, first_central + 34, 1), False, None),
        ("central_internal_attr", _replace_u16(tiny_zip, first_central + 36, 1), False, None),
        ("central_external_attr", _replace_u32(tiny_zip, first_central + 38, 0), False, None),
        ("central_crc", _replace_u32(tiny_zip, first_central + 16, 0), False, None),
        (
            "central_compressed_size",
            _replace_u32(tiny_zip, first_central + 20, 2),
            False,
            None,
        ),
        (
            "central_uncompressed_size",
            _replace_u32(tiny_zip, first_central + 24, 2),
            False,
            None,
        ),
        ("central_local_offset", _replace_u32(tiny_zip, first_central + 42, 1), False, None),
        ("local_signature", _replace_u32(tiny_zip, first_local, 0), False, None),
        ("local_needed", _replace_u16(tiny_zip, first_local + 4, 45), False, None),
        ("local_flags", _replace_u16(tiny_zip, first_local + 6, 0), False, None),
        ("local_method", _replace_u16(tiny_zip, first_local + 8, 8), False, None),
        ("local_time", _replace_u16(tiny_zip, first_local + 10, 1), False, None),
        ("local_date", _replace_u16(tiny_zip, first_local + 12, 0), False, None),
        ("local_crc", _replace_u32(tiny_zip, first_local + 14, 0), False, None),
        ("local_compressed_size", _replace_u32(tiny_zip, first_local + 18, 2), False, None),
        ("local_uncompressed_size", _replace_u32(tiny_zip, first_local + 22, 2), False, None),
        ("local_extra", _replace_u16(tiny_zip, first_local + 28, 1), False, None),
    ]
    return (
        canonical_zip,
        deflate_zip,
        [_glb_case(*case) for case in glb_payloads],
        [_zip_case(*case) for case in zip_payloads],
    )
