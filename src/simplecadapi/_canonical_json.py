"""Small strict/canonical JSON helpers without package-level dependencies."""

from __future__ import annotations

import json
from typing import Any

import rfc8785


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object member: {key!r}")
        result[key] = value
    return result


def _reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {token}")


def canonical_json_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def parse_canonical_json(data: bytes) -> Any:
    text = data.decode("utf-8", errors="strict")
    value = json.loads(
        text,
        object_pairs_hook=_reject_duplicate_pairs,
        parse_constant=_reject_nonfinite,
    )
    if canonical_json_bytes(value) != data:
        raise ValueError("JSON bytes are not RFC 8785 canonical")
    return value


__all__ = ["canonical_json_bytes", "parse_canonical_json"]
