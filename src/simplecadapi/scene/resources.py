"""Scene 1.0 resource limits shared by validators and archive preflight."""

from __future__ import annotations

from dataclasses import dataclass


MIB = 1024 * 1024


@dataclass(frozen=True)
class SceneResourceLimits:
    zip_members: int = 50_000
    input_archive_bytes: int = 256 * MIB
    canonical_archive_bytes: int = 256 * MIB
    total_uncompressed_bytes: int = 1024 * MIB
    one_member_bytes: int = 256 * MIB
    scene_json_bytes: int = 32 * MIB
    entity_json_bytes: int = 64 * MIB
    model_json_bytes: int = 64 * MIB
    presentation_json_bytes: int = 8 * MIB
    compression_ratio: int = 100
    json_depth: int = 64
    json_string_bytes: int = 1 * MIB
    uri_bytes: int = 1024
    structural_id_bytes: int = 4096
    definitions: int = 25_000
    nodes: int = 100_000
    assets_per_kind: int = 25_000
    appearances: int = 25_000
    connectors: int = 100_000
    cameras: int = 1_000
    hierarchy_depth: int = 256
    forwarded_connector_depth: int = 64
    entities_per_sidecar: int = 500_000
    entities_total: int = 2_000_000
    triangle_vertices_per_asset: int = 2_000_000
    triangle_vertices_total: int = 10_000_000
    triangles_per_asset: int = 2_000_000
    triangles_total: int = 10_000_000
    line_vertices_per_asset: int = 2_000_000
    line_vertices_total: int = 10_000_000
    line_segments_per_asset: int = 2_000_000
    line_segments_total: int = 10_000_000
    static_decoded_buffer_bytes: int = 512 * MIB


BASE_LIMITS = SceneResourceLimits()


def preflight_input_archive_size(
    size: int, *, limits: SceneResourceLimits = BASE_LIMITS
) -> int:
    """Validate a transported archive length before reading that many bytes."""

    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError("invalid input archive size")
    if size > limits.input_archive_bytes:
        raise ValueError("input archive exceeds resource limit")
    return size


def preflight_resource_count(
    count: int,
    limit_name: str,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> int:
    """Validate one non-negative resource count against the named profile limit."""

    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("invalid resource count")
    if limit_name not in SceneResourceLimits.__dataclass_fields__:
        raise ValueError(f"unknown resource limit: {limit_name}")
    if count > getattr(limits, limit_name):
        raise ValueError(f"{limit_name} exceeds resource limit")
    return count


def preflight_aggregate_compression_ratio(
    uncompressed_size: int,
    archive_size: int,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> None:
    """Validate the aggregate compression-ratio predicate without inflating data."""

    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (uncompressed_size, archive_size)
    ) or archive_size == 0:
        raise ValueError("invalid compression ratio sizes")
    if uncompressed_size > limits.compression_ratio * archive_size:
        raise ValueError("aggregate compression ratio exceeds limit")


def preflight_member_compression_ratio(
    uncompressed_size: int,
    compressed_size: int,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> None:
    """Validate one member compression-ratio predicate before inflation."""

    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in (uncompressed_size, compressed_size)
    ):
        raise ValueError("invalid compression ratio sizes")
    if uncompressed_size > limits.compression_ratio * max(1, compressed_size):
        raise ValueError("member compression ratio exceeds limit")


def canonical_archive_size(member_sizes: dict[str, int]) -> int:
    """Compute the exact stored ZIP envelope size from names and payload sizes."""

    total = 22
    for name, size in member_sizes.items():
        total += 76 + 2 * len(name.encode("ascii")) + size
    return total
