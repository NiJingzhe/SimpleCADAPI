"""Shared validation and runtime metadata for semantic CAD values."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional

_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")

class SemanticValueMixin:
    """Runtime metadata hooks shared by non-topological semantic values."""

    _metadata: Dict[str, Any]
    _runtime: Dict[str, Any]

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[str(key)] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(str(key), default)

    def _set_runtime(self, key: str, value: Any) -> None:
        self._runtime[str(key)] = value

    def _get_runtime(self, key: str, default: Any = None) -> Any:
        return self._runtime.get(str(key), default)


def _validate_identifier(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if not _ID_PATTERN.fullmatch(text):
        raise ValueError(
            f"{field_name} must start with a letter and contain only letters, "
            "digits, underscore, dash, dot, or colon"
        )
    return text


def _finite_float(value: Any, *, field_name: str) -> float:
    try:
        result = float(value)
    except Exception as exc:
        raise TypeError(f"{field_name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _optional_float(value: Optional[Any], *, field_name: str) -> Optional[float]:
    if value is None:
        return None
    return _finite_float(value, field_name=field_name)


def _optional_positive_float(value: Optional[Any], *, field_name: str) -> Optional[float]:
    result = _optional_float(value, field_name=field_name)
    if result is not None and result <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return result
