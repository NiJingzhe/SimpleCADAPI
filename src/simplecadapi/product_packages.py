"""Canonical self-contained package for a durable Part/Assembly definition graph."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from functools import lru_cache
from importlib.resources import files
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .artifacts.assembly_definition import AssemblyDefinition
from .artifacts.assembly_io import (
    decode_assembly_definition,
    definition_archive_name,
    encode_assembly_definition,
    assembly_definition_graph_is_validated,
    validate_assembly_definition_graph,
)
from .artifacts.canonical import (
    ArtifactLimits,
    ArtifactValidationError,
    DEFAULT_ARTIFACT_LIMITS,
    canonical_bytes,
    content_hash,
    parse_canonical_json,
    sha256_bytes,
)
from .artifacts.part_definition import PartDefinition
from .artifacts.part_io import encode_part_definition, load_part_definition
from .scene.archive import canonical_zip_bytes, preflight_zip_bytes
from .scene.product_scene import (
    ProductSceneError,
    compile_product_scene,
    encode_product_scene,
    read_scene_package,
)

PRODUCT_PACKAGE_SCHEMA_VERSION = "2.0"
_MANIFEST_NAME = "package.json"

Definition = PartDefinition | AssemblyDefinition


class ProductPackageError(ValueError):
    """Raised when a product package violates its closed artifact contract."""


@dataclass(frozen=True, slots=True)
class ProductPackage:
    """Validated package containing one root definition and its complete closure."""

    manifest: Mapping[str, Any]
    objects: Mapping[str, bytes]
    root_definition: Definition = field(compare=False, repr=False)
    _validated_manifest: bytes | None = field(
        default=None,
        init=False,
        compare=False,
        repr=False,
    )
    _validated_limits: ArtifactLimits | None = field(
        default=None,
        init=False,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest", MappingProxyType(dict(self.manifest)))
        object.__setattr__(
            self,
            "objects",
            MappingProxyType(
                {str(path): bytes(payload) for path, payload in self.objects.items()}
            ),
        )
        if not isinstance(self.root_definition, (PartDefinition, AssemblyDefinition)):
            raise TypeError(
                "root_definition must be a PartDefinition or AssemblyDefinition"
            )

    @property
    def content_hash(self) -> str:
        return str(self.manifest["content_hash"])

    @property
    def root_path(self) -> str:
        return str(self.manifest["root"])

    @property
    def root_kind(self) -> str:
        return self.root_definition.definition_kind

    @property
    def root_id(self) -> str:
        return self.root_definition.definition_id

    @property
    def scene_path(self) -> str:
        return str(self.manifest["scene"]["path"])

    @property
    def scene_bytes(self) -> bytes:
        return self.objects[self.scene_path]


def _mark_package_validated(
    package: ProductPackage,
    limits: ArtifactLimits,
) -> None:
    object.__setattr__(
        package,
        "_validated_manifest",
        canonical_bytes(dict(package.manifest)),
    )
    object.__setattr__(package, "_validated_limits", limits)


def _package_is_validated(
    package: ProductPackage,
    limits: ArtifactLimits,
) -> bool:
    return (
        package._validated_limits == limits
        and package._validated_manifest == canonical_bytes(dict(package.manifest))
    )


@lru_cache(maxsize=1)
def _schema() -> Mapping[str, Any]:
    resource = files("simplecadapi").joinpath(
        "contracts", "product-package-2.schema.json"
    )
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _schema_validate(manifest: Mapping[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(_schema()).iter_errors(dict(manifest)),
        key=lambda item: (list(item.absolute_path), item.message),
    )
    if errors:
        error = errors[0]
        pointer = "/" + "/".join(str(item) for item in error.absolute_path)
        raise ProductPackageError(
            f"product package schema invalid at {pointer}: {error.message}"
        )


def _coerce_definition(value: Any) -> Definition:
    definition = (
        value
        if isinstance(value, (PartDefinition, AssemblyDefinition))
        else getattr(value, "definition", None)
    )
    if not isinstance(definition, (PartDefinition, AssemblyDefinition)):
        raise TypeError(
            "value must be a PartDefinition, AssemblyDefinition, PartBuildResult, "
            "or AssemblyBuildResult"
        )
    return definition


def _definition_bytes(definition: Definition) -> bytes:
    return (
        encode_part_definition(definition)
        if isinstance(definition, PartDefinition)
        else encode_assembly_definition(definition)
    )


def _object_path(definition: Definition) -> str:
    return f"objects/{definition_archive_name(definition)}"


def _object_record(definition: Definition, payload: bytes) -> dict[str, Any]:
    return {
        "path": _object_path(definition),
        "definition_kind": definition.definition_kind,
        "definition_id": definition.definition_id,
        "revision": definition.revision,
        "content_hash": definition.content_hash,
        "sha256": sha256_bytes(payload),
        "byte_length": len(payload),
    }


def _collect_definition_closure(
    root: Definition,
) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    if isinstance(
        root, AssemblyDefinition
    ) and not assembly_definition_graph_is_validated(root):
        validate_assembly_definition_graph(root)
    identities: dict[str, tuple[str, str]] = {}
    records_by_path: dict[str, dict[str, Any]] = {}
    objects: dict[str, bytes] = {}
    active: set[tuple[str, str]] = set()

    def visit(definition: Definition) -> None:
        key = (definition.definition_kind, definition.content_hash)
        if key in active:
            raise ProductPackageError(
                f"cyclic definition graph at {definition.definition_id!r}"
            )
        identity = identities.get(definition.definition_id)
        current = (definition.definition_kind, definition.content_hash)
        if identity is not None and identity != current:
            raise ProductPackageError(
                f"definition_id {definition.definition_id!r} resolves to multiple identities"
            )
        identities[definition.definition_id] = current
        path = _object_path(definition)
        if path in objects:
            return
        active.add(key)
        try:
            payload = _definition_bytes(definition)
            objects[path] = payload
            records_by_path[path] = _object_record(definition, payload)
            if isinstance(definition, AssemblyDefinition):
                for ref in definition.definition_refs:
                    child = definition.resolved_definitions.get(ref.definition_id)
                    if not isinstance(child, (PartDefinition, AssemblyDefinition)):
                        raise ProductPackageError(
                            f"assembly {definition.definition_id!r} has an unresolved "
                            f"definition {ref.definition_id!r}"
                        )
                    visit(child)
        finally:
            active.remove(key)

    visit(root)
    records = [records_by_path[path] for path in sorted(records_by_path)]
    return records, objects


def _manifest(
    root_path: str,
    records: list[dict[str, Any]],
    scene_payload: bytes,
    scene_id: str,
    scene_revision: str,
) -> dict[str, Any]:
    draft = {
        "schema_version": PRODUCT_PACKAGE_SCHEMA_VERSION,
        "artifact_kind": "product_package",
        "root": root_path,
        "objects": records,
        "scene": {
            "path": "scene/scene.zip",
            "media_type": "application/vnd.simplecad.scene+zip",
            "scene_id": scene_id,
            "revision": scene_revision,
            "sha256": sha256_bytes(scene_payload),
            "byte_length": len(scene_payload),
        },
    }
    return {**draft, "content_hash": content_hash(draft, omit=())}


def build_product_package(value: Any) -> ProductPackage:
    """Build a package from an existing durable definition without reevaluation."""

    root = _coerce_definition(value)
    records, objects = _collect_definition_closure(root)
    scene = compile_product_scene(root)
    scene_payload = encode_product_scene(scene)
    objects["scene/scene.zip"] = scene_payload
    manifest = _manifest(
        _object_path(root),
        records,
        scene_payload,
        str(scene.manifest["scene_id"]),
        str(scene.manifest["revision"]),
    )
    package = ProductPackage(manifest=manifest, objects=objects, root_definition=root)
    _mark_package_validated(package, DEFAULT_ARTIFACT_LIMITS)
    return package


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if not isinstance(manifest, Mapping):
        raise ProductPackageError("product package manifest must be an object")
    _schema_validate(manifest)
    records = manifest["objects"]
    paths = [str(item["path"]) for item in records]
    if paths != sorted(paths, key=lambda item: item.encode("ascii")):
        raise ProductPackageError("product package objects must be path-sorted")
    if len(paths) != len(set(paths)):
        raise ProductPackageError("product package object paths must be unique")
    identities = [
        (
            str(item["definition_kind"]),
            str(item["definition_id"]),
            str(item["content_hash"]),
        )
        for item in records
    ]
    if len(identities) != len(set(identities)):
        raise ProductPackageError("product package object identities must be unique")
    if manifest["root"] not in set(paths):
        raise ProductPackageError("product package root does not resolve to an object")
    scene_path = str(manifest["scene"]["path"])
    if scene_path in set(paths):
        raise ProductPackageError("scene path must not collide with a definition object")
    expected_hash = content_hash(
        {key: item for key, item in manifest.items() if key != "content_hash"},
        omit=(),
    )
    if manifest["content_hash"] != expected_hash:
        raise ProductPackageError("product package content_hash is invalid")


def _decode_definition_objects(
    manifest: Mapping[str, Any],
    objects: Mapping[str, bytes],
    *,
    limits: ArtifactLimits,
) -> Definition:
    _validate_manifest(manifest)
    records = manifest["objects"]
    if len(records) > limits.max_definitions:
        raise ProductPackageError("product package exceeds the definition limit")
    expected_paths = {str(item["path"]) for item in records}
    scene_path = str(manifest["scene"]["path"])
    if set(objects) != expected_paths | {scene_path}:
        raise ProductPackageError(
            "product package member set differs from object and scene records"
        )

    decoded_by_path: dict[str, Definition] = {}
    identity_to_path: dict[tuple[str, str, str, str], str] = {}
    total_bytes = 0
    for index, record in enumerate(records):
        path = str(record["path"])
        payload = objects[path]
        total_bytes += len(payload)
        if total_bytes > limits.max_total_bytes:
            raise ProductPackageError("product package object bytes exceed the limit")
        if record["byte_length"] != len(payload):
            raise ProductPackageError(f"object {path!r} byte_length differs")
        if record["sha256"] != sha256_bytes(payload):
            raise ProductPackageError(f"object {path!r} sha256 differs")
        try:
            if record["definition_kind"] == "single_solid":
                definition: Definition = load_part_definition(payload)
            else:
                definition = decode_assembly_definition(payload)
        except (ArtifactValidationError, ValueError) as exc:
            raise ProductPackageError(f"object {path!r} is invalid: {exc}") from exc
        expected = (
            str(record["definition_kind"]),
            str(record["definition_id"]),
            str(record["revision"]),
            str(record["content_hash"]),
        )
        actual = (
            definition.definition_kind,
            definition.definition_id,
            definition.revision,
            definition.content_hash,
        )
        if actual != expected:
            raise ProductPackageError(
                f"object record {index} identity differs from archive"
            )
        expected_path = _object_path(definition)
        if path != expected_path:
            raise ProductPackageError(
                f"object {path!r} must use canonical path {expected_path!r}"
            )
        if actual in identity_to_path:
            raise ProductPackageError(f"definition archive {path!r} is duplicated")
        identity_to_path[actual] = path
        decoded_by_path[path] = definition

    resolved_by_path: dict[str, Definition] = {}
    active: set[str] = set()
    reachable: set[str] = set()

    def resolve(path: str) -> Definition:
        reachable.add(path)
        existing = resolved_by_path.get(path)
        if existing is not None:
            return existing
        if path in active:
            raise ProductPackageError(f"definition cycle through object {path!r}")
        definition = decoded_by_path[path]
        if isinstance(definition, PartDefinition):
            resolved_by_path[path] = definition
            return definition
        active.add(path)
        try:
            resolved: dict[str, Definition] = {}
            for ref in definition.definition_refs:
                key = (
                    ref.definition_kind,
                    ref.definition_id,
                    ref.revision,
                    ref.content_hash,
                )
                child_path = identity_to_path.get(key)
                if child_path is None:
                    raise ProductPackageError(
                        f"assembly {definition.definition_id!r} references missing "
                        f"definition {ref.definition_id!r}"
                    )
                if PurePosixPath(child_path).name != ref.path:
                    raise ProductPackageError(
                        f"assembly reference path for {ref.definition_id!r} differs "
                        "from the embedded canonical object name"
                    )
                child = resolve(child_path)
                if ref.byte_length != len(objects[child_path]):
                    raise ProductPackageError(
                        f"assembly reference size for {ref.definition_id!r} differs"
                    )
                resolved[ref.definition_id] = child
            result: Definition = replace(definition, resolved_definitions=resolved)
            resolved_by_path[path] = result
            return result
        finally:
            active.remove(path)

    root = resolve(str(manifest["root"]))
    if reachable != expected_paths:
        unused = sorted(
            expected_paths - reachable, key=lambda item: item.encode("ascii")
        )
        raise ProductPackageError(f"unreferenced definition object: {unused[0]}")
    if isinstance(root, AssemblyDefinition):
        try:
            validate_assembly_definition_graph(root, limits=limits)
        except ArtifactValidationError as exc:
            raise ProductPackageError(f"root assembly graph is invalid: {exc}") from exc

    scene_record = manifest["scene"]
    scene_payload = objects[scene_path]
    if scene_record["byte_length"] != len(scene_payload):
        raise ProductPackageError("embedded scene byte_length differs")
    if scene_record["sha256"] != sha256_bytes(scene_payload):
        raise ProductPackageError("embedded scene sha256 differs")
    try:
        scene = read_scene_package(scene_payload)
    except (ProductSceneError, ValueError) as exc:
        raise ProductPackageError(f"embedded scene is invalid: {exc}") from exc
    if (
        scene.manifest["scene_id"] != scene_record["scene_id"]
        or scene.manifest["revision"] != scene_record["revision"]
        or scene.manifest["scene_id"] != root.definition_id
    ):
        raise ProductPackageError("embedded scene identity differs")
    packaged_identities = {
        (
            str(item["definition_kind"]),
            str(item["definition_id"]),
            str(item["revision"]),
            str(item["content_hash"]),
        )
        for item in records
    }
    scene_identities = {
        (
            str(item["definition_kind"]),
            str(item["definition_id"]),
            str(item["revision"]),
            str(item["content_hash"]),
        )
        for item in scene.manifest["definitions"]
    }
    if scene_identities != packaged_identities:
        raise ProductPackageError("embedded scene definition closure differs")
    return root


def validate_product_package(
    package: ProductPackage,
    *,
    limits: ArtifactLimits = DEFAULT_ARTIFACT_LIMITS,
) -> None:
    """Validate the manifest, every object archive, and the complete definition DAG."""

    if not isinstance(package, ProductPackage):
        raise TypeError("package must be a ProductPackage")
    root = _decode_definition_objects(package.manifest, package.objects, limits=limits)
    if (
        root.definition_kind != package.root_definition.definition_kind
        or root.definition_id != package.root_definition.definition_id
        or root.content_hash != package.root_definition.content_hash
    ):
        raise ProductPackageError("root_definition differs from packaged root")
    _mark_package_validated(package, limits)


def encode_product_package(package: ProductPackage) -> bytes:
    """Return canonical `.scadpkg` bytes."""

    if not _package_is_validated(package, DEFAULT_ARTIFACT_LIMITS):
        validate_product_package(package)
    return canonical_zip_bytes(
        {_MANIFEST_NAME: canonical_bytes(dict(package.manifest)), **package.objects},
        manifest_name=_MANIFEST_NAME,
    )




def read_product_package(
    data: bytes | bytearray | memoryview | str | Path,
    *,
    limits: ArtifactLimits = DEFAULT_ARTIFACT_LIMITS,
) -> ProductPackage:
    """Read and validate one self-contained product package."""
    raw = Path(data).read_bytes() if isinstance(data, (str, Path)) else bytes(data)
    archive = preflight_zip_bytes(raw, manifest_name=_MANIFEST_NAME)
    manifest = parse_canonical_json(archive.members[_MANIFEST_NAME])
    if not isinstance(manifest, Mapping):
        raise ProductPackageError("package.json must contain an object")
    objects = {
        path: payload
        for path, payload in archive.members.items()
        if path != _MANIFEST_NAME
    }
    root = _decode_definition_objects(manifest, objects, limits=limits)
    package = ProductPackage(
        manifest=manifest,
        objects=objects,
        root_definition=root,
    )
    _mark_package_validated(package, limits)
    return package


def load_product_package(
    data: bytes | bytearray | memoryview | str | Path,
    *,
    limits: ArtifactLimits = DEFAULT_ARTIFACT_LIMITS,
) -> Definition:
    """Load the durable root definition from one self-contained package."""

    return read_product_package(data, limits=limits).root_definition


__all__ = [
    "PRODUCT_PACKAGE_SCHEMA_VERSION",
    "ProductPackage",
    "ProductPackageError",
    "build_product_package",
    "encode_product_package",
    "load_product_package",
    "read_product_package",
    "validate_product_package",
]
