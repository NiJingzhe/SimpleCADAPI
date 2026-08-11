"""Canonical Part and Assembly product package artifacts.

Product packages are definition artifacts. They are distinct from evaluated
Scene ZIPs: a part/assembly package owns product semantics while a scene owns
rendered presentation data.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from jsonschema import Draft202012Validator
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote

from OCP.BRep import BRep_Builder
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepTools import BRepTools
from OCP.TopoDS import TopoDS, TopoDS_Shape

from .core import Solid
from .product import (
    Assembly,
    Component,
    Connector,
    ConnectorAnchor,
    ConnectorRef,
    Constraint,
    GeometryRef,
    Material,
    Part,
    Placement,
    ScalarLimit,
)
from .scene.archive import canonical_zip_bytes, preflight_zip_bytes
from .scene.canonical import canonical_json_bytes, canonical_json_hash, parse_canonical_json
from .kernel.ocp_properties import bounding_box

from .scene.canonical import (
    canonical_json_bytes,
    canonical_json_hash,
    parse_canonical_json,
    parse_strict_json,
)
PRODUCT_SCHEMA_VERSION = "1.0"
_PART_MANIFEST = "part.json"
_ASSEMBLY_MANIFEST = "assembly.json"
_SUPPORTED_KINDS = {"part", "assembly"}

@lru_cache(maxsize=2)
def _schema(kind: str) -> Any:
    if kind not in _SUPPORTED_KINDS:
        raise ValueError("kind must be part or assembly")
    resource = files("simplecadapi").joinpath(
        "contracts",
        f"product-package-{kind}-1.schema.json",
    )
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _validate_schema(manifest: Mapping[str, Any], kind: str) -> None:
    validator = Draft202012Validator(_schema(kind))
    errors = sorted(validator.iter_errors(manifest), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        pointer = "/" + "/".join(str(item) for item in error.absolute_path)
        raise ProductPackageError(
            f"product {kind} manifest schema invalid at {pointer}: {error.message}"
        )


@dataclass(frozen=True, slots=True)
class ProductPackage:
    """Validated in-memory product package ready for export or loading."""

    kind: str
    manifest: Mapping[str, Any]
    blobs: Mapping[str, bytes]

    @property
    def manifest_name(self) -> str:
        return f"{self.kind}.json"

    @property
    def canonical_manifest(self) -> bytes:
        return canonical_json_bytes(self.manifest)

    @property
    def content_hash(self) -> str:
        return str(self.manifest["content_hash"])


class ProductPackageError(ValueError):
    """Raised when a product package violates its artifact contract."""


def _hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _encoded(value: str) -> str:
    return quote(str(value), safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _blob_ref(uri: str, payload: bytes, media_type: str) -> dict[str, Any]:
    return {
        "uri": uri,
        "media_type": media_type,
        "byte_length": len(payload),
        "content_hash": _hash_bytes(payload),
    }


def _put_blob(blobs: dict[str, bytes], uri: str, payload: bytes) -> dict[str, Any]:
    existing = blobs.get(uri)
    if existing is not None and existing != payload:
        raise ProductPackageError(f"conflicting product package blob: {uri}")
    blobs[uri] = bytes(payload)
    media_type = "application/octet-stream"
    if uri.endswith(".json"):
        media_type = "application/json"
    elif uri.endswith(".brep"):
        media_type = "application/vnd.opencascade.brep"
    return _blob_ref(uri, payload, media_type)


def _with_content_hash(manifest: Mapping[str, Any]) -> dict[str, Any]:
    draft = dict(manifest)
    draft.pop("content_hash", None)
    draft.pop("revision", None)
    content_hash = canonical_json_hash(draft)
    result = dict(draft)
    result["content_hash"] = content_hash
    result["revision"] = content_hash
    return result


def _write_brep(solid: Solid) -> bytes:
    stream = io.BytesIO()
    BRepTools.Write_s(solid.wrapped, stream)
    payload = stream.getvalue()
    if not payload:
        raise ProductPackageError("BRep writer produced an empty body")
    return payload


def _read_brep(payload: bytes) -> Solid:
    shape = TopoDS_Shape()
    BRepTools.Read_s(shape, io.BytesIO(payload), BRep_Builder())
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise ProductPackageError("product body BRep is invalid")
    try:
        return Solid(TopoDS.Solid_s(shape))
    except Exception as exc:
        raise ProductPackageError("product body is not exactly one solid") from exc


def _topology_payload_for_body(definition_id: str, body: Solid) -> dict[str, Any]:
    box = bounding_box(body.wrapped)
    return {
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "definition_id": definition_id,
        "body_kind": "single_solid",
        "face_count": len(body.get_faces()),
        "edge_count": len(body.get_edges()),
        "volume": body.get_volume(),
        "surface_area": sum(face.get_area() for face in body.get_faces()),
        "bounds": {
            "min": [float(box.xmin), float(box.ymin), float(box.zmin)],
            "max": [float(box.xmax), float(box.ymax), float(box.zmax)],
        },
    }


def _topology_payload(part: Part) -> dict[str, Any]:
    return _topology_payload_for_body(part.part_id, part.body)


def _material_payload(material: Material) -> dict[str, Any]:
    return {"schema_version": PRODUCT_SCHEMA_VERSION, **material.to_dict()}


def _connector_payload(definition_id: str, connectors: Sequence[Connector]) -> dict[str, Any]:
    return {
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "definition_id": definition_id,
        "connectors": [connector.to_dict() for connector in connectors],
    }


def _part_manifest(
    part: Part,
    blobs: dict[str, bytes],
    *,
    model_json: str | None = None,
    definition_uri: str | None = None,
) -> dict[str, Any]:
    body_payload = _write_brep(part.body)
    body_digest = _hash_bytes(body_payload).removeprefix("sha256:")
    body_uri = f"body/sha256-{body_digest}.brep"
    body_ref = _put_blob(blobs, body_uri, body_payload)

    topology_payload = canonical_json_bytes(_topology_payload(part))
    topology_digest = _hash_bytes(topology_payload).removeprefix("sha256:")
    topology_ref = _put_blob(
        blobs,
        f"topology/sha256-{topology_digest}.json",
        topology_payload,
    )

    connector_payload = canonical_json_bytes(_connector_payload(part.part_id, part.connectors))
    connector_digest = _hash_bytes(connector_payload).removeprefix("sha256:")
    connector_ref = _put_blob(
        blobs,
        f"connectors/sha256-{connector_digest}.json",
        connector_payload,
    )

    material_ref: dict[str, Any] | None = None
    if part.material is not None:
        material_payload = canonical_json_bytes(_material_payload(part.material))
        material_digest = _hash_bytes(material_payload).removeprefix("sha256:")
        material_ref = _put_blob(
            blobs,
            f"material/sha256-{material_digest}.json",
            material_payload,
        )

    model_ref: dict[str, Any] | None = None
    if model_json is not None:
        model_payload = model_json.encode("utf-8")
        model_digest = _hash_bytes(model_payload).removeprefix("sha256:")
        model_ref = _put_blob(
            blobs,
            f"model/sha256-{model_digest}.model.json",
            model_payload,
        )

    manifest: dict[str, Any] = {
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "artifact_kind": "part",
        "definition_kind": "single_solid",
        "part_id": part.part_id,
        "definition_id": part.part_id,
        "revision": "pending",
        "units": "mm",
        "tolerance_profile": "simplecad-default",
        "name": part.name,
        "body_ref": body_ref,
        "topology_ref": topology_ref,
        "connector_ref": connector_ref,
        "material_ref": material_ref,
        "model_ref": model_ref,
        "definition_uri": definition_uri,
        "metadata": {},
    }
    return _with_content_hash(manifest)


def _assembly_part_definitions(
    assembly: Assembly,
    blobs: dict[str, bytes],
    *,
    model_json: str | None,
    definitions: dict[str, dict[str, Any]],
    active: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for component in assembly.components:
        item = component.item
        kind = "assembly" if isinstance(item, Assembly) else "part"
        definition_id = item.assembly_id if isinstance(item, Assembly) else item.part_id
        key = (kind, definition_id)
        uri = f"definitions/{_encoded(definition_id)}.{kind}.json"
        if key in active:
            raise ProductPackageError(f"cyclic product definition reference: {definition_id}")
        if key not in definitions:
            if isinstance(item, Part):
                child_manifest = _part_manifest(item, blobs, definition_uri=uri)
            else:
                active.add(key)
                child_refs = _assembly_part_definitions(
                    item,
                    blobs,
                    model_json=None,
                    definitions=definitions,
                    active=active,
                )
                active.remove(key)
                child_manifest = _assembly_manifest(
                    item,
                    blobs,
                    model_json=None,
                    definitions=definitions,
                    child_refs=child_refs,
                    definition_uri=uri,
                )
            definitions[key] = child_manifest
            child_payload = canonical_json_bytes(child_manifest)
            _put_blob(blobs, uri, child_payload)
        child_manifest = definitions[key]
        child_payload = canonical_json_bytes(child_manifest)
        refs.append(
            {
                "definition_id": definition_id,
                "definition_kind": kind,
                "uri": uri,
                "content_hash": child_manifest["content_hash"],
                "byte_length": len(child_payload),
                "blob_hash": _hash_bytes(child_payload),
            }
        )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for ref in refs:
        unique[(str(ref["definition_kind"]), str(ref["definition_id"]))] = ref
    return list(unique.values())


def _assembly_manifest(
    assembly: Assembly,
    blobs: dict[str, bytes],
    *,
    model_json: str | None,
    definitions: dict[str, dict[str, Any]],
    child_refs: list[dict[str, Any]] | None = None,
    definition_uri: str | None = None,
) -> dict[str, Any]:
    if child_refs is None:
        child_refs = _assembly_part_definitions(
            assembly,
            blobs,
            model_json=None,
            definitions=definitions,
            active={("assembly", assembly.assembly_id)},
        )
    model_ref: dict[str, Any] | None = None
    if model_json is not None:
        payload = model_json.encode("utf-8")
        digest = _hash_bytes(payload).removeprefix("sha256:")
        model_ref = _put_blob(blobs, f"model/sha256-{digest}.model.json", payload)
    solved_snapshot = {
        "component_placements": [
            {
                "component_id": component.component_id,
                "placement": component.placement.to_dict(),
            }
            for component in assembly.components
        ]
    }
    manifest: dict[str, Any] = {
        "schema_version": PRODUCT_SCHEMA_VERSION,
        "artifact_kind": "assembly",
        "definition_kind": "assembly",
        "assembly_id": assembly.assembly_id,
        "definition_id": assembly.assembly_id,
        "revision": "pending",
        "units": "mm",
        "tolerance_profile": "simplecad-default",
        "name": assembly.name,
        "definitions": sorted(
            child_refs,
            key=lambda item: (str(item["definition_kind"]), str(item["definition_id"])),
        ),
        "instances": [
            {
                "instance_id": component.component_id,
                "definition_ref": next(
                    ref["uri"]
                    for ref in child_refs
                    if ref["definition_id"]
                    == (
                        component.item.assembly_id
                        if isinstance(component.item, Assembly)
                        else component.item.part_id
                    )
                    and ref["definition_kind"]
                    == ("assembly" if isinstance(component.item, Assembly) else "part")
                ),
                "name": component.name,
                "local_placement": component.placement.to_dict(),
            }
            for component in assembly.components
        ],
        "relations": [constraint.to_dict() for constraint in assembly.constraints],
        "grounded_instance_ids": sorted(assembly.grounded_component_ids),
        "connectors": [connector.to_dict() for connector in assembly.connectors],
        "solved_snapshot": solved_snapshot,
        "model_ref": model_ref,
        "definition_uri": definition_uri,
        "metadata": {},
    }
    return _with_content_hash(manifest)


def build_part_package(part: Part, *, model_json: str | None = None) -> ProductPackage:
    if not isinstance(part, Part):
        raise TypeError("part must be a Part")
    blobs: dict[str, bytes] = {}
    manifest = _part_manifest(part, blobs, model_json=model_json)
    validate_product_package(manifest, blobs, kind="part")
    return ProductPackage(kind="part", manifest=manifest, blobs=blobs)


def build_assembly_package(assembly: Assembly, *, model_json: str | None = None) -> ProductPackage:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    blobs: dict[str, bytes] = {}
    definitions: dict[str, dict[str, Any]] = {}
    manifest = _assembly_manifest(
        assembly,
        blobs,
        model_json=model_json,
        definitions=definitions,
    )
    for definition in definitions.values():
        uri = str(definition["definition_uri"])
        if uri not in blobs:
            blobs[uri] = canonical_json_bytes(definition)
    validate_product_package(manifest, blobs, kind="assembly")
    return ProductPackage(kind="assembly", manifest=manifest, blobs=blobs)


def encode_product_package(package: ProductPackage) -> bytes:
    """Return canonical self-contained ZIP bytes for a validated package."""

    if not isinstance(package, ProductPackage):
        raise TypeError("package must be a ProductPackage")
    validate_product_package(package.manifest, package.blobs, kind=package.kind)
    members = {
        package.manifest_name: canonical_json_bytes(package.manifest),
        **package.blobs,
    }
    return canonical_zip_bytes(members, manifest_name=package.manifest_name)


def export_product_package(
    package: ProductPackage,
    path: str | Path,
) -> Path:
    if not isinstance(package, ProductPackage):
        raise TypeError("package must be a ProductPackage")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(encode_product_package(package))
    return destination


def read_product_package(
    data: bytes | bytearray | memoryview | str | Path,
    *,
    kind: str | None = None,
) -> ProductPackage:
    if isinstance(data, (str, Path)):
        raw = Path(data).read_bytes()
    else:
        raw = bytes(data)
    if kind is not None and kind not in _SUPPORTED_KINDS:
        raise ValueError("kind must be part or assembly")
    archive = preflight_zip_bytes(
        raw,
        manifest_name=None if kind is None else f"{kind}.json",
    )
    actual_kind = archive.manifest_name.removesuffix(".json")
    if actual_kind not in _SUPPORTED_KINDS:
        raise ProductPackageError("archive is not a supported product package")
    manifest = parse_canonical_json(archive.members[archive.manifest_name])
    blobs = {
        name: payload
        for name, payload in archive.members.items()
        if name != archive.manifest_name
    }
    validate_product_package(manifest, blobs, kind=actual_kind)
    return ProductPackage(kind=actual_kind, manifest=manifest, blobs=blobs)


def _validate_ref(ref: Any, blobs: Mapping[str, bytes], path: str) -> None:
    if not isinstance(ref, dict):
        raise ProductPackageError(f"{path} must be an object")
    required = {"uri", "media_type", "byte_length", "content_hash"}
    if set(ref) != required:
        raise ProductPackageError(f"{path} has invalid fields")
    uri = ref["uri"]
    if not isinstance(uri, str) or uri not in blobs:
        raise ProductPackageError(f"{path}/uri does not resolve to a package blob")
    payload = blobs[uri]
    if ref["byte_length"] != len(payload):
        raise ProductPackageError(f"{path}/byte_length does not match blob")
    if ref["content_hash"] != _hash_bytes(payload):
        raise ProductPackageError(f"{path}/content_hash does not match blob")

def _require_fields(value: Any, fields: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProductPackageError(f"{path} must be an object")
    if set(value) != fields:
        raise ProductPackageError(f"{path} has invalid fields")
    return value


def _validate_connector_payload(payload: Any, definition_id: str, path: str) -> None:
    value = _require_fields(
        payload,
        {"schema_version", "definition_id", "connectors"},
        path,
    )
    if value["schema_version"] != PRODUCT_SCHEMA_VERSION:
        raise ProductPackageError(f"{path}/schema_version is unsupported")
    if value["definition_id"] != definition_id:
        raise ProductPackageError(f"{path}/definition_id does not match part")
    connectors = value["connectors"]
    if not isinstance(connectors, list):
        raise ProductPackageError(f"{path}/connectors must be an array")
    connector_ids: set[str] = set()
    for index, connector_payload in enumerate(connectors):
        try:
            connector = _connector_from_dict(
                _require_fields(
                    connector_payload,
                    {"connector_id", "name", "anchor"}
                    | ({"geometry_ref"} if "geometry_ref" in connector_payload else set()),
                    f"{path}/connectors/{index}",
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProductPackageError(
                f"{path}/connectors/{index} is invalid: {exc}"
            ) from exc
        if connector.connector_id in connector_ids:
            raise ProductPackageError(f"{path}/connectors contains duplicate connector_id")
        connector_ids.add(connector.connector_id)


def _validate_material_payload(payload: Any, path: str) -> None:
    value = _require_fields(
        payload,
        {"schema_version", "material_id", "name", "density", "density_unit", "color"},
        path,
    )
    if value["schema_version"] != PRODUCT_SCHEMA_VERSION:
        raise ProductPackageError(f"{path}/schema_version is unsupported")
    try:
        _material_from_dict(value)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProductPackageError(f"{path} is invalid: {exc}") from exc


def _validate_topology_payload(payload: Any, body: Solid, definition_id: str, path: str) -> None:
    value = _require_fields(
        payload,
        {
            "schema_version",
            "definition_id",
            "body_kind",
            "face_count",
            "edge_count",
            "volume",
            "surface_area",
            "bounds",
        },
        path,
    )
    bounds = _require_fields(value["bounds"], {"min", "max"}, f"{path}/bounds")
    expected = _topology_payload_for_body(definition_id, body)
    for field_name in ("schema_version", "definition_id", "body_kind", "face_count", "edge_count"):
        if value[field_name] != expected[field_name]:
            raise ProductPackageError(f"{path}/{field_name} does not match body")
    for field_name in ("volume", "surface_area"):
        actual_value = value[field_name]
        if isinstance(actual_value, bool) or not isinstance(actual_value, (int, float)):
            raise ProductPackageError(f"{path}/{field_name} must be a number")
        if not math.isclose(
            float(actual_value),
            float(expected[field_name]),
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise ProductPackageError(f"{path}/{field_name} does not match body")
    for bound_name in ("min", "max"):
        actual_bound = bounds[bound_name]
        expected_bound = expected["bounds"][bound_name]
        if not isinstance(actual_bound, list) or len(actual_bound) != 3:
            raise ProductPackageError(f"{path}/bounds/{bound_name} must be a vec3")
        if any(
            isinstance(component, bool)
            or not isinstance(component, (int, float))
            or not math.isclose(
                float(component),
                float(expected_component),
                rel_tol=1e-10,
                abs_tol=1e-10,
            )
            for component, expected_component in zip(actual_bound, expected_bound)
        ):
            raise ProductPackageError(f"{path}/bounds/{bound_name} does not match body")


def validate_product_package(
    manifest: Mapping[str, Any],
    blobs: Mapping[str, bytes],
    *,
    kind: str,
) -> None:
    if kind not in _SUPPORTED_KINDS:
        raise ValueError("kind must be part or assembly")
    if not isinstance(manifest, Mapping):
        raise ProductPackageError("product manifest must be an object")
    _validate_schema(manifest, kind)
    content_hash = manifest.get("content_hash")
    if _with_content_hash(manifest)["content_hash"] != content_hash:
        raise ProductPackageError("product manifest content_hash is invalid")
    if manifest.get("revision") != content_hash:
        raise ProductPackageError("product manifest revision must equal content_hash")
    if kind == "part":
        _validate_part_manifest(manifest, blobs)
    else:
        _validate_assembly_manifest(manifest, blobs)


def _validate_part_manifest(
    manifest: Mapping[str, Any],
    blobs: Mapping[str, bytes],
    *,
    require_exact_members: bool = True,
) -> set[str]:
    referenced: set[str] = set()
    for field_name in ("body_ref", "topology_ref", "connector_ref"):
        ref = manifest[field_name]
        _validate_ref(ref, blobs, f"/{field_name}")
        referenced.add(str(ref["uri"]))
    for field_name in ("material_ref", "model_ref"):
        ref = manifest.get(field_name)
        if ref is not None:
            _validate_ref(ref, blobs, f"/{field_name}")
            referenced.add(str(ref["uri"]))
    if require_exact_members and set(blobs) != referenced:
        raise ProductPackageError("part package member set differs from manifest refs")
    try:
        body = _read_brep(blobs[manifest["body_ref"]["uri"]])
        topology = parse_canonical_json(blobs[manifest["topology_ref"]["uri"]])
        connectors = parse_canonical_json(blobs[manifest["connector_ref"]["uri"]])
        _validate_topology_payload(
            topology,
            body,
            str(manifest["definition_id"]),
            "/topology_ref",
        )
        _validate_connector_payload(
            connectors,
            str(manifest["definition_id"]),
            "/connector_ref",
        )
        material_ref = manifest.get("material_ref")
        if material_ref is not None:
            _validate_material_payload(
                parse_canonical_json(blobs[material_ref["uri"]]),
                "/material_ref",
            )
        model_ref = manifest.get("model_ref")
        if model_ref is not None:
            parse_strict_json(blobs[model_ref["uri"]])
    except ProductPackageError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ProductPackageError(f"part package content is invalid: {exc}") from exc
    return referenced


def _validate_assembly_manifest(
    manifest: Mapping[str, Any],
    blobs: Mapping[str, bytes],
) -> None:
    referenced: set[str] = set()
    definition_uris: dict[str, tuple[str, str]] = {}
    definition_ids: dict[tuple[str, str], str] = {}
    active: set[str] = set()

    def validate_manifest_hash(child: Mapping[str, Any], path: str) -> None:
        content_hash = child.get("content_hash")
        if _with_content_hash(child)["content_hash"] != content_hash:
            raise ProductPackageError(f"{path}/content_hash is invalid")
        if child.get("revision") != content_hash:
            raise ProductPackageError(f"{path}/revision must equal content_hash")

    def validate_assembly_node(node: Mapping[str, Any], path: str) -> None:
        local_uris: set[str] = set()
        local_ids: set[tuple[str, str]] = set()
        for index, ref in enumerate(node["definitions"]):
            ref_path = f"{path}/definitions/{index}"
            uri = str(ref["uri"])
            child_kind = str(ref["definition_kind"])
            definition_id = str(ref["definition_id"])
            key = (child_kind, definition_id)
            if uri in local_uris or key in local_ids:
                raise ProductPackageError(f"{path}/definitions contains duplicate ref")
            local_uris.add(uri)
            local_ids.add(key)
            if uri not in blobs:
                raise ProductPackageError(f"{ref_path}/uri does not resolve")
            payload = blobs[uri]
            if ref["byte_length"] != len(payload):
                raise ProductPackageError(f"{ref_path}/byte_length mismatch")
            if ref["blob_hash"] != _hash_bytes(payload):
                raise ProductPackageError(f"{ref_path}/blob_hash mismatch")
            child = parse_canonical_json(payload)
            if child.get("artifact_kind") != child_kind:
                raise ProductPackageError(f"{ref_path}/definition_kind mismatch")
            if child.get("definition_id") != definition_id:
                raise ProductPackageError(f"{ref_path}/definition_id mismatch")
            if child.get("content_hash") != ref["content_hash"]:
                raise ProductPackageError(f"{ref_path}/content_hash mismatch")
            if child.get("definition_uri") != uri:
                raise ProductPackageError(f"{ref_path}/uri differs from child definition_uri")
            _validate_schema(child, child_kind)
            validate_manifest_hash(child, ref_path)
            previous_key = definition_uris.get(uri)
            previous_uri = definition_ids.get(key)
            if previous_key is not None and previous_key != key:
                raise ProductPackageError(f"conflicting definition uri: {uri}")
            if previous_uri is not None and previous_uri != uri:
                raise ProductPackageError(
                    f"conflicting definition identity: {child_kind}:{definition_id}"
                )
            definition_uris[uri] = key
            definition_ids[key] = uri
            referenced.add(uri)
            if previous_key is not None:
                continue
            if child_kind == "part":
                referenced.update(
                    _validate_part_manifest(child, blobs, require_exact_members=False)
                )
            else:
                if uri in active:
                    raise ProductPackageError(f"cyclic product definition reference: {uri}")
                active.add(uri)
                validate_assembly_node(child, ref_path)
                active.remove(uri)

        instance_ids: set[str] = set()
        instances_by_id: dict[str, Mapping[str, Any]] = {}
        definition_by_uri: dict[str, Mapping[str, Any]] = {}
        for ref in node["definitions"]:
            definition_by_uri[str(ref["uri"])] = parse_canonical_json(blobs[str(ref["uri"])])
        for index, instance in enumerate(node["instances"]):
            instance_id = str(instance["instance_id"])
            if instance_id in instance_ids:
                raise ProductPackageError(f"{path}/instances/{index}/instance_id is duplicate")
            instance_ids.add(instance_id)
            instances_by_id[instance_id] = instance
            if instance["definition_ref"] not in local_uris:
                raise ProductPackageError(
                    f"{path}/instances/{index}/definition_ref is missing"
                )

        def connector_ids_for_instance(instance_id: str) -> set[str]:
            instance = instances_by_id[instance_id]
            child = definition_by_uri[str(instance["definition_ref"])]
            if child["artifact_kind"] == "part":
                connector_payload = parse_canonical_json(
                    blobs[child["connector_ref"]["uri"]]
                )
                return {
                    str(connector["connector_id"])
                    for connector in connector_payload["connectors"]
                }
            return {
                str(connector["connector_id"])
                for connector in child["connectors"]
            }

        if not set(node["grounded_instance_ids"]).issubset(instance_ids):
            raise ProductPackageError(f"{path}/grounded instance does not exist")
        relation_ids: set[str] = set()
        for index, relation in enumerate(node["relations"]):
            relation_id = str(relation["constraint_id"])
            if relation_id in relation_ids:
                raise ProductPackageError(
                    f"{path}/relations/{index}/constraint_id is duplicate"
                )
            relation_ids.add(relation_id)
            try:
                _constraint_from_dict(relation)
            except (KeyError, TypeError, ValueError) as exc:
                raise ProductPackageError(
                    f"{path}/relations/{index} is invalid: {exc}"
                ) from exc
            for side in ("connector_a", "connector_b"):
                connector_ref = relation[side]
                component_id = str(connector_ref["component_id"])
                connector_id = str(connector_ref["connector_id"])
                if component_id not in instance_ids:
                    raise ProductPackageError(
                        f"{path}/relations/{index}/{side} references missing instance"
                    )
                if connector_id not in connector_ids_for_instance(component_id):
                    raise ProductPackageError(
                        f"{path}/relations/{index}/{side} references missing connector"
                    )

        assembly_connector_ids: set[str] = set()
        for index, connector_payload in enumerate(node["connectors"]):
            try:
                connector = _connector_from_dict(connector_payload)
            except (KeyError, TypeError, ValueError) as exc:
                raise ProductPackageError(
                    f"{path}/connectors/{index} is invalid: {exc}"
                ) from exc
            if connector.connector_id in assembly_connector_ids:
                raise ProductPackageError(f"{path}/connectors contains duplicate connector_id")
            assembly_connector_ids.add(connector.connector_id)
            if connector.anchor_kind == "geometry":
                raise ProductPackageError(f"{path}/connectors/{index} cannot use geometry anchor")
            anchor = connector.anchor
            if anchor is not None and anchor.anchor_kind == "forwarded":
                component_id = str(anchor.source_component_id)
                connector_id = str(anchor.source_connector_id)
                if component_id not in instance_ids:
                    raise ProductPackageError(
                        f"{path}/connectors/{index} forwards missing instance"
                    )
                if connector_id not in connector_ids_for_instance(component_id):
                    raise ProductPackageError(
                        f"{path}/connectors/{index} forwards missing connector"
                    )

        snapshot = node["solved_snapshot"]["component_placements"]
        snapshot_by_id = {str(item["component_id"]): item for item in snapshot}
        if len(snapshot_by_id) != len(snapshot) or set(snapshot_by_id) != instance_ids:
            raise ProductPackageError(
                f"{path}/solved_snapshot must contain every instance exactly once"
            )
        for instance_id, instance in instances_by_id.items():
            if snapshot_by_id[instance_id]["placement"] != instance["local_placement"]:
                raise ProductPackageError(
                    f"{path}/solved_snapshot placement differs from instance"
                )

        model_ref = node.get("model_ref")
        if model_ref is not None:
            _validate_ref(model_ref, blobs, f"{path}/model_ref")
            try:
                parse_strict_json(blobs[model_ref["uri"]])
            except (TypeError, ValueError) as exc:
                raise ProductPackageError(f"{path}/model_ref is invalid JSON") from exc
            referenced.add(str(model_ref["uri"]))

    validate_assembly_node(manifest, "")
    if set(blobs) != referenced:
        raise ProductPackageError("assembly package member set differs from manifest refs")


def _connector_from_dict(payload: Mapping[str, Any]) -> Connector:
    anchor_payload = payload.get("anchor")
    if not isinstance(anchor_payload, Mapping):
        raise ProductPackageError("connector anchor is required")
    kind = str(anchor_payload.get("anchor_kind"))
    if kind == "geometry":
        geometry_payload = anchor_payload.get("geometry_ref")
        if not isinstance(geometry_payload, Mapping):
            raise ProductPackageError("geometry connector requires geometry_ref")
        geometry_ref = GeometryRef(
            kind=str(geometry_payload["kind"]),
            source_node_id=geometry_payload.get("source_node_id"),
            geo_selector=dict(geometry_payload["geo_selector"]),
            flip=bool(geometry_payload.get("flip", False)),
        )
        anchor = ConnectorAnchor("geometry", geometry_ref=geometry_ref)
        return Connector(str(payload["connector_id"]), geometry_ref, name=payload.get("name"), anchor=anchor)
    if kind == "placement":
        placement = Placement(**dict(anchor_payload["placement"]))
        return Connector(
            str(payload["connector_id"]),
            name=payload.get("name"),
            anchor=ConnectorAnchor("placement", placement=placement),
        )
    if kind == "forwarded":
        offset_payload = anchor_payload.get("offset")
        offset = Placement(**dict(offset_payload)) if offset_payload is not None else None
        return Connector(
            str(payload["connector_id"]),
            name=payload.get("name"),
            anchor=ConnectorAnchor(
                "forwarded",
                source_component_id=str(anchor_payload["source_component_id"]),
                source_connector_id=str(anchor_payload["source_connector_id"]),
                offset=offset,
            ),
        )
    raise ProductPackageError(f"unsupported connector anchor kind: {kind}")


def _material_from_dict(payload: Mapping[str, Any]) -> Material:
    return Material(
        material_id=str(payload["material_id"]),
        name=payload.get("name"),
        density=payload.get("density"),
        density_unit=payload.get("density_unit"),
        color=tuple(payload["color"]) if payload.get("color") is not None else None,
    )

def _part_from_manifest(
    manifest: Mapping[str, Any],
    blobs: Mapping[str, bytes],
) -> Part:
    body = _read_brep(blobs[manifest["body_ref"]["uri"]])
    connector_payload = parse_canonical_json(
        blobs[manifest["connector_ref"]["uri"]]
    )
    material = None
    if manifest.get("material_ref") is not None:
        material = _material_from_dict(
            parse_canonical_json(blobs[manifest["material_ref"]["uri"]])
        )
    return Part(
        part_id=str(manifest["part_id"]),
        body=body,
        name=manifest.get("name"),
        material=material,
        connectors=tuple(
            _connector_from_dict(item) for item in connector_payload["connectors"]
        ),
    )


def load_part_package(
    data: bytes | bytearray | memoryview | str | Path,
) -> Part:
    package = read_product_package(data, kind="part")
    return _part_from_manifest(package.manifest, package.blobs)


def _constraint_from_dict(payload: Mapping[str, Any]) -> Constraint:
    def limit(value: Any) -> ScalarLimit | None:
        return ScalarLimit(**dict(value)) if value is not None else None

    return Constraint(
        constraint_id=str(payload["constraint_id"]),
        constraint_kind=str(payload["constraint_kind"]),
        connector_a=ConnectorRef(**dict(payload["connector_a"])),
        connector_b=ConnectorRef(**dict(payload["connector_b"])),
        drive_distance=payload.get("drive_distance"),
        distance_limit=limit(payload.get("distance_limit")),
        drive_angle_degrees=payload.get("drive_angle_degrees"),
        angle_limit=limit(payload.get("angle_limit")),
        pitch_radius_a=payload.get("pitch_radius_a"),
        pitch_radius_b=payload.get("pitch_radius_b"),
        pulley_radius_a=payload.get("pulley_radius_a"),
        pulley_radius_b=payload.get("pulley_radius_b"),
        pitch_radius=payload.get("pitch_radius"),
        phase_offset=payload.get("phase_offset"),
        name=payload.get("name"),
    )


def load_assembly_package(
    data: bytes | bytearray | memoryview | str | Path,
) -> Assembly:
    package = read_product_package(data, kind="assembly")
    manifest_by_uri: dict[str, Mapping[str, Any]] = {}

    def collect(node: Mapping[str, Any]) -> None:
        for ref in node["definitions"]:
            uri = str(ref["uri"])
            if uri in manifest_by_uri:
                continue
            child = parse_canonical_json(package.blobs[uri])
            manifest_by_uri[uri] = child
            if child["artifact_kind"] == "assembly":
                collect(child)

    collect(package.manifest)
    loaded: dict[str, Part | Assembly] = {}

    def load_definition(uri: str) -> Part | Assembly:
        existing = loaded.get(uri)
        if existing is not None:
            return existing
        child = manifest_by_uri[uri]
        if child["artifact_kind"] == "part":
            result: Part | Assembly = _part_from_manifest(child, package.blobs)
        else:
            result = load_assembly_manifest(child)
        loaded[uri] = result
        return result

    def load_assembly_manifest(node: Mapping[str, Any]) -> Assembly:
        components = tuple(
            Component(
                component_id=str(instance["instance_id"]),
                item=load_definition(str(instance["definition_ref"])),
                placement=Placement(**dict(instance["local_placement"])),
                name=instance.get("name"),
            )
            for instance in node["instances"]
        )
        return Assembly(
            assembly_id=str(node["assembly_id"]),
            name=node.get("name"),
            components=components,
            connectors=tuple(
                _connector_from_dict(item) for item in node.get("connectors", [])
            ),
            constraints=tuple(
                _constraint_from_dict(item) for item in node.get("relations", [])
            ),
            grounded_component_ids=tuple(node.get("grounded_instance_ids", [])),
        )

    return load_assembly_manifest(package.manifest)


__all__ = [
    "PRODUCT_SCHEMA_VERSION",
    "ProductPackage",
    "ProductPackageError",
    "build_part_package",
    "build_assembly_package",
    "export_product_package",
    "encode_product_package",
    "read_product_package",
    "validate_product_package",
    "load_part_package",
    "load_assembly_package",
]
