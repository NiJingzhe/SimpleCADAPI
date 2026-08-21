import os

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from simplecadapi.artifacts.canonical import sha256_bytes
from simplecadapi.cache.policy import CacheMode, CachePolicy
from simplecadapi.cache.store import CacheLockTimeout, ContentAddressedStore


def _store(tmp_path, **overrides):
    return ContentAddressedStore(
        CachePolicy(
            root=tmp_path / "cache",
            lock_timeout_seconds=overrides.pop("lock_timeout_seconds", 1.0),
            stale_lock_seconds=overrides.pop("stale_lock_seconds", 10.0),
            **overrides,
        )
    )


def test_get_or_compute_deduplicates_concurrent_same_key(tmp_path):
    store = _store(tmp_path)
    key = sha256_bytes(b"same-key")
    calls = 0
    guard = threading.Lock()

    def compute():
        nonlocal calls
        with guard:
            calls += 1
        time.sleep(0.05)
        return b"shared-payload"

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: store.get_or_compute("part", key, compute),
                range(8),
            )
        )

    assert calls == 1
    assert [entry.payload for entry, _ in results] == [b"shared-payload"] * 8
    assert sum(not hit for _, hit in results) == 1
    assert store.stats().objects == 1
    assert store.stats().records == 1
    assert store.stats().locks == 0


def test_different_keys_deduplicate_identical_content_objects(tmp_path):
    store = _store(tmp_path)
    payload = b"content-addressed"

    store.put("part", sha256_bytes(b"key-a"), payload)
    store.put("part", sha256_bytes(b"key-b"), payload)

    assert store.stats().objects == 1
    assert store.stats().records == 2


def test_corrupt_record_is_quarantined_and_becomes_a_miss(tmp_path):
    store = _store(tmp_path)
    key = sha256_bytes(b"corrupt-record")
    store.put("part", key, b"valid")
    record_path = store.record_path("part", key)
    record_path.write_bytes(b'{"truncated":')

    assert store.get("part", key) is None
    assert not record_path.exists()
    assert store.stats().quarantined == 1


def test_corrupt_object_is_quarantined_with_its_record(tmp_path):
    store = _store(tmp_path)
    key = sha256_bytes(b"corrupt-object")
    record = store.put("part", key, b"valid")
    store.object_path(record.object_hash).write_bytes(b"wrong")

    assert store.get("part", key) is None
    assert store.stats().quarantined == 2


def test_stale_lock_is_recovered(tmp_path):
    store = _store(tmp_path, stale_lock_seconds=0.01)
    key = sha256_bytes(b"stale")
    lock = store.lock_path("part", key)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"stale")
    old = time.time() - 60.0
    os.utime(lock, (old, old))


    store.put("part", key, b"recovered")

    assert store.get("part", key).payload == b"recovered"
    assert not lock.exists()


def test_live_lock_times_out_without_overwriting_owner(tmp_path):
    store = _store(tmp_path, lock_timeout_seconds=0.05, stale_lock_seconds=30.0)
    key = sha256_bytes(b"live")

    with store.key_lock("part", key):
        with pytest.raises(CacheLockTimeout):
            with store.key_lock("part", key):
                pass



def test_old_owner_release_does_not_delete_replacement_lock(tmp_path):
    store = _store(
        tmp_path,
        lock_timeout_seconds=1.0,
        stale_lock_seconds=0.01,
    )
    key = sha256_bytes(b"owner-token")
    path = store.lock_path("part", key)
    first_lock = store.key_lock("part", key)
    first_lock.__enter__()

    # Model stale recovery after the original owner became unreachable. A
    # second owner acquires the same pathname while the first context still
    # has its original token and is about to unwind.
    from simplecadapi.artifacts.canonical import canonical_bytes

    path.write_bytes(
        canonical_bytes(
            {"pid": 999_999_999, "token": "dead-owner", "created_ns": "0"}
        )
    )
    old = time.time() - 60.0
    os.utime(path, (old, old))

    replacement_entered = threading.Event()
    release_replacement = threading.Event()

    def hold_replacement():
        with store.key_lock("part", key):
            replacement_entered.set()
            assert release_replacement.wait(timeout=2.0)

    thread = threading.Thread(target=hold_replacement)
    thread.start()
    assert replacement_entered.wait(timeout=2.0)
    replacement_owner = store._read_lock_owner(path)
    assert replacement_owner is not None

    first_lock.__exit__(None, None, None)
    assert path.exists()
    assert store._read_lock_owner(path) == replacement_owner

    release_replacement.set()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    assert not path.exists()


def test_get_or_compute_falls_back_after_lock_timeout(tmp_path):
    store = _store(
        tmp_path,
        lock_timeout_seconds=0.05,
        stale_lock_seconds=30.0,
    )
    key = sha256_bytes(b"timeout-fallback")
    calls = 0

    def compute():
        nonlocal calls
        calls += 1
        return b"independent-payload"

    with store.key_lock("part", key):
        entry, hit = store.get_or_compute("part", key, compute)
        assert store.lock_path("part", key).exists()

    assert not hit
    assert calls == 1
    assert entry.payload == b"independent-payload"
    assert store.get("part", key).payload == b"independent-payload"

def test_cache_modes_gate_reads_and_writes(tmp_path):
    read_write = _store(tmp_path)
    key = sha256_bytes(b"mode")
    read_write.put("part", key, b"payload")

    off = ContentAddressedStore(CachePolicy(mode=CacheMode.OFF, root=read_write.root))
    assert off.get("part", key) is None
    with pytest.raises(PermissionError):
        off.put("part", key, b"new")

    read_only = ContentAddressedStore(
        CachePolicy(mode=CacheMode.READ_ONLY, root=read_write.root)
    )
    assert read_only.get("part", key).payload == b"payload"
    with pytest.raises(PermissionError):
        read_only.put("part", key, b"new")
