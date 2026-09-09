"""Installed-addon registry: ``<addon home>/registry.json``.

The registry is the single source of truth for what ``sca`` installed
and where: ``list`` reads it, ``remove``/``update`` clean up exactly the
paths recorded in it, and skills copied by addons are distinguishable
from hand-written skills because they appear here.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import AddonError

REGISTRY_SCHEMA_VERSION = "1.0"
REGISTRY_FILENAME = "registry.json"

_REQUIRED_RECORD_KEYS = frozenset(
    {
        "name",
        "version",
        "source",
        "addon_relpath",
        "skill_install",
        "runtime",
        "sca_version_at_install",
        "installed_at",
    }
)


def registry_path(home: Path) -> Path:
    return home / REGISTRY_FILENAME


def empty_registry() -> dict[str, Any]:
    return {"schema_version": REGISTRY_SCHEMA_VERSION, "addons": {}}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_registry(home: Path) -> dict[str, Any]:
    """Load the registry, validating shape; missing file yields an empty one."""
    path = registry_path(home)
    if not path.is_file():
        return empty_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AddonError(f"{path}: cannot read addon registry: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise AddonError(
            f"{path}: unrecognized registry schema_version "
            f"{data.get('schema_version')!r} (expected {REGISTRY_SCHEMA_VERSION!r}); "
            "re-run `sca addon init` against a clean home or remove the file"
        )
    addons = data.get("addons")
    if not isinstance(addons, dict):
        raise AddonError(f"{path}: registry 'addons' must be an object")
    for name, record in addons.items():
        if not isinstance(record, dict):
            raise AddonError(f"{path}: registry entry {name!r} must be an object")
        missing = sorted(_REQUIRED_RECORD_KEYS - set(record))
        if missing:
            raise AddonError(
                f"{path}: registry entry {name!r} is missing key(s) "
                f"{', '.join(missing)}; remove the entry or re-initialize"
            )
    return data


def save_registry(home: Path, data: Mapping[str, Any]) -> Path:
    """Atomically write the registry with stable key ordering."""
    path = registry_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
    return path


def get_record(registry: Mapping[str, Any], name: str) -> dict[str, Any] | None:
    record = registry.get("addons", {}).get(name)
    return dict(record) if isinstance(record, dict) else None


def put_record(registry: dict[str, Any], record: Mapping[str, Any]) -> None:
    registry.setdefault("addons", {})[str(record["name"])] = dict(record)


def drop_record(registry: dict[str, Any], name: str) -> None:
    registry.setdefault("addons", {}).pop(name, None)
