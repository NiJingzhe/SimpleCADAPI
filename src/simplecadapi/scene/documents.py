"""Immutable aggregate boundaries for validated Scene contract documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, ClassVar, Generic, Mapping, TypeVar, cast

from typing_extensions import Self

from .canonical import canonical_json_bytes, parse_canonical_json
from .generated.connector_binding import (
    ConnectorBindingDocument as ConnectorBindingValue,
)
from .generated.entities import EntityDocument as EntityValue
from .generated.normalized_product import (
    NormalizedProductDocument as NormalizedProductValue,
)
from .generated.presentation import PresentationDocument as PresentationValue
from .generated.scene import SceneDocument as SceneValue
from .validation import (
    SceneContractError,
    SceneValidationReport,
    validate_connector_binding,
    validate_entity_asset,
    validate_normalized_product,
    validate_presentation,
    validate_scene_manifest,
)


DocumentValue = TypeVar("DocumentValue")


def _copy_json_value(value: Any, stack: set[int] | None = None) -> Any:
    """Detach JSON-like input while accepting frozen mappings and tuples."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if stack is None:
        stack = set()
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in stack:
            raise ValueError("cyclic value is not JSON")
        stack.add(marker)
        try:
            result: dict[str, Any] = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                result[key] = _copy_json_value(child, stack)
            return result
        finally:
            stack.remove(marker)
    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in stack:
            raise ValueError("cyclic value is not JSON")
        stack.add(marker)
        try:
            return [_copy_json_value(child, stack) for child in value]
        finally:
            stack.remove(marker)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json_value(child) for key, child in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(child) for child in value)
    return value


@dataclass(frozen=True, slots=True, init=False)
class _ContractDocument(Generic[DocumentValue]):
    _value: Mapping[str, Any] = field(repr=False, compare=False)
    _canonical_bytes: bytes = field(repr=False)
    _canonical_hash: str

    _validator: ClassVar[Callable[[Any], SceneValidationReport]]

    def __init__(self, value: DocumentValue | Mapping[str, Any]) -> None:
        copied = _copy_json_value(value)
        canonical = canonical_json_bytes(copied)
        parsed = parse_canonical_json(canonical)
        report = type(self)._validator(parsed)
        if not report.valid:
            raise SceneContractError(report)
        if not isinstance(parsed, dict):  # The schemas require object roots.
            raise TypeError("contract document root must be a JSON object")
        object.__setattr__(self, "_value", _freeze_json_value(parsed))
        object.__setattr__(self, "_canonical_bytes", canonical)
        object.__setattr__(
            self,
            "_canonical_hash",
            "sha256:" + hashlib.sha256(canonical).hexdigest(),
        )

    @classmethod
    def from_value(cls, value: DocumentValue | Mapping[str, Any]) -> Self:
        """Validate and detach a structural contract value."""

        return cls(value)

    @classmethod
    def parse(cls, data: bytes | bytearray | memoryview | str) -> Self:
        """Parse exact canonical JSON bytes, validate them, and freeze the value."""

        return cls(parse_canonical_json(data))

    @property
    def value(self) -> Mapping[str, Any]:
        """The deeply immutable document value."""

        return self._value

    @property
    def canonical_bytes(self) -> bytes:
        return self._canonical_bytes

    @property
    def canonical_hash(self) -> str:
        return self._canonical_hash

    def to_mutable(self) -> DocumentValue:
        """Return a fresh mutable dict/list tree with no aliases to this document."""

        return cast(DocumentValue, parse_canonical_json(self._canonical_bytes))

    def __bytes__(self) -> bytes:
        return self._canonical_bytes


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class SceneDocument(_ContractDocument[SceneValue]):
    _validator: ClassVar[Callable[[Any], SceneValidationReport]] = (
        validate_scene_manifest
    )

    @property
    def revision(self) -> str:
        """The validated two-pass revision carried by this immutable scene."""

        return cast(str, self._value["revision"])


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class EntityDocument(_ContractDocument[EntityValue]):
    _validator: ClassVar[Callable[[Any], SceneValidationReport]] = (
        validate_entity_asset
    )


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class PresentationDocument(_ContractDocument[PresentationValue]):
    _validator: ClassVar[Callable[[Any], SceneValidationReport]] = (
        validate_presentation
    )


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class ConnectorBindingDocument(_ContractDocument[ConnectorBindingValue]):
    _validator: ClassVar[Callable[[Any], SceneValidationReport]] = (
        validate_connector_binding
    )


@dataclass(frozen=True, slots=True, init=False, eq=False, repr=False)
class NormalizedProductDocument(_ContractDocument[NormalizedProductValue]):
    _validator: ClassVar[Callable[[Any], SceneValidationReport]] = (
        validate_normalized_product
    )


__all__ = [
    "ConnectorBindingDocument",
    "EntityDocument",
    "NormalizedProductDocument",
    "PresentationDocument",
    "SceneDocument",
]
