"""Crash-safe content-addressed object and key-record store."""

from __future__ import annotations

import errno
import os
import time
import shutil
import uuid
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from ..artifacts.canonical import (
    ArtifactValidationError,
    canonical_bytes,
    parse_canonical_json,
    sha256_bytes,
    validate_hash,
)
from .policy import CachePolicy
from .records import CacheRecord


class CacheLockTimeout(TimeoutError):
    """Raised when a cache key remains locked past policy timeout."""


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """Validated cache record and its object payload."""
    record: CacheRecord
    payload: bytes


@dataclass(frozen=True, slots=True)
class CacheStats:
    """Aggregate content-addressed store counts and object bytes."""
    objects: int
    records: int
    locks: int
    quarantined: int
    object_bytes: int


class ContentAddressedStore:
    """Persistent CAS whose corrupt entries degrade to misses."""

    def __init__(self, policy: CachePolicy) -> None:
        if not isinstance(policy, CachePolicy):
            raise TypeError("policy must be a CachePolicy")
        self.policy = policy
        self.root = policy.root
        self.objects_dir = self.root / "objects" / "sha256"
        self.records_dir = self.root / "records"
        self.locks_dir = self.root / "locks"
        self.quarantine_dir = self.root / "quarantine"
        if policy.can_write:
            for directory in (
                self.objects_dir,
                self.records_dir,
                self.locks_dir,
                self.quarantine_dir,
            ):
                directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _digest(value: str) -> str:
        return validate_hash(value, "/hash").removeprefix("sha256:")

    @staticmethod
    def _namespace(namespace: str) -> str:
        # Reuse CacheRecord's closed namespace grammar without persisting a dummy record.
        CacheRecord(namespace, "sha256:" + "0" * 64, "sha256:" + "0" * 64, 0, "application/octet-stream")
        return namespace

    def object_path(self, object_hash: str) -> Path:
        digest = self._digest(object_hash)
        return self.objects_dir / digest[:2] / digest[2:]

    def record_path(self, namespace: str, key: str) -> Path:
        namespace = self._namespace(namespace)
        digest = self._digest(key)
        return self.records_dir / namespace / digest[:2] / f"{digest[2:]}.json"

    def lock_path(self, namespace: str, key: str) -> Path:
        namespace = self._namespace(namespace)
        digest = self._digest(key)
        return self.locks_dir / namespace / digest[:2] / f"{digest[2:]}.lock"

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @classmethod
    def _atomic_write(cls, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            cls._fsync_directory(path.parent)
        except BaseException:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            raise

    def _quarantine(self, path: Path, reason: str) -> None:
        if not self.policy.can_write or not self.policy.quarantine_corrupt or not path.exists():
            return
        relative = path.relative_to(self.root)
        destination = self.quarantine_dir / reason / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination = destination.with_name(destination.name + f".{uuid.uuid4().hex}.bad")
        try:
            os.replace(path, destination)
            self._fsync_directory(destination.parent)
        except FileNotFoundError:
            return

    def _load_record(self, namespace: str, key: str) -> CacheRecord | None:
        path = self.record_path(namespace, key)
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            record = CacheRecord.from_bytes(payload)
            if record.namespace != namespace or record.key != key:
                raise ArtifactValidationError("cache_record_invalid", "/key", "record address differs")
            return record
        except (ArtifactValidationError, OSError, ValueError):
            self._quarantine(path, "record")
            return None

    def get(self, namespace: str, key: str) -> CacheEntry | None:
        if not self.policy.can_read:
            return None
        record = self._load_record(namespace, key)
        if record is None:
            return None
        object_path = self.object_path(record.object_hash)
        try:
            payload = object_path.read_bytes()
        except FileNotFoundError:
            self._quarantine(self.record_path(namespace, key), "missing-object")
            return None
        if len(payload) != record.byte_length:
            self._quarantine(object_path, "object-size")
            self._quarantine(self.record_path(namespace, key), "record-object-size")
            return None
        if self.policy.verify_reads and sha256_bytes(payload) != record.object_hash:
            self._quarantine(object_path, "object-hash")
            self._quarantine(self.record_path(namespace, key), "record-object-hash")
            return None
        return CacheEntry(record=record, payload=payload)

    def discard(self, namespace: str, key: str, *, reason: str = "invalid") -> None:
        """Quarantine one key record after semantic payload validation fails."""

        if not self.policy.can_write:
            return

        path = self.record_path(namespace, key)
        if self.policy.quarantine_corrupt:
            self._quarantine(path, reason)
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def _put_locked(
        self,
        namespace: str,
        key: str,
        payload: bytes,
        *,
        media_type: str,
        metadata: Mapping[str, Any] | None,
    ) -> CacheRecord:
        object_hash = sha256_bytes(payload)
        record = CacheRecord(
            namespace=namespace,
            key=key,
            object_hash=object_hash,
            byte_length=len(payload),
            media_type=media_type,
            metadata={} if metadata is None else metadata,
        )
        object_path = self.object_path(object_hash)
        if object_path.exists():
            existing = object_path.read_bytes()
            if len(existing) != len(payload) or sha256_bytes(existing) != object_hash:
                self._quarantine(object_path, "object-existing-corrupt")
                self._atomic_write(object_path, payload)
        else:
            self._atomic_write(object_path, payload)
        self._atomic_write(self.record_path(namespace, key), record.canonical_bytes)
        return record

    def put_locked(
        self,
        namespace: str,
        key: str,
        payload: bytes | bytearray | memoryview,
        *,
        media_type: str = "application/octet-stream",
        metadata: Mapping[str, Any] | None = None,
    ) -> CacheRecord:
        """Write while the caller holds ``key_lock(namespace, key)``."""

        if not self.policy.can_write:
            raise PermissionError("cache policy does not allow writes")
        return self._put_locked(
            namespace,
            key,
            bytes(payload),
            media_type=media_type,
            metadata=metadata,
        )

    def put(
        self,
        namespace: str,
        key: str,
        payload: bytes | bytearray | memoryview,
        *,
        media_type: str = "application/octet-stream",
        metadata: Mapping[str, Any] | None = None,
    ) -> CacheRecord:
        if not self.policy.can_write:
            raise PermissionError("cache policy does not allow writes")
        raw = bytes(payload)
        with self.key_lock(namespace, key):
            return self._put_locked(namespace, key, raw, media_type=media_type, metadata=metadata)

    def get_or_compute(
        self,
        namespace: str,
        key: str,
        compute: Callable[[], bytes | bytearray | memoryview],
        *,
        media_type: str = "application/octet-stream",
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[CacheEntry, bool]:
        """Return (entry, hit); one process computes a missing key."""

        if self.policy.can_read:
            hit = self.get(namespace, key)
            if hit is not None:
                return hit, True
        if not self.policy.can_write:
            payload = bytes(compute())
            record = CacheRecord(namespace, key, sha256_bytes(payload), len(payload), media_type, metadata or {})
            return CacheEntry(record, payload), False
        with self.key_lock(namespace, key):
            if self.policy.can_read:
                hit = self.get(namespace, key)
                if hit is not None:
                    return hit, True
            payload = bytes(compute())
            record = self._put_locked(namespace, key, payload, media_type=media_type, metadata=metadata)
            return CacheEntry(record, payload), False

    @contextmanager
    def key_lock(self, namespace: str, key: str) -> Iterator[None]:
        path = self.lock_path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.policy.lock_timeout_seconds
        payload = canonical_bytes({"pid": os.getpid(), "created_ns": str(time.time_ns())})
        while True:
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                try:
                    os.write(descriptor, payload)
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                self._fsync_directory(path.parent)
                break
            except FileExistsError:
                try:
                    age = time.time() - path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > self.policy.stale_lock_seconds:
                    stale = path.with_name(path.name + f".{uuid.uuid4().hex}.stale")
                    try:
                        os.replace(path, stale)
                        stale.unlink(missing_ok=True)
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise CacheLockTimeout(f"cache key remained locked: {namespace}/{key}")
                time.sleep(0.01)
        try:
            yield
        finally:
            try:
                path.unlink()
                self._fsync_directory(path.parent)
            except FileNotFoundError:
                pass

    def _record_files(self, namespace: str | None = None) -> list[Path]:
        root = self.records_dir if namespace is None else self.records_dir / self._namespace(namespace)
        return sorted(root.rglob("*.json")) if root.exists() else []

    def _object_files(self) -> list[Path]:
        if not self.objects_dir.exists():
            return []
        return sorted(
            path
            for path in self.objects_dir.rglob("*")
            if path.is_file()
            and path.parent.parent == self.objects_dir
            and re.fullmatch(r"[0-9a-f]{2}", path.parent.name) is not None
            and re.fullmatch(r"[0-9a-f]{62}", path.name) is not None
        )

    def _referenced_objects(self) -> set[Path]:
        referenced: set[Path] = set()
        for path in self._record_files():
            try:
                record = CacheRecord.from_bytes(path.read_bytes())
                if self.record_path(record.namespace, record.key) == path:
                    referenced.add(self.object_path(record.object_hash))
            except (ArtifactValidationError, OSError, ValueError):
                continue
        return referenced

    def _orphan_objects(self) -> list[Path]:
        referenced = self._referenced_objects()
        return [path for path in self._object_files() if path not in referenced]

    def diagnostics(self, namespace: str | None = None) -> dict[str, int | str]:
        """Return stable counts without mutating cache state."""

        objects = self._object_files()
        locks = (
            [path for path in self.locks_dir.rglob("*.lock") if path.is_file()]
            if self.locks_dir.exists()
            else []
        )
        quarantine = (
            [path for path in self.quarantine_dir.rglob("*") if path.is_file()]
            if self.quarantine_dir.exists()
            else []
        )
        return {
            "root": str(self.root),
            "namespace": "*" if namespace is None else namespace,
            "records": len(self._record_files(namespace)),
            "objects": len(objects),
            "object_bytes": sum(path.stat().st_size for path in objects),
            "locks": len(locks),
            "quarantined": len(quarantine),
            "orphan_objects": len(self._orphan_objects()),
        }

    def verify_cache(
        self,
        namespace: str | None = None,
        *,
        repair: bool = False,
    ) -> dict[str, int | str | bool]:
        """Verify record/object integrity and optionally quarantine invalid entries."""

        if repair and not self.policy.can_write:
            raise PermissionError("cache policy does not allow repairs")
        files = self._record_files(namespace)
        invalid_records = 0
        missing_objects = 0
        invalid_objects = 0
        for path in files:
            object_path: Path | None = None
            try:
                record = CacheRecord.from_bytes(path.read_bytes())
                if namespace is not None and record.namespace != namespace:
                    raise ArtifactValidationError(
                        "cache_record_invalid", "/namespace", "record namespace differs"
                    )
                if self.record_path(record.namespace, record.key) != path:
                    raise ArtifactValidationError(
                        "cache_record_invalid", "/path", "record path differs"
                    )
                object_path = self.object_path(record.object_hash)
                payload = object_path.read_bytes()
                if len(payload) != record.byte_length:
                    invalid_objects += 1
                    raise ArtifactValidationError(
                        "cache_object_invalid", "/byte_length", "object size differs"
                    )
                if sha256_bytes(payload) != record.object_hash:
                    invalid_objects += 1
                    raise ArtifactValidationError(
                        "cache_object_invalid", "/object_hash", "object hash differs"
                    )
            except FileNotFoundError:
                missing_objects += 1
                invalid_records += 1
                if repair:
                    self._quarantine(path, "verify-missing-object")
            except (ArtifactValidationError, OSError, ValueError):
                invalid_records += 1
                if repair:
                    if object_path is not None and object_path.exists():
                        self._quarantine(object_path, "verify-invalid-object")
                    self._quarantine(path, "verify-invalid-record")

        orphan_objects = self._orphan_objects()
        return {
            "namespace": "*" if namespace is None else namespace,
            "records_checked": len(files),
            "invalid_records": invalid_records,
            "missing_objects": missing_objects,
            "invalid_objects": invalid_objects,
            "orphan_objects": len(orphan_objects),
            "repaired": bool(repair),
            "ok": invalid_records == 0 and not orphan_objects,
        }

    def prune_orphans(self, *, dry_run: bool = True) -> dict[str, int | bool]:
        """Report or quarantine objects not referenced by any cache record."""

        orphans = self._orphan_objects()
        reclaimed_bytes = sum(path.stat().st_size for path in orphans)
        if not dry_run:
            if not self.policy.can_write:
                raise PermissionError("cache policy does not allow pruning")
            for path in orphans:
                self._quarantine(path, "prune-orphan-object")
        return {
            "orphan_objects": len(orphans),
            "reclaimed_bytes": reclaimed_bytes,
            "dry_run": bool(dry_run),
        }

    def clear_cache(
        self,
        namespace: str | None = None,
        *,
        confirm: bool = False,
    ) -> dict[str, int | str | bool]:
        """Remove records in one namespace, or the complete cache when confirmed."""

        if not confirm:
            raise ValueError("clear_cache requires confirm=True")
        if not self.policy.can_write:
            raise PermissionError("cache policy does not allow clearing")
        before = self.diagnostics(namespace)
        if namespace is None:
            shutil.rmtree(self.root, ignore_errors=True)
        else:
            shutil.rmtree(self.records_dir / self._namespace(namespace), ignore_errors=True)
            self.prune_orphans(dry_run=False)
        return {**before, "cleared": True}

    def stats(self) -> CacheStats:
        def files_under(path: Path) -> list[Path]:
            return [item for item in path.rglob("*") if item.is_file()] if path.exists() else []

        objects = files_under(self.objects_dir)
        records = files_under(self.records_dir)
        locks = files_under(self.locks_dir)
        quarantine = files_under(self.quarantine_dir)
        return CacheStats(
            objects=len(objects),
            records=len(records),
            locks=len(locks),
            quarantined=len(quarantine),
            object_bytes=sum(item.stat().st_size for item in objects),
        )


__all__ = [
    "CacheEntry",
    "CacheLockTimeout",
    "CacheStats",
    "ContentAddressedStore",
]
