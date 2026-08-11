"""Structured part interface diffs and latest-state persistence."""

from __future__ import annotations

import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .canonical import (
    ArtifactValidationError,
    canonical_bytes,
    parse_canonical_json,
    validate_hash,
    validate_logical_id,
)
from .part_definition import PartDefinition
from .references import InterfaceHashes


@dataclass(frozen=True, slots=True)
class PartInterfaceSnapshot:
    """The stable interface subset persisted in ``latest-parts.json``."""

    definition_id: str
    definition_hash: str
    build_key: str
    interface_hashes: InterfaceHashes

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            validate_logical_id(self.definition_id, "/definition_id"),
        )
        object.__setattr__(
            self,
            "definition_hash",
            validate_hash(self.definition_hash, "/definition_hash"),
        )
        object.__setattr__(
            self,
            "build_key",
            validate_hash(self.build_key, "/build_key"),
        )
        if not isinstance(self.interface_hashes, InterfaceHashes):
            raise ArtifactValidationError(
                "interface_invalid",
                "/interface_hashes",
                "expected InterfaceHashes",
            )

    @classmethod
    def from_definition(
        cls,
        definition: PartDefinition,
        *,
        build_key: str,
    ) -> "PartInterfaceSnapshot":
        if not isinstance(definition, PartDefinition):
            raise TypeError("definition must be a PartDefinition")
        return cls(
            definition_id=definition.definition_id,
            definition_hash=definition.content_hash,
            build_key=build_key,
            interface_hashes=definition.interface_hashes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_hash": self.definition_hash,
            "build_key": self.build_key,
            "interface_hashes": self.interface_hashes.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        definition_id: str,
        value: Mapping[str, Any],
    ) -> "PartInterfaceSnapshot":
        required = {"definition_hash", "build_key", "interface_hashes"}
        if not isinstance(value, Mapping) or set(value) != required:
            raise ArtifactValidationError(
                "state_invalid",
                f"/parts/{definition_id}",
                "state entry fields are not closed",
            )
        return cls(
            definition_id=definition_id,
            definition_hash=str(value["definition_hash"]),
            build_key=str(value["build_key"]),
            interface_hashes=InterfaceHashes.from_dict(
                value["interface_hashes"],
                f"/parts/{definition_id}/interface_hashes",
            ),
        )


@dataclass(frozen=True, slots=True)
class PartInterfaceDiff:
    """Typed changes between two durable part interfaces."""

    definition_id_before: str
    definition_id_after: str
    build_key_changed: bool
    geometry_changed: bool
    connector_interface_changed: tuple[str, ...]
    connector_binding_changed: tuple[str, ...]
    connector_added: tuple[str, ...]
    connector_removed: tuple[str, ...]
    material_changed: bool

    @property
    def pose_dirty(self) -> bool:
        return bool(
            self.connector_interface_changed
            or self.connector_added
            or self.connector_removed
        )

    @property
    def geometry_dirty(self) -> bool:
        return self.geometry_changed

    @property
    def material_dirty(self) -> bool:
        return self.material_changed

    @property
    def interface_changed(self) -> bool:
        return bool(
            self.geometry_changed
            or self.connector_interface_changed
            or self.connector_binding_changed
            or self.connector_added
            or self.connector_removed
            or self.material_changed
        )

    @property
    def provenance_only(self) -> bool:
        return self.build_key_changed and not self.interface_changed

    def dirty_scopes(self) -> tuple[str, ...]:
        scopes: list[str] = []
        if self.geometry_changed:
            scopes.append("geometry")
        if self.pose_dirty:
            scopes.append("pose")
        if self.connector_binding_changed:
            scopes.append("binding_audit")
        if self.material_changed:
            scopes.append("material")
        if self.provenance_only:
            scopes.append("provenance")
        return tuple(scopes)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(
            pose_dirty=self.pose_dirty,
            geometry_dirty=self.geometry_dirty,
            material_dirty=self.material_dirty,
            interface_changed=self.interface_changed,
            provenance_only=self.provenance_only,
            dirty_scopes=list(self.dirty_scopes()),
        )
        return result


def _interface_snapshot(
    value: PartDefinition | PartInterfaceSnapshot,
    *,
    build_key: str | None = None,
) -> PartInterfaceSnapshot:
    if isinstance(value, PartInterfaceSnapshot):
        if build_key is not None and build_key != value.build_key:
            raise ValueError("build_key cannot override a PartInterfaceSnapshot")
        return value
    if isinstance(value, PartDefinition):
        return PartInterfaceSnapshot.from_definition(
            value,
            build_key=value.content_hash if build_key is None else build_key,
        )
    raise TypeError("interface value must be PartDefinition or PartInterfaceSnapshot")


def diff_part_interfaces(
    before: PartDefinition | PartInterfaceSnapshot,
    after: PartDefinition | PartInterfaceSnapshot,
    *,
    before_build_key: str | None = None,
    after_build_key: str | None = None,
) -> PartInterfaceDiff:
    """Compare durable interfaces and preserve connector deletion semantics."""

    previous = _interface_snapshot(before, build_key=before_build_key)
    current = _interface_snapshot(after, build_key=after_build_key)
    old_connectors = dict(previous.interface_hashes.connectors)
    new_connectors = dict(current.interface_hashes.connectors)
    old_bindings = dict(previous.interface_hashes.bindings)
    new_bindings = dict(current.interface_hashes.bindings)
    common_ids = set(old_connectors) & set(new_connectors)
    return PartInterfaceDiff(
        definition_id_before=previous.definition_id,
        definition_id_after=current.definition_id,
        build_key_changed=previous.build_key != current.build_key,
        geometry_changed=(
            previous.interface_hashes.geometry != current.interface_hashes.geometry
        ),
        connector_interface_changed=tuple(
            sorted(
                connector_id
                for connector_id in common_ids
                if old_connectors[connector_id] != new_connectors[connector_id]
            )
        ),
        connector_binding_changed=tuple(
            sorted(
                connector_id
                for connector_id in common_ids
                if old_bindings.get(connector_id) != new_bindings.get(connector_id)
            )
        ),
        connector_added=tuple(sorted(set(new_connectors) - set(old_connectors))),
        connector_removed=tuple(sorted(set(old_connectors) - set(new_connectors))),
        material_changed=(
            previous.interface_hashes.material != current.interface_hashes.material
        ),
    )


def load_latest_part_state(path: str | Path) -> dict[str, PartInterfaceSnapshot]:
    """Load a canonical latest-parts state file without creating it."""

    source = Path(path)
    try:
        payload = source.read_bytes()
    except FileNotFoundError:
        return {}
    try:
        value = parse_canonical_json(payload)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ArtifactValidationError("state_invalid", "/", str(exc)) from exc
    if canonical_bytes(value) != payload:
        raise ArtifactValidationError(
            "state_invalid", "/", "state bytes are not canonical"
        )
    if not isinstance(value, Mapping) or set(value) != {"schema_version", "parts"}:
        raise ArtifactValidationError(
            "state_invalid", "/", "state fields are not closed"
        )
    if value["schema_version"] != "1.0" or not isinstance(value["parts"], Mapping):
        raise ArtifactValidationError("state_invalid", "/", "unsupported state schema")
    return {
        definition_id: PartInterfaceSnapshot.from_dict(definition_id, entry)
        for definition_id, entry in value["parts"].items()
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
        parent_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def _state_lock(
    path: Path,
    *,
    timeout_seconds: float = 30.0,
    stale_seconds: float = 300.0,
) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            descriptor = os.open(
                lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
            os.close(descriptor)
            break
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > stale_seconds
            except FileNotFoundError:
                continue
            if stale:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"latest part state remained locked: {path}")
            time.sleep(0.01)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def update_latest_part_state(
    path: str | Path,
    *,
    definition: PartDefinition,
    build_key: str,
) -> PartInterfaceSnapshot | None:
    """Atomically replace one latest interface entry and return its predecessor."""

    current = PartInterfaceSnapshot.from_definition(
        definition,
        build_key=build_key,
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _state_lock(destination):
        parts = load_latest_part_state(destination)
        previous = parts.get(current.definition_id)
        if previous == current:
            return previous
        parts[current.definition_id] = current
        payload = {
            "schema_version": "1.0",
            "parts": {
                definition_id: snapshot.to_dict()
                for definition_id, snapshot in sorted(parts.items())
            },
        }
        _atomic_write(destination, canonical_bytes(payload))
        return previous


def write_latest_part_state(
    path: str | Path,
    *,
    definition: PartDefinition,
    build_key: str,
) -> Path:
    """Persist one entry while retaining all other latest-part state."""

    update_latest_part_state(path, definition=definition, build_key=build_key)
    return Path(path)


__all__ = [
    "PartInterfaceDiff",
    "PartInterfaceSnapshot",
    "diff_part_interfaces",
    "load_latest_part_state",
    "update_latest_part_state",
    "write_latest_part_state",
]
