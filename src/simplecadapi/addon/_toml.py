"""TOML reading shared by the addon manager (tomllib with a 3.10 fallback)."""

from __future__ import annotations

from pathlib import Path

from . import AddonError

try:
    import tomllib as _toml  # Python >= 3.11
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 path
    try:
        import tomli as _toml  # type: ignore[no-redef]
    except ModuleNotFoundError as _exc:  # pragma: no cover
        raise AddonError(
            "no TOML parser available: Python 3.10 requires the 'tomli' package"
        ) from _exc


def load_toml_document(path: Path) -> dict:
    """Parse ``path`` as a TOML document, naming the file on any failure."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise AddonError(f"{path}: cannot read file: {exc}") from exc
    try:
        document = _toml.loads(payload.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise AddonError(f"{path}: not valid UTF-8: {exc}") from exc
    except Exception as exc:  # tomllib.TOMLDecodeError and tomli equivalents
        raise AddonError(f"{path}: invalid TOML: {exc}") from exc
    if not isinstance(document, dict):
        raise AddonError(f"{path}: TOML document must be a table")
    return document
