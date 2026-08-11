"""Unified cache policy resolution with explicit, environment, project, default precedence."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib  # type: ignore[no-redef]


class CacheMode(str, Enum):
    """Persistent cache read/write mode."""
    OFF = "off"
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class CachePolicy:
    """Resolved persistent cache location, integrity, and locking policy."""
    mode: CacheMode = CacheMode.READ_WRITE
    root: Path = Path(".simplecad/cache")
    verify_reads: bool = True
    quarantine_corrupt: bool = True
    lock_timeout_seconds: float = 30.0
    stale_lock_seconds: float = 300.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "mode", CacheMode(self.mode))
        object.__setattr__(self, "root", Path(self.root).expanduser())
        for name in ("lock_timeout_seconds", "stale_lock_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{name} must be a positive number")
        if not isinstance(self.verify_reads, bool) or not isinstance(self.quarantine_corrupt, bool):
            raise TypeError("verify_reads and quarantine_corrupt must be booleans")

    @property
    def can_read(self) -> bool:
        return self.mode in {CacheMode.READ_ONLY, CacheMode.READ_WRITE}

    @property
    def can_write(self) -> bool:
        return self.mode in {CacheMode.READ_WRITE, CacheMode.REFRESH}


_DEFAULTS: dict[str, Any] = {
    "mode": CacheMode.READ_WRITE.value,
    "root": ".simplecad/cache",
    "verify_reads": True,
    "quarantine_corrupt": True,
    "lock_timeout_seconds": 30.0,
    "stale_lock_seconds": 300.0,
}
_ENV_FIELDS = {
    "SIMPLECAD_CACHE_MODE": "mode",
    "SIMPLECAD_CACHE_DIR": "root",
    "SIMPLECAD_CACHE_VERIFY_READS": "verify_reads",
    "SIMPLECAD_CACHE_QUARANTINE_CORRUPT": "quarantine_corrupt",
    "SIMPLECAD_CACHE_LOCK_TIMEOUT": "lock_timeout_seconds",
    "SIMPLECAD_CACHE_STALE_LOCK": "stale_lock_seconds",
}


def _bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    if isinstance(value, str) and value.strip().lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{field} must be a boolean")


def _normalize(values: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(values) - set(_DEFAULTS)
    if unknown:
        raise ValueError("unknown cache policy fields: " + ", ".join(sorted(unknown)))
    result = dict(values)
    if "mode" in result:
        result["mode"] = CacheMode(result["mode"])
    if "root" in result:
        result["root"] = Path(result["root"]).expanduser()
    for field in ("verify_reads", "quarantine_corrupt"):
        if field in result:
            result[field] = _bool(result[field], field)
    for field in ("lock_timeout_seconds", "stale_lock_seconds"):
        if field in result:
            result[field] = float(result[field])
    return result


def _project_values(project_root: Path) -> Mapping[str, Any]:
    config = project_root / "pyproject.toml"
    if not config.is_file():
        return {}
    with config.open("rb") as stream:
        parsed = tomllib.load(stream)
    tool = parsed.get("tool", {})
    simplecad = tool.get("simplecadapi", {}) if isinstance(tool, Mapping) else {}
    cache = simplecad.get("cache", {}) if isinstance(simplecad, Mapping) else {}
    if not isinstance(cache, Mapping):
        raise ValueError("[tool.simplecadapi.cache] must be a TOML table")
    return cache


def resolve_cache_policy(
    explicit: CachePolicy | Mapping[str, Any] | None = None,
    *,
    project_root: str | Path = ".",
    environ: Mapping[str, str] | None = None,
) -> CachePolicy:
    """Resolve fields using explicit > environment > project > defaults."""

    root = Path(project_root).expanduser().resolve()
    values: dict[str, Any] = dict(_DEFAULTS)
    values.update(_normalize(_project_values(root)))
    environment = os.environ if environ is None else environ
    env_values = {
        field: environment[name]
        for name, field in _ENV_FIELDS.items()
        if name in environment and environment[name] != ""
    }
    values.update(_normalize(env_values))
    if isinstance(explicit, CachePolicy):
        values.update(
            {
                "mode": explicit.mode,
                "root": explicit.root,
                "verify_reads": explicit.verify_reads,
                "quarantine_corrupt": explicit.quarantine_corrupt,
                "lock_timeout_seconds": explicit.lock_timeout_seconds,
                "stale_lock_seconds": explicit.stale_lock_seconds,
            }
        )
    elif explicit is not None:
        values.update(_normalize(explicit))
    policy = CachePolicy(**values)
    policy_root = policy.root if policy.root.is_absolute() else root / policy.root
    return replace(policy, root=policy_root.resolve())


__all__ = ["CacheMode", "CachePolicy", "resolve_cache_policy"]
