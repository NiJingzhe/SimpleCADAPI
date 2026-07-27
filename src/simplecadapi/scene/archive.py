"""Canonical Scene ZIP encoding and hostile-input archive preflight."""

from __future__ import annotations

import binascii
import json
import os
import re
import stat
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .resources import (
    BASE_LIMITS,
    SceneResourceLimits,
    canonical_archive_size,
    preflight_aggregate_compression_ratio,
    preflight_input_archive_size,
    preflight_member_compression_ratio,
)


_MEMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}$")
_LOCAL = struct.Struct("<IHHHHHIIIHH")
_CENTRAL = struct.Struct("<IHHHHHHIIIHHHHHII")
_EOCD = struct.Struct("<IHHHHIIH")


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


@dataclass(frozen=True)
class ArchiveInfo:
    members: Mapping[str, bytes]
    input_size: int | None
    canonical_size: int
    used_deflate: bool


@dataclass(frozen=True)
class _CentralEntry:
    name: str
    method: int
    crc32: int
    compressed_size: int
    uncompressed_size: int
    local_offset: int


def _validate_member_name(name: str, seen_casefold: set[str]) -> bytes:
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("archive member names must be ASCII") from exc
    if not _MEMBER_RE.fullmatch(name):
        raise ValueError(f"invalid archive member name: {_quote(name)}")
    segments = name.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"invalid archive member path segment: {_quote(name)}")
    folded = name.lower()
    if folded in seen_casefold:
        raise ValueError(f"duplicate or case-colliding archive member: {_quote(name)}")
    seen_casefold.add(folded)
    return encoded


def preflight_archive_member_sizes(
    sizes: Mapping[str, int], *, limits: SceneResourceLimits = BASE_LIMITS
) -> int:
    """Validate declared archive sizes before allocating or reading payloads."""

    if not sizes or "scene.json" not in sizes:
        raise ValueError("scene package must contain scene.json")
    if len(sizes) > limits.zip_members:
        raise ValueError("archive member count exceeds resource limit")
    total = 0
    seen_casefold: set[str] = set()
    for name, size in sizes.items():
        _validate_member_name(name, seen_casefold)
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"invalid member size for {_quote(name)}")
        if size > limits.one_member_bytes:
            raise ValueError(f"archive member exceeds resource limit: {_quote(name)}")
        if name == "scene.json" and size > limits.scene_json_bytes:
            raise ValueError("scene.json exceeds resource limit")
        if name.startswith("entities/") and size > limits.entity_json_bytes:
            raise ValueError(f"entity sidecar exceeds resource limit: {_quote(name)}")
        if name == "model/model.json" and size > limits.model_json_bytes:
            raise ValueError("embedded model.json exceeds resource limit")
        if name == "presentation/presentation.json" and size > limits.presentation_json_bytes:
            raise ValueError("presentation JSON exceeds resource limit")
        total += size
        if total > limits.total_uncompressed_bytes:
            raise ValueError("total uncompressed bytes exceed resource limit")
    canonical_size = canonical_archive_size(dict(sizes))
    if canonical_size > limits.canonical_archive_bytes:
        raise ValueError("canonical stored archive exceeds resource limit")
    if len(sizes) > 0xFFFF or canonical_size > 0xFFFFFFFF:
        raise ValueError("archive would require ZIP64")
    return canonical_size


def canonical_zip_bytes(
    members: Mapping[str, bytes | bytearray | memoryview],
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> bytes:
    """Encode exact canonical stored ZIP bytes for a validated member mapping."""

    payloads = {name: bytes(value) for name, value in members.items()}
    canonical_size = preflight_archive_member_sizes(
        {name: len(value) for name, value in payloads.items()}, limits=limits
    )
    local_parts: list[bytes] = []
    central_parts: list[bytes] = []
    local_offset = 0
    for name in sorted(payloads, key=lambda value: value.encode("ascii")):
        name_bytes = name.encode("ascii")
        payload = payloads[name]
        crc = binascii.crc32(payload) & 0xFFFFFFFF
        local_header = _LOCAL.pack(
            0x04034B50,
            20,
            0x0800,
            0,
            0,
            0x0021,
            crc,
            len(payload),
            len(payload),
            len(name_bytes),
            0,
        )
        local_parts.extend((local_header, name_bytes, payload))
        central_parts.extend(
            (
                _CENTRAL.pack(
                    0x02014B50,
                    0x0314,
                    20,
                    0x0800,
                    0,
                    0,
                    0x0021,
                    crc,
                    len(payload),
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
        local_offset += len(local_header) + len(name_bytes) + len(payload)
    central = b"".join(central_parts)
    eocd = _EOCD.pack(
        0x06054B50,
        0,
        0,
        len(payloads),
        len(payloads),
        len(central),
        local_offset,
        0,
    )
    result = b"".join(local_parts) + central + eocd
    if len(result) != canonical_size:
        raise AssertionError("canonical ZIP size formula disagrees with encoder")
    return result


def _decode_name(raw: bytes, seen_casefold: set[str]) -> str:
    try:
        name = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("archive member names must be ASCII") from exc
    _validate_member_name(name, seen_casefold)
    return name


def preflight_zip_bytes(
    data: bytes | bytearray | memoryview,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> ArchiveInfo:
    """Validate and decode an allowlisted stored/deflate Scene ZIP archive."""

    input_size = data.nbytes if isinstance(data, memoryview) else len(data)
    preflight_input_archive_size(input_size, limits=limits)
    raw = data if isinstance(data, bytes) else bytes(data)
    if len(raw) < _EOCD.size:
        raise ValueError("truncated ZIP archive")
    eocd_offset = len(raw) - _EOCD.size
    eocd = _EOCD.unpack_from(raw, eocd_offset)
    if eocd[0] != 0x06054B50 or eocd[7] != 0:
        raise ValueError("ZIP EOCD must be final and have no comment")
    _, disk, central_disk, disk_count, total_count, central_size, central_offset, _ = eocd
    if disk or central_disk or disk_count != total_count:
        raise ValueError("multi-disk ZIP archives are forbidden")
    if total_count > limits.zip_members:
        raise ValueError("archive member count exceeds resource limit")
    if central_offset + central_size != eocd_offset:
        raise ValueError("ZIP central directory offset/size mismatch")

    entries: list[_CentralEntry] = []
    cursor = central_offset
    seen_casefold: set[str] = set()
    for _index in range(total_count):
        if cursor + _CENTRAL.size > eocd_offset:
            raise ValueError("truncated ZIP central directory")
        fields = _CENTRAL.unpack_from(raw, cursor)
        if fields[0] != 0x02014B50:
            raise ValueError("invalid ZIP central header signature")
        (
            _signature,
            made_by,
            needed,
            flags,
            method,
            dos_time,
            dos_date,
            crc,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
            comment_length,
            disk_start,
            internal_attributes,
            external_attributes,
            local_offset,
        ) = fields
        if made_by != 0x0314 or needed != 20:
            raise ValueError("ZIP creator/version profile mismatch")
        if flags != 0x0800 or method not in {0, 8}:
            raise ValueError("unsupported ZIP flags or compression method")
        if dos_time != 0 or dos_date != 0x0021:
            raise ValueError("ZIP timestamp profile mismatch")
        if extra_length or comment_length or disk_start or internal_attributes:
            raise ValueError("ZIP extra/comment/disk/attributes are forbidden")
        if external_attributes != 0x81A40000:
            raise ValueError("ZIP member must be Unix regular mode 0100644")
        name_start = cursor + _CENTRAL.size
        name_end = name_start + name_length
        record_end = name_end + extra_length + comment_length
        if record_end > eocd_offset:
            raise ValueError("truncated ZIP central member record")
        name = _decode_name(raw[name_start:name_end], seen_casefold)
        entries.append(
            _CentralEntry(
                name=name,
                method=method,
                crc32=crc,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
                local_offset=local_offset,
            )
        )
        cursor = record_end
    if cursor != eocd_offset:
        raise ValueError("unexpected bytes in ZIP central directory")

    canonical_size = preflight_archive_member_sizes(
        {entry.name: entry.uncompressed_size for entry in entries}, limits=limits
    )
    occupied: list[tuple[int, int]] = []
    payload_ranges: list[tuple[_CentralEntry, int, int]] = []
    total_uncompressed = 0
    for entry in entries:
        offset = entry.local_offset
        if offset + _LOCAL.size > central_offset:
            raise ValueError("truncated ZIP local header")
        fields = _LOCAL.unpack_from(raw, offset)
        if fields[0] != 0x04034B50:
            raise ValueError("invalid ZIP local header signature")
        (
            _signature,
            needed,
            flags,
            method,
            dos_time,
            dos_date,
            crc,
            compressed_size,
            uncompressed_size,
            name_length,
            extra_length,
        ) = fields
        if (
            needed != 20
            or flags != 0x0800
            or method != entry.method
            or dos_time != 0
            or dos_date != 0x0021
            or crc != entry.crc32
            or compressed_size != entry.compressed_size
            or uncompressed_size != entry.uncompressed_size
            or extra_length != 0
        ):
            raise ValueError("ZIP central/local header mismatch")
        name_start = offset + _LOCAL.size
        name_end = name_start + name_length
        payload_end = name_end + compressed_size
        if payload_end > central_offset:
            raise ValueError("ZIP member payload crosses central directory")
        try:
            local_name = raw[name_start:name_end].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("archive member names must be ASCII") from exc
        if local_name != entry.name:
            raise ValueError("ZIP central/local member name mismatch")
        occupied.append((offset, payload_end))
        payload_ranges.append((entry, name_end, payload_end))
        total_uncompressed += uncompressed_size
    occupied.sort()
    if occupied:
        if occupied[0][0] != 0:
            raise ValueError("ZIP archive has a leading prefix")
        for previous, current in zip(occupied, occupied[1:]):
            if previous[1] != current[0]:
                raise ValueError("ZIP local records overlap or contain gaps")
        if occupied[-1][1] != central_offset:
            raise ValueError("ZIP bytes exist between local records and central directory")
    preflight_aggregate_compression_ratio(
        total_uncompressed, len(raw), limits=limits
    )

    members: dict[str, bytes] = {}
    for entry, payload_start, payload_end in payload_ranges:
        compressed = raw[payload_start:payload_end]
        try:
            preflight_member_compression_ratio(
                entry.uncompressed_size, entry.compressed_size, limits=limits
            )
        except ValueError as exc:
            raise ValueError(f"member compression ratio exceeds limit: {_quote(entry.name)}")
        if entry.method == 0:
            payload = compressed
        else:
            inflater = zlib.decompressobj(-zlib.MAX_WBITS)
            payload = inflater.decompress(compressed, entry.uncompressed_size + 1)
            if inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError(f"invalid deflate stream: {_quote(entry.name)}")
            payload += inflater.flush(entry.uncompressed_size + 1 - len(payload))
            if not inflater.eof:
                raise ValueError(f"invalid deflate stream: {_quote(entry.name)}")
        if len(payload) != entry.uncompressed_size:
            raise ValueError(f"ZIP member decoded size mismatch: {_quote(entry.name)}")
        if binascii.crc32(payload) & 0xFFFFFFFF != entry.crc32:
            raise ValueError(f"ZIP member CRC mismatch: {_quote(entry.name)}")
        members[entry.name] = payload
    return ArchiveInfo(
        members=MappingProxyType(members),
        input_size=len(raw),
        canonical_size=canonical_size,
        used_deflate=any(entry.method == 8 for entry in entries),
    )


def preflight_unpacked_scene(
    path: str | os.PathLike[str],
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> ArchiveInfo:
    """Preflight and immutably read an unpacked scene without following links."""

    root = Path(path)
    root_stat = root.stat(follow_symlinks=False)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ValueError("unpacked scene root must be a directory")
    records: dict[str, tuple[Path, os.stat_result]] = {}
    for current_root, dir_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        for directory in dir_names:
            directory_path = current / directory
            mode = directory_path.stat(follow_symlinks=False).st_mode
            if not stat.S_ISDIR(mode):
                raise ValueError(f"unpacked scene contains a non-directory link: {directory_path}")
        for filename in file_names:
            file_path = current / filename
            relative = file_path.relative_to(root).as_posix()
            file_stat = file_path.stat(follow_symlinks=False)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(
                    f"unpacked scene member is not a regular file: {_quote(relative)}"
                )
            records[relative] = (file_path, file_stat)
    canonical_size = preflight_archive_member_sizes(
        {name: record.st_size for name, (_path, record) in records.items()}, limits=limits
    )
    members: dict[str, bytes] = {}
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    for name, (file_path, expected) in records.items():
        descriptor = os.open(file_path, os.O_RDONLY | nofollow)
        try:
            actual = os.fstat(descriptor)
            if (
                actual.st_dev != expected.st_dev
                or actual.st_ino != expected.st_ino
                or actual.st_size != expected.st_size
                or not stat.S_ISREG(actual.st_mode)
            ):
                raise ValueError(
                    f"unpacked scene member changed during preflight: {_quote(name)}"
                )
            chunks: list[bytes] = []
            remaining = expected.st_size
            while remaining:
                chunk = os.read(descriptor, min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError(
                        f"unpacked scene member was truncated: {_quote(name)}"
                    )
                chunks.append(chunk)
                remaining -= len(chunk)
            payload = b"".join(chunks)
            if os.read(descriptor, 1):
                raise ValueError(f"unpacked scene member grew during read: {_quote(name)}")
            members[name] = payload
        finally:
            os.close(descriptor)
    return ArchiveInfo(
        members=MappingProxyType(members),
        input_size=None,
        canonical_size=canonical_size,
        used_deflate=False,
    )
