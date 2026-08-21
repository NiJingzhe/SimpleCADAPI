"""Material semantic values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from ._semantic import SemanticValueMixin, _finite_float, _validate_identifier
from .placement import Vec3, _vec3

def _validate_color(value: Optional[Tuple[float, float, float]]) -> Optional[Vec3]:
    if value is None:
        return None
    color = _vec3(value, field_name="color")
    if any(component < 0.0 or component > 1.0 for component in color):
        raise ValueError("color components must be in [0.0, 1.0]")
    return color


@dataclass(frozen=True)
class Material(SemanticValueMixin):
    """Material definition assigned to a Part through `assign_material_rpart`."""

    material_id: str
    name: Optional[str] = None
    density: Optional[float] = None
    density_unit: Optional[str] = None
    color: Optional[Vec3] = None
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "material_id",
            _validate_identifier(self.material_id, field_name="material_id"),
        )
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)
        if self.density is not None:
            density = _finite_float(self.density, field_name="density")
            if density <= 0.0:
                raise ValueError("density must be positive when provided")
            object.__setattr__(self, "density", density)
            if not isinstance(self.density_unit, str) or not self.density_unit.strip():
                raise ValueError("density_unit must be explicit when density is provided")
            object.__setattr__(self, "density_unit", self.density_unit.strip())
        elif self.density_unit is not None:
            raise ValueError("density_unit requires density")
        object.__setattr__(self, "color", _validate_color(self.color))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "material_id": self.material_id,
            "name": self.name,
            "density": self.density,
            "density_unit": self.density_unit,
            "color": list(self.color) if self.color is not None else None,
        }


__all__ = ["Material"]
