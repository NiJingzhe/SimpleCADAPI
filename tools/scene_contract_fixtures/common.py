"""Shared fixture construction and package-record helpers."""

from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from typing import Any, Callable

from simplecadapi.scene import (
    canonical_json_bytes,
    validate_scene_package,
)


JsonObject = dict[str, Any]
ScenePackage = tuple[JsonObject, JsonObject, dict[str, bytes]]
Validator = Callable[[Any], Any]

IDENTITY = {
    "origin": [0, 0, 0],
    "x_axis": [1, 0, 0],
    "y_axis": [0, 1, 0],
    "z_axis": [0, 0, 1],
}


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def content_hash(value: bytes) -> str:
    return "sha256:" + sha256_hex(value)


def first_issue(report: Any) -> dict[str, str] | None:
    issue = report.first_error
    return None if issue is None else {"code": issue.code, "path": issue.path}


def report_case(name: str, payload: bytes, report: Any) -> dict[str, object]:
    return {
        "expected": first_issue(report),
        "name": name,
        "payload_base64": b64(payload),
        "valid": report.valid,
    }


def transform(origin: list[float] | None = None) -> JsonObject:
    value = deepcopy(IDENTITY)
    if origin is not None:
        value["origin"] = origin
    return value


def validation_case(
    name: str, value: Any, validator: Validator
) -> dict[str, object]:
    payload = value if isinstance(value, bytes) else canonical_json_bytes(value)
    return report_case(name, payload, validator(payload))


def replace_entity_sidecar(
    scene: JsonObject,
    entity: JsonObject,
    blobs: dict[str, bytes],
) -> ScenePackage:
    entity_bytes = canonical_json_bytes(entity)
    entity_hash = content_hash(entity_bytes)
    entity_uri = f"entities/sha256-{entity_hash.removeprefix('sha256:')}.json"
    entity_record = scene["entity_assets"][0]
    old_uri = entity_record["uri"]
    entity_record.update(
        {
            "byte_length": len(entity_bytes),
            "content_hash": entity_hash,
            "entity_asset_id": entity_hash,
            "uri": entity_uri,
        }
    )
    for definition in scene["definitions"]:
        if definition["kind"] in {"part", "shape"}:
            definition["entity_asset_id"] = entity_hash
    updated_blobs = {uri: payload for uri, payload in blobs.items() if uri != old_uri}
    updated_blobs[entity_uri] = entity_bytes
    return scene, entity, updated_blobs


def set_product_material_appearance(
    scene: JsonObject, material_id: str = "fixture_material"
) -> None:
    appearance = scene["appearances"][0]
    appearance["name"] = "Fixture material"
    appearance["source"] = {
        "kind": "product_material",
        "material_id": material_id,
        "root_id": "root",
    }
    draft = dict(appearance)
    draft.pop("appearance_id")
    appearance_id = "appearance/evaluated/" + sha256_hex(canonical_json_bytes(draft))
    appearance["appearance_id"] = appearance_id
    for definition in scene["definitions"]:
        if definition["kind"] in {"part", "shape"}:
            definition["appearance_id"] = appearance_id


def inline_package_case(
    name: str,
    scene: JsonObject,
    blobs: dict[str, bytes],
    blob_pool: dict[str, str],
) -> dict[str, object]:
    scene_bytes = canonical_json_bytes(scene)
    report = validate_scene_package(scene_bytes, blobs)
    for uri, payload in blobs.items():
        encoded = b64(payload)
        previous = blob_pool.setdefault(uri, encoded)
        if previous != encoded:
            raise AssertionError(f"one fixture URI resolved to different bytes: {uri}")
    return {
        "blob_uris": sorted(blobs),
        "expected": first_issue(report),
        "manifest_base64": b64(scene_bytes),
        "name": name,
        "valid": report.valid,
    }


def scene_shape_case(
    name: str,
    scene: JsonObject,
    blobs: dict[str, bytes],
    expected: dict[str, object],
    blob_pool: dict[str, str],
) -> dict[str, object]:
    package = inline_package_case(name, scene, blobs, blob_pool)
    if not package["valid"]:
        raise AssertionError(f"invalid scene shape fixture {name}: {package['expected']}")
    return {**package, "expected_shape": expected}
