"""Self-contained PartDefinition archive encoding and loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .brep import read_brep_solid
from .canonical import ArtifactValidationError
from .part_definition import PartDefinition
from .topology_snapshot import restore_topology_snapshot
from .validation import parse_artifact_json, validate_artifact_blobs
from ..scene.archive import canonical_zip_bytes, preflight_zip_bytes

_PART_DEFINITION_MANIFEST = "part-definition.json"
_BLOB_PREFIX = "blobs/"


def encode_part_definition(definition: PartDefinition) -> bytes:
    """Encode one validated definition and every referenced blob canonically."""

    if not isinstance(definition, PartDefinition):
        raise TypeError("definition must be a PartDefinition")
    validate_artifact_blobs(definition.to_dict(), definition.blobs)
    members: dict[str, bytes] = {
        _PART_DEFINITION_MANIFEST: definition.canonical_bytes,
    }
    for path, payload in definition.blobs.items():
        members[_BLOB_PREFIX + path] = bytes(payload)
    return canonical_zip_bytes(
        members,
        manifest_name=_PART_DEFINITION_MANIFEST,
    )


def load_part_definition(
    data: bytes | bytearray | memoryview | str | Path,
) -> PartDefinition:
    """Load and fully validate a self-contained PartDefinition archive."""

    raw = Path(data).read_bytes() if isinstance(data, (str, Path)) else bytes(data)
    archive = preflight_zip_bytes(
        raw,
        manifest_name=_PART_DEFINITION_MANIFEST,
    )
    manifest = parse_artifact_json(
        archive.members[_PART_DEFINITION_MANIFEST],
        kind="part_definition",
    )
    expected_paths = {
        str(manifest["definition"]["model_ref"]["path"]),
        str(manifest["solid_cache"]["body_ref"]["path"]),
        str(manifest["topology_snapshot_ref"]["path"]),
    }
    material_ref = manifest["material_ref"]
    if material_ref is not None:
        expected_paths.add(str(material_ref["path"]))
    expected_members = {
        _PART_DEFINITION_MANIFEST,
        *(_BLOB_PREFIX + path for path in expected_paths),
    }
    if set(archive.members) != expected_members:
        raise ArtifactValidationError(
            "blob_unreferenced",
            "/blobs",
            "archive member set differs from definition references",
        )
    blobs = {
        path: archive.members[_BLOB_PREFIX + path]
        for path in expected_paths
    }
    definition = PartDefinition.from_dict(manifest, blobs=blobs)
    validate_artifact_blobs(definition.to_dict(), definition.blobs)
    body = read_brep_solid(definition.blobs[definition.solid_cache_ref.path])
    restore_topology_snapshot(
        body,
        definition.blobs[definition.topology_snapshot_ref.path],
    )
    return definition


def export_part_definition(
    value: PartDefinition | Any,
    path: str | Path,
) -> Path:
    """Write a PartDefinition or PartBuildResult to a canonical archive."""

    definition = value if isinstance(value, PartDefinition) else getattr(value, "definition", None)
    if not isinstance(definition, PartDefinition):
        raise TypeError("value must be a PartDefinition or PartBuildResult")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encode_part_definition(definition))
    return destination


__all__ = [
    "encode_part_definition",
    "export_part_definition",
    "load_part_definition",
]
