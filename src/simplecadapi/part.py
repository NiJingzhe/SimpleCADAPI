"""Single-body part semantic values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from ._semantic import SemanticValueMixin, _validate_identifier
from .connector import (
    Connector,
    _validate_connectors,
    _validate_part_connector_anchors,
)
from .core import Solid
from .material import Material

@dataclass(frozen=True)
class Part(SemanticValueMixin):
    """Single-body product item wrapping exactly one Solid."""

    part_id: str
    body: Solid
    name: Optional[str] = None
    material: Optional[Material] = None
    connectors: Tuple[Connector, ...] = ()
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "part_id",
            _validate_identifier(self.part_id, field_name="part_id"),
        )
        if not isinstance(self.body, Solid):
            raise TypeError("body must be a Solid")
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)
        if self.material is not None and not isinstance(self.material, Material):
            raise TypeError("material must be a Material")
        connectors = _validate_connectors(self.connectors)
        _validate_part_connector_anchors(connectors)
        object.__setattr__(self, "connectors", connectors)

    def with_material(self, material: Material) -> "Part":
        if not isinstance(material, Material):
            raise TypeError("material must be a Material")
        return Part(
            self.part_id,
            self.body,
            name=self.name,
            material=material,
            connectors=self.connectors,
            _metadata=dict(self._metadata),
        )

    def connector_ids(self) -> Tuple[str, ...]:
        return tuple(connector.connector_id for connector in self.connectors)

    def get_connector(self, connector_id: str) -> Connector:
        target = _validate_identifier(connector_id, field_name="connector_id")
        for connector in self.connectors:
            if connector.connector_id == target:
                return connector
        raise KeyError(f"part has no connector_id '{target}'")

    def with_connector(self, connector: Connector) -> "Part":
        if not isinstance(connector, Connector):
            raise TypeError("connector must be a Connector")
        if connector.connector_id in self.connector_ids():
            raise ValueError(f"duplicate connector_id in part: {connector.connector_id}")
        return Part(
            self.part_id,
            self.body,
            name=self.name,
            material=self.material,
            connectors=(*self.connectors, connector),
            _metadata=dict(self._metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "part_id": self.part_id,
            "name": self.name,
            "material": self.material.to_dict() if self.material is not None else None,
            "connectors": [connector.to_dict() for connector in self.connectors],
        }


__all__ = ["Part"]
