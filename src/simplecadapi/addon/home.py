"""Addon home, skills directory, and ``~/.sca/config.toml`` resolution.

Resolution chain for both locations, most specific first:

1. the ``--home`` / ``--skills-dir`` CLI flag;
2. the ``SCA_ADDON_HOME`` / ``SCA_SKILLS_DIR`` environment variables
   (user-side overrides — the CLI never writes shell profiles);
3. ``~/.sca/config.toml`` (written by ``sca addon init``; its presence
   is the "initialized" marker);
4. platform defaults: ``~/.sca/addons`` and ``~/.agents/skills``.

Every addon command requires an initialized home: the config file must
exist and the resolved home directory must exist.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from . import AddonError
from ._toml import load_toml_document

ENV_ADDON_HOME = "SCA_ADDON_HOME"
ENV_SKILLS_DIR = "SCA_SKILLS_DIR"

_CONFIG_KEYS = frozenset({"addon_home", "skills_dir"})


def default_home() -> Path:
    return Path.home() / ".sca" / "addons"


def default_skills_dir() -> Path:
    return Path.home() / ".agents" / "skills"


def config_path() -> Path:
    return Path.home() / ".sca" / "config.toml"


@dataclass(frozen=True)
class ResolvedPaths:
    """Resolved install locations plus which chain link chose them."""

    home: Path
    skills_dir: Path
    home_source: str
    skills_source: str


def _from_chain(
    flag: Path | None,
    env_name: str,
    config_value: str | None,
    fallback: Path,
) -> tuple[Path, str]:
    if flag is not None:
        return flag.expanduser(), "flag"
    env_value = os.environ.get(env_name)
    if env_value:
        return Path(env_value).expanduser(), f"env {env_name}"
    if config_value:
        return Path(config_value).expanduser(), "config"
    return fallback, "default"


def read_config() -> dict[str, str]:
    """Read ``~/.sca/config.toml``; missing file means not initialized."""
    path = config_path()
    if not path.is_file():
        return {}
    document = load_toml_document(path)
    unknown = sorted(set(document) - _CONFIG_KEYS)
    if unknown:
        raise AddonError(
            f"{path}: unknown config key(s) {', '.join(unknown)}; allowed keys "
            f"are {', '.join(sorted(_CONFIG_KEYS))}"
        )
    config: dict[str, str] = {}
    for key in _CONFIG_KEYS:
        value = document.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise AddonError(f"{path}: config key {key!r} must be a non-empty path string")
        config[key] = value.strip()
    return config


def resolve_paths(
    *, home: Path | None = None, skills_dir: Path | None = None
) -> ResolvedPaths:
    """Resolve home and skills dir through the precedence chain."""
    config = read_config()
    home_path, home_source = _from_chain(home, ENV_ADDON_HOME, config.get("addon_home"), default_home())
    skills_path, skills_source = _from_chain(
        skills_dir, ENV_SKILLS_DIR, config.get("skills_dir"), default_skills_dir()
    )
    return ResolvedPaths(
        home=home_path,
        skills_dir=skills_path,
        home_source=home_source,
        skills_source=skills_source,
    )


def require_initialized(resolved: ResolvedPaths) -> None:
    """Fail with actionable guidance unless ``sca addon init`` has run."""
    if not config_path().is_file() or not resolved.home.is_dir():
        raise AddonError(
            "addon home is not initialized "
            f"(home={resolved.home} via {resolved.home_source}; "
            f"config={config_path()}); run `sca addon init` first"
        )


def init_home(resolved: ResolvedPaths) -> dict[str, str]:
    """Create the home, registry skeleton, and config; idempotent.

    Re-running against an existing home preserves its registry. The
    config always records the locations resolved at init time; the
    ``SCA_ADDON_HOME`` / ``SCA_SKILLS_DIR`` environment variables remain
    live overrides that outrank the config.
    """
    from .registry import REGISTRY_FILENAME, empty_registry, load_registry, save_registry

    created = not resolved.home.is_dir()
    resolved.home.mkdir(parents=True, exist_ok=True)
    resolved.skills_dir.mkdir(parents=True, exist_ok=True)
    registry_state = "created"
    if (resolved.home / REGISTRY_FILENAME).is_file():
        load_registry(resolved.home)  # validate; named failure on corruption
        registry_state = "preserved"
    else:
        save_registry(resolved.home, empty_registry())
    write_config(resolved)
    return {
        "home": str(resolved.home),
        "skills_dir": str(resolved.skills_dir),
        "config": str(config_path()),
        "registry": registry_state,
        "created": "yes" if created else "no",
    }


def write_config(resolved: ResolvedPaths) -> Path:
    """Write ``~/.sca/config.toml`` with the resolved locations."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    def _quote(value: Path) -> str:
        return json.dumps(str(value))

    text = (
        "# Written by `sca addon init`. The environment variables\n"
        f"# {ENV_ADDON_HOME} and {ENV_SKILLS_DIR} override these values at any time.\n"
        f"addon_home = {_quote(resolved.home)}\n"
        f"skills_dir = {_quote(resolved.skills_dir)}\n"
    )
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return path
