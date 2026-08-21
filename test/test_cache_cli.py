from __future__ import annotations

from pathlib import Path

from simplecadapi.artifacts.canonical import sha256_bytes
from simplecadapi.cache.cli import run
from simplecadapi.cache.policy import CacheMode, CachePolicy
from simplecadapi.cache.store import ContentAddressedStore


def _store(root: Path) -> ContentAddressedStore:
    return ContentAddressedStore(CachePolicy(root=root, mode=CacheMode.READ_WRITE))


def test_status_verify_and_prune_report_stable_counts(tmp_path):
    root = tmp_path / "cache"
    store = _store(root)
    store.put("part", sha256_bytes(b"part-key"), b"shared")
    store.put("assembly", sha256_bytes(b"assembly-key"), b"shared")
    orphan = store.object_path(sha256_bytes(b"orphan"))
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"orphan")

    status, exit_code = run(["--cache-dir", str(root), "status", "--namespace", "part"])
    assert exit_code == 0
    assert status["records"] == 1
    assert status["objects"] == 2
    assert status["orphan_objects"] == 1

    verified, exit_code = run(["--cache-dir", str(root), "verify"])
    assert exit_code == 1
    assert verified["records_checked"] == 2
    assert verified["invalid_records"] == 0
    assert verified["orphan_objects"] == 1

    preview, exit_code = run(["--cache-dir", str(root), "prune"])
    assert exit_code == 0
    assert preview == {"orphan_objects": 1, "reclaimed_bytes": 6, "dry_run": True}
    assert orphan.exists()

    applied, exit_code = run(["--cache-dir", str(root), "prune", "--apply"])
    assert exit_code == 0
    assert applied["orphan_objects"] == 1
    assert applied["dry_run"] is False
    assert not orphan.exists()


def test_verify_detects_and_repairs_corrupt_object(tmp_path):
    root = tmp_path / "cache"
    store = _store(root)
    record = store.put("part", sha256_bytes(b"part-key"), b"valid")
    store.object_path(record.object_hash).write_bytes(b"broken")

    report, exit_code = run(["--cache-dir", str(root), "verify"])
    assert exit_code == 1
    assert report["invalid_records"] == 1
    assert report["invalid_objects"] == 1

    repaired, exit_code = run(["--cache-dir", str(root), "verify", "--repair"])
    assert exit_code == 1
    assert repaired["repaired"] is True
    assert store.stats().quarantined == 2

    clean, exit_code = run(["--cache-dir", str(root), "verify"])
    assert exit_code == 0
    assert clean["ok"] is True


def test_verify_hashes_objects_when_runtime_read_verification_is_disabled(tmp_path):
    root = tmp_path / "cache"
    store = ContentAddressedStore(
        CachePolicy(root=root, mode=CacheMode.READ_WRITE, verify_reads=False)
    )
    key = sha256_bytes(b"part-key")
    record = store.put("part", key, b"valid")
    store.object_path(record.object_hash).write_bytes(b"xxxxx")

    assert store.get("part", key) is not None
    report, exit_code = run(["--cache-dir", str(root), "verify"])
    assert exit_code == 1
    assert report["invalid_objects"] == 1


def test_read_only_commands_and_unconfirmed_clear_do_not_create_cache(tmp_path):
    root = tmp_path / "absent-cache"

    status, exit_code = run(["--cache-dir", str(root), "status"])
    assert exit_code == 0
    assert status["records"] == 0
    assert not root.exists()

    try:
        run(["--cache-dir", str(root), "clear"])
    except ValueError as exc:
        assert "--yes" in str(exc)
    else:
        raise AssertionError("clear without --yes must fail")
    assert not root.exists()


def test_clear_requires_confirmation_and_preserves_shared_objects(tmp_path):
    root = tmp_path / "cache"
    store = _store(root)
    payload = b"shared"
    part_key = sha256_bytes(b"part-key")
    assembly_key = sha256_bytes(b"assembly-key")
    part_record = store.put("part", part_key, payload)
    store.put("assembly", assembly_key, payload)

    try:
        run(["--cache-dir", str(root), "clear", "--namespace", "part"])
    except ValueError as exc:
        assert "confirm" in str(exc)
    else:
        raise AssertionError("clear without --yes must fail")

    report, exit_code = run(
        ["--cache-dir", str(root), "clear", "--namespace", "part", "--yes"]
    )
    assert exit_code == 0
    assert report["cleared"] is True
    assert store.get("part", part_key) is None
    assert store.get("assembly", assembly_key) is not None
    assert store.object_path(part_record.object_hash).exists()
