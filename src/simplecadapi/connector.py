"""Connector datums, references, and placement resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Tuple, cast

from ._semantic import SemanticValueMixin, _finite_float, _validate_identifier
from .placement import (
    Placement,
    Vec3,
    _cross,
    _dot,
    _normalize_axis,
)

if TYPE_CHECKING:
    from .assembly import Assembly

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
class ConnectorAnchor(SemanticValueMixin):
    """Serializable source for a connector datum frame.

    Supported `anchor_kind` values are `geometry`, `placement`, and `forwarded`.
    """

    anchor_kind: str
    geometry_ref: Optional[GeometryRef] = None
    placement: Optional[Placement] = None
    source_component_id: Optional[str] = None
    source_connector_id: Optional[str] = None
    offset: Optional[Placement] = None
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        kind = str(self.anchor_kind).strip().lower()
        if kind not in {"geometry", "placement", "forwarded"}:
            raise ValueError("anchor_kind must be geometry, placement, or forwarded")
        object.__setattr__(self, "anchor_kind", kind)
        if kind == "geometry":
            if not isinstance(self.geometry_ref, GeometryRef):
                raise TypeError("geometry anchors require geometry_ref")
            if self.placement is not None:
                raise ValueError("geometry anchors do not accept placement")
            if self.source_component_id is not None or self.source_connector_id is not None:
                raise ValueError("geometry anchors do not accept forwarded source ids")
            if self.offset is not None:
                raise ValueError("geometry anchors do not accept offset")
            return
        if kind == "placement":
            if not isinstance(self.placement, Placement):
                raise TypeError("placement anchors require placement")
            if self.geometry_ref is not None:
                raise ValueError("placement anchors do not accept geometry_ref")
            if self.source_component_id is not None or self.source_connector_id is not None:
                raise ValueError("placement anchors do not accept forwarded source ids")
            if self.offset is not None:
                raise ValueError("placement anchors do not accept offset")
            return
        if self.geometry_ref is not None or self.placement is not None:
            raise ValueError("forwarded anchors do not accept geometry_ref or placement")
        object.__setattr__(
            self,
            "source_component_id",
            _validate_identifier(
                self.source_component_id or "",
                field_name="source_component_id",
            ),
        )
        object.__setattr__(
            self,
            "source_connector_id",
            _validate_identifier(
                self.source_connector_id or "",
                field_name="source_connector_id",
            ),
        )
        if self.offset is not None and not isinstance(self.offset, Placement):
            raise TypeError("offset must be a Placement")

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"anchor_kind": self.anchor_kind}
        if self.anchor_kind == "geometry":
            payload["geometry_ref"] = cast(GeometryRef, self.geometry_ref).to_dict()
        elif self.anchor_kind == "placement":
            payload["placement"] = cast(Placement, self.placement).to_dict()
        else:
            payload["source_component_id"] = self.source_component_id
            payload["source_connector_id"] = self.source_connector_id
            payload["offset"] = self.offset.to_dict() if self.offset is not None else None
        return payload


@dataclass(frozen=True)
class Connector(SemanticValueMixin):
    """Semantic datum frame anchored by geometry, placement, or forwarding.

    Geometry connectors derive placement from a selected BREP sub-shape.
    Placement connectors store an explicit local datum frame. Forwarded
    connectors expose a component connector as an assembly-level public
    interface.
    """

    connector_id: str
    geometry_ref: Optional[GeometryRef] = None
    name: Optional[str] = None
    anchor: Optional[ConnectorAnchor] = None
    _metadata: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)
    _runtime: Dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "connector_id",
            _validate_identifier(self.connector_id, field_name="connector_id"),
        )
        anchor = self.anchor
        if anchor is None:
            if not isinstance(self.geometry_ref, GeometryRef):
                raise TypeError("geometry_ref must be a GeometryRef when anchor is omitted")
            anchor = ConnectorAnchor("geometry", geometry_ref=self.geometry_ref)
            object.__setattr__(self, "anchor", anchor)
        elif not isinstance(anchor, ConnectorAnchor):
            raise TypeError("anchor must be a ConnectorAnchor")
        if anchor.anchor_kind == "geometry":
            object.__setattr__(self, "geometry_ref", anchor.geometry_ref)
        elif self.geometry_ref is not None:
            raise ValueError("geometry_ref is only valid for geometry connectors")
        if self.name is not None:
            name = str(self.name).strip()
            if not name:
                raise ValueError("name must not be empty when provided")
            object.__setattr__(self, "name", name)

    @property
    def anchor_kind(self) -> str:
        return cast(ConnectorAnchor, self.anchor).anchor_kind

    @property
    def placement(self) -> Placement:
        """Lazily-computed local Placement derived from the connector anchor."""
        owner = self._get_runtime("owner_assembly")
        return resolve_connector_placement(self, owner_assembly=owner)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "connector_id": self.connector_id,
            "name": self.name,
            "anchor": cast(ConnectorAnchor, self.anchor).to_dict(),
        }
        if self.geometry_ref is not None:
            payload["geometry_ref"] = self.geometry_ref.to_dict()
        return payload


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


def _validate_part_connector_anchors(connectors: Iterable[Connector]) -> None:
    for connector in connectors:
        if connector.anchor_kind == "forwarded":
            raise ValueError("forwarded connectors can only be added to assemblies")


def _validate_assembly_connector_anchors(assembly: Assembly) -> None:
    for connector in assembly.connectors:
        if connector.anchor_kind != "forwarded":
            continue
        anchor = cast(ConnectorAnchor, connector.anchor)
        try:
            source_component = assembly.get_component(cast(str, anchor.source_component_id))
        except KeyError as exc:
            raise ValueError(
                f"forwarded connector '{connector.connector_id}' references missing "
                f"component '{anchor.source_component_id}'"
            ) from exc
        try:
            source_component.item.get_connector(cast(str, anchor.source_connector_id))
        except KeyError as exc:
            raise ValueError(
                f"forwarded connector '{connector.connector_id}' references missing "
                f"connector '{anchor.source_connector_id}' on component "
                f"'{anchor.source_component_id}'"
            ) from exc
        resolve_connector_placement(connector, owner_assembly=assembly)


def resolve_connector(assembly: "Assembly", connector_ref: ConnectorRef) -> Connector:
    component = assembly.get_component(connector_ref.component_id)
    return component.item.get_connector(connector_ref.connector_id)


def resolve_connector_placement(
    connector: Connector,
    owner_assembly: Optional[Assembly] = None,
    _seen: Optional[set] = None,
) -> Placement:
    if not isinstance(connector, Connector):
        raise TypeError("connector must be a Connector")
    anchor = cast(ConnectorAnchor, connector.anchor)
    if anchor.anchor_kind == "geometry":
        return _placement_from_geometry_ref(cast(GeometryRef, anchor.geometry_ref))
    if anchor.anchor_kind == "placement":
        return cast(Placement, anchor.placement)
    if owner_assembly is None:
        raise ValueError(
            f"forwarded connector '{connector.connector_id}' requires an owner assembly"
        )
    seen = set(_seen or set())
    key = (id(owner_assembly), connector.connector_id)
    if key in seen:
        raise ValueError(f"forwarded connector cycle detected at '{connector.connector_id}'")
    seen.add(key)
    source_component_id = cast(str, anchor.source_component_id)
    source_connector_id = cast(str, anchor.source_connector_id)
    try:
        source_component = owner_assembly.get_component(source_component_id)
    except KeyError as exc:
        raise ValueError(
            f"forwarded connector '{connector.connector_id}' references missing "
            f"component '{source_component_id}'"
        ) from exc
    try:
        source_connector = source_component.item.get_connector(source_connector_id)
    except KeyError as exc:
        raise ValueError(
            f"forwarded connector '{connector.connector_id}' references missing "
            f"connector '{source_connector_id}' on component '{source_component_id}'"
        ) from exc
    from .assembly import Assembly

    source_owner = source_component.item if isinstance(source_component.item, Assembly) else None
    source_frame = source_component.placement.compose(
        resolve_connector_placement(
            source_connector,
            owner_assembly=source_owner,
            _seen=seen,
        )
    )
    if anchor.offset is not None:
        source_frame = source_frame.compose(anchor.offset)
    return source_frame


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


__all__ = [
    "Connector",
    "ConnectorAnchor",
    "ConnectorRef",
    "GeometryRef",
    "resolve_connector_placement",
]
