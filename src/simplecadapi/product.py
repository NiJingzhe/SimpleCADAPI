"""Product-level semantic values for SimpleCAD Part and Assembly workflows."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple, Union

from .core import Solid


Vec3 = Tuple[float, float, float]
_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_AXIS_TOLERANCE = 1e-9
_ORTHOGONAL_TOLERANCE = 1e-7


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


def _vec3(value: Any, *, field_name: str) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field_name} must be a 3-element tuple or list")
    return (
        _finite_float(value[0], field_name=f"{field_name}[0]"),
        _finite_float(value[1], field_name=f"{field_name}[1]"),
        _finite_float(value[2], field_name=f"{field_name}[2]"),
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(value: Vec3) -> float:
    return math.sqrt(_dot(value, value))


def _normalize_axis(value: Any, *, field_name: str) -> Vec3:
    vec = _vec3(value, field_name=field_name)
    length = _norm(vec)
    if length <= _AXIS_TOLERANCE:
        raise ValueError(f"{field_name} must be a non-zero vector")
    return (vec[0] / length, vec[1] / length, vec[2] / length)


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


@dataclass(frozen=True)
class Placement(SemanticValueMixin):
    """Right-handed placement mapping child-local coordinates to parent coordinates."""

    origin: Vec3
    x_axis: Vec3 = (1.0, 0.0, 0.0)
    y_axis: Vec3 = (0.0, 1.0, 0.0)
    z_axis: Vec3 = (0.0, 0.0, 1.0)
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        origin = _vec3(self.origin, field_name="origin")
        x_axis = _normalize_axis(self.x_axis, field_name="x_axis")
        y_axis = _normalize_axis(self.y_axis, field_name="y_axis")
        dot = abs(_dot(x_axis, y_axis))
        if dot > _ORTHOGONAL_TOLERANCE:
            raise ValueError("x_axis and y_axis must be orthogonal")
        z_axis = _cross(x_axis, y_axis)
        z_norm = _norm(z_axis)
        if z_norm <= _AXIS_TOLERANCE:
            raise ValueError("x_axis and y_axis must define a right-handed frame")
        z_axis = (z_axis[0] / z_norm, z_axis[1] / z_norm, z_axis[2] / z_norm)
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)
        object.__setattr__(self, "z_axis", z_axis)

    def transform_point(self, point: Vec3) -> Vec3:
        local = _vec3(point, field_name="point")
        return (
            self.origin[0]
            + local[0] * self.x_axis[0]
            + local[1] * self.y_axis[0]
            + local[2] * self.z_axis[0],
            self.origin[1]
            + local[0] * self.x_axis[1]
            + local[1] * self.y_axis[1]
            + local[2] * self.z_axis[1],
            self.origin[2]
            + local[0] * self.x_axis[2]
            + local[1] * self.y_axis[2]
            + local[2] * self.z_axis[2],
        )

    def transform_vector(self, vector: Vec3) -> Vec3:
        local = _vec3(vector, field_name="vector")
        return (
            local[0] * self.x_axis[0]
            + local[1] * self.y_axis[0]
            + local[2] * self.z_axis[0],
            local[0] * self.x_axis[1]
            + local[1] * self.y_axis[1]
            + local[2] * self.z_axis[1],
            local[0] * self.x_axis[2]
            + local[1] * self.y_axis[2]
            + local[2] * self.z_axis[2],
        )

    def compose(self, child: "Placement") -> "Placement":
        if not isinstance(child, Placement):
            raise TypeError("child must be a Placement")
        return Placement(
            origin=self.transform_point(child.origin),
            x_axis=self.transform_vector(child.x_axis),
            y_axis=self.transform_vector(child.y_axis),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": list(self.origin),
            "x_axis": list(self.x_axis),
            "y_axis": list(self.y_axis),
            "z_axis": list(self.z_axis),
        }


@dataclass(frozen=True)
class Part(SemanticValueMixin):
    """Single-body product item wrapping exactly one Solid."""

    part_id: str
    body: Solid
    name: Optional[str] = None
    material: Optional[Material] = None
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

    def with_material(self, material: Material) -> "Part":
        if not isinstance(material, Material):
            raise TypeError("material must be a Material")
        return Part(
            self.part_id,
            self.body,
            name=self.name,
            material=material,
            _metadata=dict(self._metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "part_id": self.part_id,
            "name": self.name,
            "material": self.material.to_dict() if self.material is not None else None,
        }


AssemblyItem = Union[Part, "Assembly"]


@dataclass(frozen=True)
class Component:
    """Assembly-local instance of a Part or subassembly."""

    component_id: str
    item: AssemblyItem
    placement: Placement
    name: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "component_id",
            _validate_identifier(self.component_id, field_name="component_id"),
        )
        if not isinstance(self.item, (Part, Assembly)):
            raise TypeError("item must be a Part or Assembly")
        if not isinstance(self.placement, Placement):
            raise TypeError("placement must be a Placement")
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)

    def to_dict(self) -> Dict[str, Any]:
        item_kind = "assembly" if isinstance(self.item, Assembly) else "part"
        item_id = self.item.assembly_id if isinstance(self.item, Assembly) else self.item.part_id
        return {
            "component_id": self.component_id,
            "name": self.name,
            "item_kind": item_kind,
            "item_id": item_id,
            "placement": self.placement.to_dict(),
        }


@dataclass(frozen=True)
class Assembly(SemanticValueMixin):
    """Product structure containing placed Part or subassembly components."""

    assembly_id: str
    name: Optional[str] = None
    components: Tuple[Component, ...] = ()
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assembly_id",
            _validate_identifier(self.assembly_id, field_name="assembly_id"),
        )
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)
        ids = [component.component_id for component in self.components]
        duplicates = sorted({component_id for component_id in ids if ids.count(component_id) > 1})
        if duplicates:
            raise ValueError("duplicate component_id in assembly: " + ", ".join(duplicates))

    def component_ids(self) -> Tuple[str, ...]:
        return tuple(component.component_id for component in self.components)

    def get_component(self, component_id: str) -> Component:
        target = _validate_identifier(component_id, field_name="component_id")
        for component in self.components:
            if component.component_id == target:
                return component
        raise KeyError(f"assembly has no component_id '{target}'")

    def with_component(self, component: Component) -> "Assembly":
        if not isinstance(component, Component):
            raise TypeError("component must be a Component")
        if component.component_id in self.component_ids():
            raise ValueError(f"duplicate component_id in assembly: {component.component_id}")
        if isinstance(component.item, Assembly):
            _assert_no_assembly_cycle(self, component.item)
        return Assembly(
            self.assembly_id,
            name=self.name,
            components=(*self.components, component),
            _metadata=dict(self._metadata),
        )

    def with_component_placement(
        self, component_id: str, placement: Placement
    ) -> "Assembly":
        if not isinstance(placement, Placement):
            raise TypeError("placement must be a Placement")
        target = _validate_identifier(component_id, field_name="component_id")
        found = False
        components = []
        for component in self.components:
            if component.component_id == target:
                found = True
                components.append(
                    Component(
                        component.component_id,
                        component.item,
                        placement,
                        name=component.name,
                    )
                )
            else:
                components.append(component)
        if not found:
            raise KeyError(f"assembly has no component_id '{target}'")
        return Assembly(
            self.assembly_id,
            name=self.name,
            components=tuple(components),
            _metadata=dict(self._metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assembly_id": self.assembly_id,
            "name": self.name,
            "components": [component.to_dict() for component in self.components],
        }


def identity_placement() -> Placement:
    return Placement((0.0, 0.0, 0.0))


def compose_placements(parent: Placement, child: Placement) -> Placement:
    if not isinstance(parent, Placement):
        raise TypeError("parent must be a Placement")
    return parent.compose(child)


def _assert_no_assembly_cycle(parent: Assembly, child: Assembly) -> None:
    if child.assembly_id == parent.assembly_id:
        raise ValueError(f"assembly cycle detected for '{parent.assembly_id}'")
    for component in child.components:
        if isinstance(component.item, Assembly):
            _assert_no_assembly_cycle(parent, component.item)


__all__ = [
    "Assembly",
    "Component",
    "Material",
    "Part",
    "Placement",
    "compose_placements",
    "identity_placement",
]
