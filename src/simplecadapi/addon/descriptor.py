"""``sca-addon.toml`` descriptor: load, strict validation, typed access.

The descriptor is machine-checked by the ``sca`` CLI only; everything an
agent needs to read lives in the addon's ``SKILL.md``. Validation is
strict and names the offending field and file on every failure —
unknown tables/keys are rejected, not ignored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from . import AddonError
from ._toml import load_toml_document
from .platforms import PLATFORMS
from .versions import VersionRange, VersionSpecError, version_key

DESCRIPTOR_FILENAME = "sca-addon.toml"

RUNTIME_KINDS: tuple[str, ...] = ("binary", "python-env", "docker", "none")
#: Kinds that must declare ``platforms``; docker is abstracted by its
#: engine and ``none`` has no runtime to pin to a host.
PLATFORM_REQUIRED_KINDS = frozenset({"binary", "python-env"})
#: Kinds that must declare ``check_cmd``; for docker it is optional.
CHECK_REQUIRED_KINDS = frozenset({"binary", "python-env"})

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

_ADDON_KEYS = frozenset({"name", "version", "license", "skill_path"})
_COMPAT_KEYS = frozenset({"sca"})
_RUNTIME_KEYS = frozenset({"kind", "platforms", "check_cmd", "check_overrides"})


@dataclass(frozen=True)
class AddonDescriptor:
    """Validated contents of one ``sca-addon.toml``."""

    name: str
    version: str
    license: str
    skill_path: str
    sca_compat: str
    runtime_kind: str
    platforms: tuple[str, ...]
    check_cmd: str | None
    check_overrides: Mapping[str, str]


def descriptor_path(root: Path) -> Path:
    return root / DESCRIPTOR_FILENAME


def _require_table(
    document: Mapping[str, object], key: str, source: Path
) -> Mapping[str, object]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise AddonError(
            f"{source}: missing required table [{key}] — every addon descriptor "
            f"needs [addon], [compat], and [runtime]"
        )
    return value


def _check_keys(table: Mapping[str, object], allowed: frozenset[str], label: str, source: Path) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise AddonError(
            f"{source}: unknown key(s) in [{label}]: {', '.join(unknown)}; "
            f"allowed keys are {', '.join(sorted(allowed))}"
        )


def _require_str(table: Mapping[str, object], key: str, label: str, source: Path) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AddonError(f"{source}: [{label}].{key} must be a non-empty string")
    return value.strip()


def load_descriptor(root: Path) -> AddonDescriptor:
    """Load and validate ``root/sca-addon.toml``; every failure names the file."""
    source = descriptor_path(root)
    if not source.is_file():
        raise AddonError(
            f"{source}: not an addon repository — {DESCRIPTOR_FILENAME} is missing "
            "from the repository root"
        )
    document = load_toml_document(source)
    unknown_tables = sorted(set(document) - {"addon", "compat", "runtime"})
    if unknown_tables:
        raise AddonError(
            f"{source}: unknown table(s) {', '.join(unknown_tables)}; allowed "
            "tables are [addon], [compat], [runtime]"
        )

    addon = _require_table(document, "addon", source)
    compat = _require_table(document, "compat", source)
    runtime = _require_table(document, "runtime", source)
    _check_keys(addon, _ADDON_KEYS, "addon", source)
    _check_keys(compat, _COMPAT_KEYS, "compat", source)
    _check_keys(runtime, _RUNTIME_KEYS, "runtime", source)

    name = _require_str(addon, "name", "addon", source)
    if not _NAME_RE.match(name):
        raise AddonError(
            f"{source}: [addon].name {name!r} must be a lowercase slug matching "
            f"{_NAME_RE.pattern} (it becomes the install directory name)"
        )
    version = _require_str(addon, "version", "addon", source)
    try:
        version_key(version)
    except VersionSpecError as exc:
        raise AddonError(f"{source}: [addon].version: {exc}") from exc
    license_ = _require_str(addon, "license", "addon", source)
    skill_path = _require_str(addon, "skill_path", "addon", source)
    posix = PurePosixPath(skill_path)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise AddonError(
            f"{source}: [addon].skill_path {skill_path!r} must be a relative "
            "POSIX-style directory inside the repository (no leading '/', no '..')"
        )

    sca_compat = _require_str(compat, "sca", "compat", source)
    try:
        VersionRange.parse(sca_compat)
    except VersionSpecError as exc:
        raise AddonError(f"{source}: [compat].sca: {exc}") from exc

    kind = _require_str(runtime, "kind", "runtime", source)
    if kind not in RUNTIME_KINDS:
        raise AddonError(
            f"{source}: [runtime].kind {kind!r} is not one of "
            f"{', '.join(RUNTIME_KINDS)}"
        )

    platforms_value = runtime.get("platforms")
    if kind in PLATFORM_REQUIRED_KINDS:
        if not isinstance(platforms_value, list) or not platforms_value:
            raise AddonError(
                f"{source}: [runtime].platforms must be a non-empty list for "
                f"kind {kind!r} (known platforms: {', '.join(PLATFORMS)})"
            )
        if not all(isinstance(item, str) for item in platforms_value):
            raise AddonError(f"{source}: [runtime].platforms entries must be strings")
        unknown_platforms = sorted(set(platforms_value) - set(PLATFORMS))
        if unknown_platforms:
            raise AddonError(
                f"{source}: [runtime].platforms has unknown value(s) "
                f"{', '.join(unknown_platforms)}; known platforms are "
                f"{', '.join(PLATFORMS)}"
            )
        if len(set(platforms_value)) != len(platforms_value):
            raise AddonError(f"{source}: [runtime].platforms has duplicate entries")
        platforms = tuple(platforms_value)
    else:
        if platforms_value is not None:
            raise AddonError(
                f"{source}: [runtime].platforms must be omitted for kind "
                f"{kind!r} (the runtime is not pinned to a host platform)"
            )
        platforms = ()

    check_cmd_value = runtime.get("check_cmd")
    if kind in CHECK_REQUIRED_KINDS:
        if not isinstance(check_cmd_value, str) or not check_cmd_value.strip():
            raise AddonError(
                f"{source}: [runtime].check_cmd is required for kind {kind!r}: a "
                "fast probe that exits 0 iff the runtime is usable"
            )
        check_cmd: str | None = check_cmd_value.strip()
    elif kind == "none":
        if check_cmd_value is not None:
            raise AddonError(
                f"{source}: [runtime].check_cmd contradicts kind 'none' "
                "(no runtime to probe)"
            )
        check_cmd = None
    else:  # docker: optional
        if check_cmd_value is not None and (
            not isinstance(check_cmd_value, str) or not check_cmd_value.strip()
        ):
            raise AddonError(f"{source}: [runtime].check_cmd must be a non-empty string")
        check_cmd = (
            check_cmd_value.strip()
            if isinstance(check_cmd_value, str)
            else None
        )

    overrides_value = runtime.get("check_overrides")
    overrides: dict[str, str] = {}
    if overrides_value is not None:
        if not isinstance(overrides_value, dict):
            raise AddonError(
                f"{source}: [runtime].check_overrides must be a table mapping "
                f"platform → command (known platforms: {', '.join(PLATFORMS)})"
            )
        if check_cmd is None and overrides_value:
            raise AddonError(
                f"{source}: [runtime].check_overrides requires a default "
                "[runtime].check_cmd to override"
            )
        for key, value in overrides_value.items():
            if key not in PLATFORMS:
                raise AddonError(
                    f"{source}: [runtime].check_overrides key {key!r} is not a "
                    f"known platform ({', '.join(PLATFORMS)})"
                )
            if key not in platforms:
                raise AddonError(
                    f"{source}: [runtime].check_overrides key {key!r} is not in "
                    "[runtime].platforms — overriding a platform the addon does "
                    "not declare is meaningless"
                )
            if not isinstance(value, str) or not value.strip():
                raise AddonError(
                    f"{source}: [runtime].check_overrides[{key!r}] must be a "
                    "non-empty command string"
                )
            overrides[key] = value.strip()

    return AddonDescriptor(
        name=name,
        version=version,
        license=license_,
        skill_path=posix.as_posix(),
        sca_compat=sca_compat,
        runtime_kind=kind,
        platforms=platforms,
        check_cmd=check_cmd,
        check_overrides=overrides,
    )
