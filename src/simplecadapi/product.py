"""Product-level semantic values for SimpleCAD Part and Assembly workflows."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .core import Solid


Vec3 = Tuple[float, float, float]
_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
_AXIS_TOLERANCE = 1e-9
_ORTHOGONAL_TOLERANCE = 1e-7
_PLACEMENT_TOLERANCE = 1e-7
_ANGLE_TOLERANCE_DEGREES = 1e-6


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
class GeometryRef(SemanticValueMixin):
    """Serializable reference to a sub-shape selected via QL.

    Wraps the geo_selector fingerprint + source graph node id so the
    exact sub-element (Face/Edge/Vertex) can be re-resolved at translation
    time or during constraint solving. When flip is True, the derived
    placement Z axis is negated.
    """

    kind: str
    source_node_id: Optional[str]
    geo_selector: Dict[str, Any]
    flip: bool = False
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        kind = str(self.kind).strip().lower()
        if kind not in {"vertex", "edge", "wire", "face", "solid"}:
            raise ValueError(
                "kind must be one of: vertex, edge, wire, face, solid"
            )
        object.__setattr__(self, "kind", kind)
        if not isinstance(self.geo_selector, dict):
            raise TypeError("geo_selector must be a dict")
        if self.source_node_id is not None:
            object.__setattr__(self, "source_node_id", str(self.source_node_id))
        object.__setattr__(self, "flip", bool(self.flip))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "source_node_id": self.source_node_id,
            "geo_selector": dict(self.geo_selector),
            "flip": self.flip,
        }


@dataclass(frozen=True)
class Connector(SemanticValueMixin):
    """Semantic datum frame anchored to a geometry sub-element (Face/Edge/Vertex).

    The connector wraps a QL-selected sub-shape.  The Placement is derived
    from the geometry at solve/translate time, not stored directly.
    """

    connector_id: str
    geometry_ref: GeometryRef
    name: Optional[str] = None
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "connector_id",
            _validate_identifier(self.connector_id, field_name="connector_id"),
        )
        if not isinstance(self.geometry_ref, GeometryRef):
            raise TypeError("geometry_ref must be a GeometryRef")
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)

    @property
    def placement(self) -> Placement:
        """Lazily-computed Placement derived from the geometry_ref."""
        return _placement_from_geometry_ref(self.geometry_ref)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "name": self.name,
            "geometry_ref": self.geometry_ref.to_dict(),
        }


@dataclass(frozen=True)
class ConnectorRef(SemanticValueMixin):
    """Reference to a connector through a component instance."""

    component_id: str
    connector_id: str
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "component_id",
            _validate_identifier(self.component_id, field_name="component_id"),
        )
        object.__setattr__(
            self,
            "connector_id",
            _validate_identifier(self.connector_id, field_name="connector_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "connector_id": self.connector_id,
        }


@dataclass(frozen=True)
class ScalarLimit(SemanticValueMixin):
    """Closed scalar range for a constraint drive coordinate."""

    lower_value: float
    upper_value: float
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        lower = _finite_float(self.lower_value, field_name="lower_value")
        upper = _finite_float(self.upper_value, field_name="upper_value")
        if lower > upper:
            raise ValueError("lower_value must be less than or equal to upper_value")
        object.__setattr__(self, "lower_value", lower)
        object.__setattr__(self, "upper_value", upper)

    def contains(self, value: float) -> bool:
        scalar = _finite_float(value, field_name="value")
        return self.lower_value <= scalar <= self.upper_value

    def to_dict(self) -> Dict[str, Any]:
        return {"lower_value": self.lower_value, "upper_value": self.upper_value}


ConstraintKind = str


@dataclass(frozen=True)
class Constraint(SemanticValueMixin):
    """Connector-to-connector assembly constraint."""

    constraint_id: str
    constraint_kind: ConstraintKind
    connector_a: ConnectorRef
    connector_b: ConnectorRef
    drive_distance: Optional[float] = None
    distance_limit: Optional[ScalarLimit] = None
    drive_angle_degrees: Optional[float] = None
    angle_limit: Optional[ScalarLimit] = None
    name: Optional[str] = None
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "constraint_id",
            _validate_identifier(self.constraint_id, field_name="constraint_id"),
        )
        kind = str(self.constraint_kind).strip().lower()
        if kind not in {"fixed", "revolute", "prismatic"}:
            raise ValueError("constraint_kind must be fixed, revolute, or prismatic")
        object.__setattr__(self, "constraint_kind", kind)
        if not isinstance(self.connector_a, ConnectorRef):
            raise TypeError("connector_a must be a ConnectorRef")
        if not isinstance(self.connector_b, ConnectorRef):
            raise TypeError("connector_b must be a ConnectorRef")
        if self.connector_a == self.connector_b:
            raise ValueError("constraint cannot connect the same connector ref twice")
        drive_distance = _optional_float(self.drive_distance, field_name="drive_distance")
        drive_angle = _optional_float(
            self.drive_angle_degrees, field_name="drive_angle_degrees"
        )
        if self.distance_limit is not None and not isinstance(self.distance_limit, ScalarLimit):
            raise TypeError("distance_limit must be a ScalarLimit")
        if self.angle_limit is not None and not isinstance(self.angle_limit, ScalarLimit):
            raise TypeError("angle_limit must be a ScalarLimit")
        if kind == "fixed":
            if drive_distance is not None or drive_angle is not None:
                raise ValueError("fixed constraints do not accept drive scalars")
            if self.distance_limit is not None or self.angle_limit is not None:
                raise ValueError("fixed constraints do not accept scalar limits")
        if kind == "revolute":
            if drive_distance is not None or self.distance_limit is not None:
                raise ValueError("revolute constraints only accept angle scalars")
        if kind == "prismatic":
            if drive_angle is not None or self.angle_limit is not None:
                raise ValueError("prismatic constraints only accept distance scalars")
        object.__setattr__(self, "drive_distance", drive_distance)
        object.__setattr__(self, "drive_angle_degrees", drive_angle)
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "constraint_kind": self.constraint_kind,
            "connector_a": self.connector_a.to_dict(),
            "connector_b": self.connector_b.to_dict(),
            "drive_distance": self.drive_distance,
            "distance_limit": self.distance_limit.to_dict() if self.distance_limit else None,
            "drive_angle_degrees": self.drive_angle_degrees,
            "angle_limit": self.angle_limit.to_dict() if self.angle_limit else None,
            "name": self.name,
        }


@dataclass(frozen=True)
class ConstraintResidual:
    """Residual for a single assembly constraint."""

    constraint_id: str
    translation_error: float
    angular_error_degrees: float
    within_tolerance: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "translation_error": self.translation_error,
            "angular_error_degrees": self.angular_error_degrees,
            "within_tolerance": self.within_tolerance,
        }


@dataclass(frozen=True)
class ConstraintReport:
    """Assembly constraint inspection report."""

    solved: bool
    grounded_component_ids: Tuple[str, ...]
    solved_component_ids: Tuple[str, ...]
    unsolved_component_ids: Tuple[str, ...]
    residuals: Tuple[ConstraintResidual, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "solved": self.solved,
            "grounded_component_ids": list(self.grounded_component_ids),
            "solved_component_ids": list(self.solved_component_ids),
            "unsolved_component_ids": list(self.unsolved_component_ids),
            "residuals": [residual.to_dict() for residual in self.residuals],
        }


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
    connectors: Tuple[Connector, ...] = ()
    constraints: Tuple[Constraint, ...] = ()
    grounded_component_ids: Tuple[str, ...] = ()
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
        object.__setattr__(self, "connectors", _validate_connectors(self.connectors))
        constraints = _validate_constraints(self.constraints)
        object.__setattr__(self, "constraints", constraints)
        for constraint in constraints:
            _validate_constraint_refs(self, constraint)
        grounded = tuple(
            _validate_identifier(component_id, field_name="component_id")
            for component_id in self.grounded_component_ids
        )
        unknown_grounded = sorted(set(grounded) - set(ids))
        if unknown_grounded:
            raise ValueError(
                "grounded component_id not found in assembly: " + ", ".join(unknown_grounded)
            )
        object.__setattr__(self, "grounded_component_ids", tuple(dict.fromkeys(grounded)))

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
            connectors=self.connectors,
            constraints=self.constraints,
            grounded_component_ids=self.grounded_component_ids,
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
            connectors=self.connectors,
            constraints=self.constraints,
            grounded_component_ids=self.grounded_component_ids,
            _metadata=dict(self._metadata),
        )

    def connector_ids(self) -> Tuple[str, ...]:
        return tuple(connector.connector_id for connector in self.connectors)

    def get_connector(self, connector_id: str) -> Connector:
        target = _validate_identifier(connector_id, field_name="connector_id")
        for connector in self.connectors:
            if connector.connector_id == target:
                return connector
        raise KeyError(f"assembly has no connector_id '{target}'")

    def with_connector(self, connector: Connector) -> "Assembly":
        if not isinstance(connector, Connector):
            raise TypeError("connector must be a Connector")
        if connector.connector_id in self.connector_ids():
            raise ValueError(f"duplicate connector_id in assembly: {connector.connector_id}")
        return Assembly(
            self.assembly_id,
            name=self.name,
            components=self.components,
            connectors=(*self.connectors, connector),
            constraints=self.constraints,
            grounded_component_ids=self.grounded_component_ids,
            _metadata=dict(self._metadata),
        )

    def constraint_ids(self) -> Tuple[str, ...]:
        return tuple(constraint.constraint_id for constraint in self.constraints)

    def get_constraint(self, constraint_id: str) -> Constraint:
        target = _validate_identifier(constraint_id, field_name="constraint_id")
        for constraint in self.constraints:
            if constraint.constraint_id == target:
                return constraint
        raise KeyError(f"assembly has no constraint_id '{target}'")

    def with_constraint(self, constraint: Constraint) -> "Assembly":
        if not isinstance(constraint, Constraint):
            raise TypeError("constraint must be a Constraint")
        if constraint.constraint_id in self.constraint_ids():
            raise ValueError(f"duplicate constraint_id in assembly: {constraint.constraint_id}")
        _validate_constraint_refs(self, constraint)
        return Assembly(
            self.assembly_id,
            name=self.name,
            components=self.components,
            connectors=self.connectors,
            constraints=(*self.constraints, constraint),
            grounded_component_ids=self.grounded_component_ids,
            _metadata=dict(self._metadata),
        )

    def with_grounded_component(self, component_id: str) -> "Assembly":
        target = _validate_identifier(component_id, field_name="component_id")
        self.get_component(target)
        if target in self.grounded_component_ids:
            return self
        return Assembly(
            self.assembly_id,
            name=self.name,
            components=self.components,
            connectors=self.connectors,
            constraints=self.constraints,
            grounded_component_ids=(*self.grounded_component_ids, target),
            _metadata=dict(self._metadata),
        )

    def without_grounded_component(self, component_id: str) -> "Assembly":
        target = _validate_identifier(component_id, field_name="component_id")
        self.get_component(target)
        grounded = tuple(
            existing for existing in self.grounded_component_ids if existing != target
        )
        return Assembly(
            self.assembly_id,
            name=self.name,
            components=self.components,
            connectors=self.connectors,
            constraints=self.constraints,
            grounded_component_ids=grounded,
            _metadata=dict(self._metadata),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assembly_id": self.assembly_id,
            "name": self.name,
            "components": [component.to_dict() for component in self.components],
            "connectors": [connector.to_dict() for connector in self.connectors],
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "grounded_component_ids": list(self.grounded_component_ids),
        }


def identity_placement() -> Placement:
    return Placement((0.0, 0.0, 0.0))


def compose_placements(parent: Placement, child: Placement) -> Placement:
    if not isinstance(parent, Placement):
        raise TypeError("parent must be a Placement")
    return parent.compose(child)


def inverse_placement(placement: Placement) -> Placement:
    if not isinstance(placement, Placement):
        raise TypeError("placement must be a Placement")
    origin = placement.origin
    x_axis = placement.x_axis
    y_axis = placement.y_axis
    z_axis = placement.z_axis
    return Placement(
        origin=(-_dot(origin, x_axis), -_dot(origin, y_axis), -_dot(origin, z_axis)),
        x_axis=(x_axis[0], y_axis[0], z_axis[0]),
        y_axis=(x_axis[1], y_axis[1], z_axis[1]),
    )


def relative_placement(base: Placement, target: Placement) -> Placement:
    return inverse_placement(base).compose(target)


def rotate_z_placement(angle_degrees: float) -> Placement:
    angle = math.radians(_finite_float(angle_degrees, field_name="angle_degrees"))
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return Placement((0.0, 0.0, 0.0), x_axis=(cos_a, sin_a, 0.0), y_axis=(-sin_a, cos_a, 0.0))


def translate_z_placement(distance: float) -> Placement:
    return Placement((0.0, 0.0, _finite_float(distance, field_name="distance")))


def solve_assembly_constraints(assembly: Assembly, strict: bool = True) -> Assembly:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    if not assembly.constraints:
        return assembly
    if not assembly.grounded_component_ids:
        raise ValueError("assembly constraints require at least one grounded component")
    solved: Dict[str, Placement] = {
        component_id: assembly.get_component(component_id).placement
        for component_id in assembly.grounded_component_ids
    }

    pending = list(assembly.constraints)
    progressed = True
    while pending and progressed:
        progressed = False
        remaining: List[Constraint] = []
        for constraint in pending:
            a_id = constraint.connector_a.component_id
            b_id = constraint.connector_b.component_id
            if a_id in solved and b_id not in solved:
                bounds = _constraint_scalar_bounds(constraint)
                if constraint.constraint_kind == "revolute" and constraint.drive_angle_degrees is not None:
                    scalar = _project_scalar(constraint.drive_angle_degrees, bounds)
                elif constraint.constraint_kind == "prismatic" and constraint.drive_distance is not None:
                    scalar = _project_scalar(constraint.drive_distance, bounds)
                elif bounds is not None:
                    scalar = _project_scalar(
                        _constraint_current_scalar(assembly, constraint), bounds
                    )
                else:
                    scalar = None
                solved[b_id] = _solve_other_component(
                    assembly, constraint,
                    known_side="a", known_placement=solved[a_id],
                    scalar_override=scalar,
                )
                progressed = True
            elif b_id in solved and a_id not in solved:
                bounds = _constraint_scalar_bounds(constraint)
                if constraint.constraint_kind == "revolute" and constraint.drive_angle_degrees is not None:
                    scalar = _project_scalar(constraint.drive_angle_degrees, bounds)
                elif constraint.constraint_kind == "prismatic" and constraint.drive_distance is not None:
                    scalar = _project_scalar(constraint.drive_distance, bounds)
                elif bounds is not None:
                    scalar = _project_scalar(
                        _constraint_current_scalar(assembly, constraint), bounds
                    )
                else:
                    scalar = None
                solved[a_id] = _solve_other_component(
                    assembly, constraint,
                    known_side="b", known_placement=solved[b_id],
                    scalar_override=scalar,
                )
                progressed = True
            elif a_id in solved and b_id in solved:
                residual = measure_constraint_residual(
                    assembly.with_component_placement(a_id, solved[a_id]).with_component_placement(b_id, solved[b_id]),
                    constraint.constraint_id,
                )
                if strict and not residual.within_tolerance:
                    raise ValueError(
                        f"constraint '{constraint.constraint_id}' residual exceeds tolerance"
                    )
            else:
                remaining.append(constraint)
        pending = remaining

    for constraint in pending:
        a_id = constraint.connector_a.component_id
        b_id = constraint.connector_b.component_id
        bounds = _constraint_scalar_bounds(constraint)
        if bounds is None:
            if strict:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' forms an unresolvable loop"
                )
            continue
        if a_id in solved and b_id in solved:
            known_side = "a"
            known_placement = solved[a_id]
        elif b_id in solved:
            known_side = "b"
            known_placement = solved[b_id]
        else:
            if strict:
                raise ValueError(
                    f"constraint '{constraint.constraint_id}' has no grounded path"
                )
            continue

        lo, hi = bounds
        obj = lambda s: _loop_constraint_residual_at_scalar(
            assembly, constraint, known_side, known_placement, s
        )
        optimal_scalar = _golden_section_search(obj, lo, hi)
        if known_side == "a":
            solved[b_id] = _solve_other_component(
                assembly, constraint,
                known_side="a", known_placement=known_placement,
                scalar_override=optimal_scalar,
            )
        else:
            solved[a_id] = _solve_other_component(
                assembly, constraint,
                known_side="b", known_placement=known_placement,
                scalar_override=optimal_scalar,
            )

    unsolved = tuple(
        component.component_id
        for component in assembly.components
        if component.component_id not in solved
    )
    if strict and unsolved:
        raise ValueError("unsolved components in constrained assembly: " + ", ".join(unsolved))
    result = assembly
    for component_id, placement in solved.items():
        result = result.with_component_placement(component_id, placement)
    report = inspect_assembly_constraints(result)
    result._set_runtime("constraint_report", report.to_dict())
    return result


def measure_constraint_residual(
    assembly: Assembly, constraint_id: str
) -> ConstraintResidual:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    constraint = assembly.get_constraint(constraint_id)
    frame_a = _connector_world_frame(assembly, constraint.connector_a)
    frame_b = _connector_world_frame(assembly, constraint.connector_b)
    current_scalar = _constraint_current_scalar(assembly, constraint)
    motion = _motion_from_scalar(constraint, current_scalar)
    expected_b = frame_a.compose(motion)
    relative = relative_placement(expected_b, frame_b)
    translation_error = _norm(relative.origin)
    angular_error = _angular_error_degrees(relative)
    return ConstraintResidual(
        constraint.constraint_id,
        translation_error,
        angular_error,
        translation_error <= _PLACEMENT_TOLERANCE
        and angular_error <= _ANGLE_TOLERANCE_DEGREES,
    )


def inspect_assembly_constraints(assembly: Assembly) -> ConstraintReport:
    if not isinstance(assembly, Assembly):
        raise TypeError("assembly must be an Assembly")
    residuals = tuple(
        measure_constraint_residual(assembly, constraint.constraint_id)
        for constraint in assembly.constraints
    )
    all_ids = tuple(component.component_id for component in assembly.components)
    if assembly.constraints:
        reachable = set(assembly.grounded_component_ids)
        progressed = True
        while progressed:
            progressed = False
            for constraint in assembly.constraints:
                a_id = constraint.connector_a.component_id
                b_id = constraint.connector_b.component_id
                if a_id in reachable and b_id not in reachable:
                    reachable.add(b_id)
                    progressed = True
                if b_id in reachable and a_id not in reachable:
                    reachable.add(a_id)
                    progressed = True
        solved_ids = tuple(component_id for component_id in all_ids if component_id in reachable)
        unsolved_ids = tuple(component_id for component_id in all_ids if component_id not in reachable)
    else:
        solved_ids = all_ids
        unsolved_ids = ()
    return ConstraintReport(
        solved=not unsolved_ids and all(residual.within_tolerance for residual in residuals),
        grounded_component_ids=assembly.grounded_component_ids,
        solved_component_ids=solved_ids,
        unsolved_component_ids=unsolved_ids,
        residuals=residuals,
    )


def _optional_float(value: Optional[Any], *, field_name: str) -> Optional[float]:
    if value is None:
        return None
    return _finite_float(value, field_name=field_name)


def _assert_limit_contains(limit: ScalarLimit, value: float, field_name: str) -> None:
    if not limit.contains(value):
        raise ValueError(f"{field_name} is outside the scalar limit")


def _validate_connectors(connectors: Iterable[Connector]) -> Tuple[Connector, ...]:
    result = tuple(connectors or ())
    for connector in result:
        if not isinstance(connector, Connector):
            raise TypeError("connectors must contain Connector values")
    ids = [connector.connector_id for connector in result]
    duplicates = sorted({connector_id for connector_id in ids if ids.count(connector_id) > 1})
    if duplicates:
        raise ValueError("duplicate connector_id: " + ", ".join(duplicates))
    return result


def _validate_constraints(constraints: Iterable[Constraint]) -> Tuple[Constraint, ...]:
    result = tuple(constraints or ())
    for constraint in result:
        if not isinstance(constraint, Constraint):
            raise TypeError("constraints must contain Constraint values")
    ids = [constraint.constraint_id for constraint in result]
    duplicates = sorted({constraint_id for constraint_id in ids if ids.count(constraint_id) > 1})
    if duplicates:
        raise ValueError("duplicate constraint_id: " + ", ".join(duplicates))
    return result


def _validate_constraint_refs(assembly: Assembly, constraint: Constraint) -> None:
    _resolve_connector(assembly, constraint.connector_a)
    _resolve_connector(assembly, constraint.connector_b)


def _resolve_connector(assembly: Assembly, connector_ref: ConnectorRef) -> Connector:
    component = assembly.get_component(connector_ref.component_id)
    item = component.item
    if isinstance(item, Part):
        return item.get_connector(connector_ref.connector_id)
    return item.get_connector(connector_ref.connector_id)


def _connector_world_frame(assembly: Assembly, connector_ref: ConnectorRef) -> Placement:
    component = assembly.get_component(connector_ref.component_id)
    connector = _resolve_connector(assembly, connector_ref)
    return component.placement.compose(connector.placement)


def _constraint_current_scalar(assembly: Assembly, constraint: Constraint) -> float:
    frame_a = _connector_world_frame(assembly, constraint.connector_a)
    frame_b = _connector_world_frame(assembly, constraint.connector_b)
    relative = relative_placement(frame_a, frame_b)
    if constraint.constraint_kind == "prismatic":
        return relative.origin[2]
    return math.degrees(math.atan2(relative.x_axis[1], relative.x_axis[0]))


def _constraint_scalar_bounds(constraint: Constraint) -> Optional[Tuple[float, float]]:
    if constraint.constraint_kind == "revolute" and constraint.angle_limit is not None:
        return (constraint.angle_limit.lower_value, constraint.angle_limit.upper_value)
    if constraint.constraint_kind == "prismatic" and constraint.distance_limit is not None:
        return (constraint.distance_limit.lower_value, constraint.distance_limit.upper_value)
    return None


def _project_scalar(scalar: float, bounds: Optional[Tuple[float, float]]) -> float:
    if bounds is None:
        return scalar
    lo, hi = bounds
    return max(lo, min(hi, scalar))


def _motion_from_scalar(constraint: Constraint, scalar: float) -> Placement:
    if constraint.constraint_kind == "fixed":
        return identity_placement()
    if constraint.constraint_kind == "revolute":
        return rotate_z_placement(scalar)
    return translate_z_placement(scalar)


def _golden_section_search(
    func, a: float, b: float, tol: float = 1e-10, max_iter: int = 200
) -> float:
    _phi = (math.sqrt(5.0) - 1.0) / 2.0
    c = b - _phi * (b - a)
    d = a + _phi * (b - a)
    fc = func(c)
    fd = func(d)
    for _ in range(max_iter):
        if b - a <= tol:
            break
        if fc < fd:
            b = d
            d = c
            fd = fc
            c = b - _phi * (b - a)
            fc = func(c)
        else:
            a = c
            c = d
            fc = fd
            d = a + _phi * (b - a)
            fd = func(d)
    return (a + b) / 2.0


def _constraint_motion_from_current(assembly: Assembly, constraint: Constraint) -> Placement:
    if constraint.constraint_kind == "fixed":
        return identity_placement()
    if constraint.constraint_kind == "revolute":
        angle = (
            constraint.drive_angle_degrees
            if constraint.drive_angle_degrees is not None
            else _constraint_current_scalar(assembly, constraint)
        )
        return rotate_z_placement(angle)
    distance = (
        constraint.drive_distance
        if constraint.drive_distance is not None
        else _constraint_current_scalar(assembly, constraint)
    )
    return translate_z_placement(distance)


def _loop_constraint_residual_at_scalar(
    assembly: Assembly,
    constraint: Constraint,
    known_side: str,
    known_placement: Placement,
    candidate_scalar: float,
) -> float:
    unknown_ref = constraint.connector_b if known_side == "a" else constraint.connector_a
    known_ref = constraint.connector_a if known_side == "a" else constraint.connector_b
    motion = _motion_from_scalar(constraint, candidate_scalar)
    if known_side == "b":
        motion = inverse_placement(motion)
    known_connector = _resolve_connector(assembly, known_ref)
    unknown_connector = _resolve_connector(assembly, unknown_ref)
    known_frame = known_placement.compose(known_connector.placement)
    target_unknown_frame = known_frame.compose(motion)
    target_placement = target_unknown_frame.compose(inverse_placement(unknown_connector.placement))

    test = assembly.with_component_placement(
        unknown_ref.component_id, target_placement
    )
    residual = measure_constraint_residual(test, constraint.constraint_id)
    return residual.translation_error + math.radians(residual.angular_error_degrees)


def _solve_other_component(
    assembly: Assembly,
    constraint: Constraint,
    *,
    known_side: str,
    known_placement: Placement,
    scalar_override: Optional[float] = None,
) -> Placement:
    if constraint.constraint_kind == "fixed":
        motion = identity_placement()
    else:
        if scalar_override is not None:
            scalar = scalar_override
        elif known_side == "a":
            scalar = (
                constraint.drive_angle_degrees
                if constraint.constraint_kind == "revolute"
                else constraint.drive_distance
            )
            if scalar is None:
                scalar = _constraint_current_scalar(assembly, constraint)
        else:
            scalar = (
                constraint.drive_angle_degrees
                if constraint.constraint_kind == "revolute"
                else constraint.drive_distance
            )
            if scalar is None:
                scalar = _constraint_current_scalar(assembly, constraint)
        motion = _motion_from_scalar(constraint, scalar)
        if known_side == "b":
            motion = inverse_placement(motion)
    if known_side == "a":
        known_ref = constraint.connector_a
        unknown_ref = constraint.connector_b
    else:
        known_ref = constraint.connector_b
        unknown_ref = constraint.connector_a
    known_connector = _resolve_connector(assembly, known_ref)
    unknown_connector = _resolve_connector(assembly, unknown_ref)
    known_frame = known_placement.compose(known_connector.placement)
    target_unknown_frame = known_frame.compose(motion)
    return target_unknown_frame.compose(inverse_placement(unknown_connector.placement))


def _angular_error_degrees(relative: Placement) -> float:
    trace = relative.x_axis[0] + relative.y_axis[1] + relative.z_axis[2]
    cos_angle = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    return abs(math.degrees(math.acos(cos_angle)))


def _placement_from_geometry_ref(geo_ref: GeometryRef) -> Placement:
    # Compute a Placement from a GeometryRef geo_selector.
    # face: origin = face center, z_axis = face normal
    # edge: origin = edge midpoint, z_axis = edge direction (start->end)
    # vertex: origin = vertex point, z_axis = (0,0,1)
    # If geo_ref.flip is True, z_axis is negated.
    selector = geo_ref.geo_selector
    kind = geo_ref.kind

    def _vec(val: Any) -> Vec3:
        return (_finite_float(val[0], field_name="x"), _finite_float(val[1], field_name="y"), _finite_float(val[2], field_name="z"))

    if kind == "face":
        center = _vec(selector.get("center", (0.0, 0.0, 0.0)))
        normal = _vec(selector.get("normal", (0.0, 0.0, 1.0)))
        z_axis = _normalize_axis(normal, field_name="normal")
        if geo_ref.flip:
            z_axis = (-z_axis[0], -z_axis[1], -z_axis[2])
        x_axis = _orthogonal_axis(z_axis)
        y_axis = _cross(z_axis, x_axis)
        y_axis = _normalize_axis(y_axis, field_name="y_axis")
        return Placement(origin=center, x_axis=x_axis, y_axis=y_axis)

    if kind == "edge":
        center = _vec(selector.get("center", (0.0, 0.0, 0.0)))
        start = selector.get("start")
        end = selector.get("end")
        if start is not None and end is not None:
            s = _vec(start)
            e = _vec(end)
            direction = (e[0] - s[0], e[1] - s[1], e[2] - s[2])
        else:
            direction = (1.0, 0.0, 0.0)
        z_axis = _normalize_axis(direction, field_name="direction")
        if geo_ref.flip:
            z_axis = (-z_axis[0], -z_axis[1], -z_axis[2])
        x_axis = _orthogonal_axis(z_axis)
        y_axis = _cross(z_axis, x_axis)
        y_axis = _normalize_axis(y_axis, field_name="y_axis")
        return Placement(origin=center, x_axis=x_axis, y_axis=y_axis)

    if kind == "vertex":
        coords = _vec(selector.get("coordinates", (0.0, 0.0, 0.0)))
        return Placement(origin=coords)

    # Fallback for wire/solid: use center if available
    center = _vec(selector.get("center", (0.0, 0.0, 0.0)))
    return Placement(origin=center)


def _orthogonal_axis(z_axis: Vec3) -> Vec3:
    """Find an axis orthogonal to z_axis."""
    candidates = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    best = candidates[0]
    best_dot = abs(_dot(z_axis, best))
    for c in candidates[1:]:
        d = abs(_dot(z_axis, c))
        if d < best_dot:
            best_dot = d
            best = c
    if best_dot > 0.999:
        return (0.0, 1.0, 0.0) if abs(z_axis[1]) < 0.999 else (1.0, 0.0, 0.0)
    projected = (
        best[0] - z_axis[0] * _dot(z_axis, best),
        best[1] - z_axis[1] * _dot(z_axis, best),
        best[2] - z_axis[2] * _dot(z_axis, best),
    )
    return _normalize_axis(projected, field_name="x_axis")


def _assert_no_assembly_cycle(parent: Assembly, child: Assembly) -> None:
    if child.assembly_id == parent.assembly_id:
        raise ValueError(f"assembly cycle detected for '{parent.assembly_id}'")
    for component in child.components:
        if isinstance(component.item, Assembly):
            _assert_no_assembly_cycle(parent, component.item)


__all__ = [
    "Assembly",
    "Component",
    "Connector",
    "ConnectorRef",
    "Constraint",
    "ConstraintReport",
    "ConstraintResidual",
    "GeometryRef",
    "Material",
    "Part",
    "Placement",
    "ScalarLimit",
    "compose_placements",
    "identity_placement",
    "inspect_assembly_constraints",
    "inverse_placement",
    "measure_constraint_residual",
    "relative_placement",
    "rotate_z_placement",
    "solve_assembly_constraints",
    "translate_z_placement",
]
