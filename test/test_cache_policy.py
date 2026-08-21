from pathlib import Path

import pytest

from simplecadapi.cache.policy import CacheMode, CachePolicy, resolve_cache_policy


def test_cache_policy_precedence_is_explicit_env_project_defaults(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.simplecadapi.cache]
mode = "read_only"
root = "project-cache"
verify_reads = false
lock_timeout_seconds = 12
""".strip(),
        encoding="utf-8",
    )
    environment = {
        "SIMPLECAD_CACHE_MODE": "refresh",
        "SIMPLECAD_CACHE_DIR": "env-cache",
        "SIMPLECAD_CACHE_VERIFY_READS": "true",
    }

    policy = resolve_cache_policy(
        {"mode": "read_write", "lock_timeout_seconds": 3},
        project_root=tmp_path,
        environ=environment,
    )

    assert policy.mode is CacheMode.READ_WRITE
    assert policy.root == (tmp_path / "env-cache").resolve()
    assert policy.verify_reads is True
    assert policy.lock_timeout_seconds == 3
    assert policy.stale_lock_seconds == 300


def test_cache_policy_resolves_relative_root_against_project(tmp_path):
    policy = resolve_cache_policy(project_root=tmp_path, environ={})

    assert policy.root == (tmp_path / ".simplecad/cache").resolve()


def test_cache_policy_rejects_unknown_fields_and_invalid_booleans(tmp_path):
    with pytest.raises(ValueError, match="unknown"):
        resolve_cache_policy({"surprise": True}, project_root=tmp_path, environ={})
    with pytest.raises(ValueError, match="boolean"):
        resolve_cache_policy(
            project_root=tmp_path,
            environ={"SIMPLECAD_CACHE_VERIFY_READS": "sometimes"},
        )
