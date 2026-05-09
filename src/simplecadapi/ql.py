from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, cast


Predicate = Callable[[Any], bool]
KeyFn = Callable[[Any], Any]
MISSING = object()
_PROPERTY_RESOLVERS: Dict[str, Callable[[Any, str], Any]] = {}


def _get_tags(obj: Any) -> List[str]:
    if hasattr(obj, "get_tags"):
        try:
            return list(obj.get_tags())
        except Exception:
            return []
    tags = getattr(obj, "_tags", None)
    if tags is None:
        return []
    return list(tags)


def _get_metadata_root(obj: Any) -> dict:
    root = getattr(obj, "_metadata", None)
    if isinstance(root, dict):
        return root
    return {}


def _lookup_metadata(obj: Any, path: str) -> Any:
    if not isinstance(path, str) or not path:
        return None
    segments = path.split(".")
    current: Any = _get_metadata_root(obj)
    for seg in segments:
        if isinstance(current, dict) and seg in current:
            current = current[seg]
        else:
            return None
    return current


def register_property_resolver(
    prefix: str, resolver: Callable[[Any, str], Any]
) -> None:
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("prefix must be a non-empty string")
    _PROPERTY_RESOLVERS[prefix] = resolver


def unregister_property_resolver(prefix: str) -> None:
    _PROPERTY_RESOLVERS.pop(prefix, None)


def _lookup_property(obj: Any, path: str) -> Any:
    if not isinstance(path, str) or not path:
        return MISSING

    if path.startswith("meta."):
        actual = _lookup_metadata(obj, path.split(".", 1)[1])
        return actual if actual is not None else MISSING

    metadata_value = _lookup_metadata(obj, path)
    if metadata_value is not None:
        return metadata_value

    for prefix, resolver in sorted(
        _PROPERTY_RESOLVERS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if path.startswith(prefix):
            value = resolver(obj, path)
            if value is not MISSING:
                return value

    if path == "topo.kind":
        cls_name = obj.__class__.__name__.lower()
        if cls_name in {"vertex", "edge", "wire", "face", "solid"}:
            return cls_name
        return MISSING

    if path == "topo.loop_role":
        if hasattr(obj, "has_tag"):
            try:
                if obj.has_tag("wire.outer") or obj.has_tag("outer_wire"):
                    return "outer"
                if obj.has_tag("wire.inner") or obj.has_tag("inner_wire"):
                    return "inner"
            except Exception:
                return MISSING
        return MISSING

    if path == "geom.type":
        gtype = _geom_type(obj)
        return gtype if gtype is not None else MISSING

    if path == "geom.family":
        cls_name = obj.__class__.__name__.lower()
        if cls_name == "edge":
            return "curve"
        if cls_name == "face":
            return "surface"
        if cls_name == "solid":
            return "body"
        if cls_name == "wire":
            return "wire"
        if cls_name == "vertex":
            return "point"
        return MISSING

    if path.startswith("geom.center."):
        center = _center_tuple(obj)
        if center is None:
            return MISSING
        axis = path.rsplit(".", 1)[1]
        if axis == "x":
            return center[0]
        if axis == "y":
            return center[1]
        if axis == "z":
            return center[2]
        return MISSING

    if path.startswith("geom.normal.") and hasattr(obj, "get_normal_at"):
        try:
            normal = obj.get_normal_at()
            axis = path.rsplit(".", 1)[1]
            if axis == "x":
                return float(normal.x)
            if axis == "y":
                return float(normal.y)
            if axis == "z":
                return float(normal.z)
        except Exception:
            return MISSING

    if path == "geom.length" and hasattr(obj, "get_length"):
        try:
            return float(obj.get_length())
        except Exception:
            return MISSING
    if path == "geom.area" and hasattr(obj, "get_area"):
        try:
            return float(obj.get_area())
        except Exception:
            return MISSING
    if path == "geom.volume" and hasattr(obj, "get_volume"):
        try:
            return float(obj.get_volume())
        except Exception:
            return MISSING
    if path == "geom.closed" and hasattr(obj, "is_closed"):
        try:
            return bool(obj.is_closed())
        except Exception:
            return MISSING

    return MISSING


def _center_tuple(obj: Any) -> Optional[Tuple[float, float, float]]:
    if hasattr(obj, "get_center"):
        try:
            center = obj.get_center()
            if hasattr(center, "x") and hasattr(center, "y") and hasattr(center, "z"):
                return (float(center.x), float(center.y), float(center.z))
        except Exception:
            pass

    if hasattr(obj, "get_start_vertex") and hasattr(obj, "get_end_vertex"):
        try:
            start = obj.get_start_vertex().get_coordinates()
            end = obj.get_end_vertex().get_coordinates()
            return (
                float(start[0] + end[0]) / 2.0,
                float(start[1] + end[1]) / 2.0,
                float(start[2] + end[2]) / 2.0,
            )
        except Exception:
            pass

    if hasattr(obj, "get_coordinates"):
        try:
            coords = obj.get_coordinates()
            return (float(coords[0]), float(coords[1]), float(coords[2]))
        except Exception:
            pass

    return None


def _geom_type(obj: Any) -> Optional[str]:
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
        from OCP.GeomAbs import (
            GeomAbs_BSplineCurve,
            GeomAbs_BSplineSurface,
            GeomAbs_BezierCurve,
            GeomAbs_BezierSurface,
            GeomAbs_Circle,
            GeomAbs_Cone,
            GeomAbs_Cylinder,
            GeomAbs_Line,
            GeomAbs_Plane,
            GeomAbs_Sphere,
            GeomAbs_Torus,
        )
        from .core import Edge, Face

        if isinstance(obj, Edge):
            curve_type = BRepAdaptor_Curve(obj.wrapped).GetType()
            mapping = {
                GeomAbs_Line: "LINE",
                GeomAbs_Circle: "CIRCLE",
                GeomAbs_BSplineCurve: "BSPLINE",
                GeomAbs_BezierCurve: "BEZIER",
            }
            return mapping.get(curve_type, str(curve_type).replace("GeomAbs_CurveType.GeomAbs_", "").upper())
        if isinstance(obj, Face):
            surface_type = BRepAdaptor_Surface(obj.wrapped).GetType()
            mapping = {
                GeomAbs_Plane: "PLANE",
                GeomAbs_Cylinder: "CYLINDER",
                GeomAbs_Cone: "CONE",
                GeomAbs_Sphere: "SPHERE",
                GeomAbs_Torus: "TORUS",
                GeomAbs_BSplineSurface: "BSPLINE",
                GeomAbs_BezierSurface: "BEZIER",
            }
            return mapping.get(surface_type, str(surface_type).replace("GeomAbs_SurfaceType.GeomAbs_", "").upper())
    except Exception:
        return None
    return None


def _compare(actual: Any, op: str, value: Any) -> bool:
    if op == "==":
        return actual == value
    if op == "!=":
        return actual != value
    if actual is None:
        return False
    try:
        if op == ">":
            return actual > value
        if op == ">=":
            return actual >= value
        if op == "<":
            return actual < value
        if op == "<=":
            return actual <= value
    except Exception:
        return False
    raise ValueError(f"unsupported op: {op}")


@dataclass(frozen=True)
class SerializablePredicate:
    kind: str
    data: Dict[str, Any] = field(default_factory=dict)
    children: Tuple["SerializablePredicate", ...] = ()

    def __call__(self, obj: Any) -> bool:
        if self.kind == "tag":
            pattern = str(self.data["pattern"])
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return any(tag.startswith(prefix) for tag in _get_tags(obj))
            return pattern in _get_tags(obj)

        if self.kind == "meta":
            actual = _lookup_metadata(obj, str(self.data["path"]))
            return _compare(actual, str(self.data["op"]), self.data["value"])

        if self.kind == "property_compare":
            actual = _lookup_property(obj, str(self.data["path"]))
            if actual is MISSING:
                return False
            return _compare(actual, str(self.data["op"]), self.data["value"])

        if self.kind == "curve_type":
            gtype = _geom_type(obj)
            return gtype == str(self.data["value"]).upper()

        if self.kind == "surface_type":
            gtype = _geom_type(obj)
            return gtype == str(self.data["value"]).upper()

        if self.kind == "and":
            return all(child(obj) for child in self.children)

        if self.kind == "or":
            return any(child(obj) for child in self.children)

        if self.kind == "not":
            return not self.children[0](obj)

        raise ValueError(f"unsupported predicate kind: {self.kind}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "data": dict(self.data),
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SerializablePredicate":
        return cls(
            kind=str(data["kind"]),
            data=dict(data.get("data", {})),
            children=tuple(
                SerializablePredicate.from_dict(child)
                for child in data.get("children", [])
            ),
        )


@dataclass(frozen=True)
class SerializableKey:
    kind: str
    data: Dict[str, Any] = field(default_factory=dict)

    def __call__(self, obj: Any) -> Any:
        if self.kind == "value":
            path = str(self.data["path"])
            default = self.data.get("default")
            actual = _lookup_metadata(obj, path)
            if actual is not None:
                return actual

            if path.startswith("geo."):
                remainder = path.split(".", 1)[1]
                if "." not in remainder:
                    if remainder == "area" and hasattr(obj, "get_area"):
                        try:
                            return obj.get_area()
                        except Exception:
                            return default
                    if remainder == "length" and hasattr(obj, "get_length"):
                        try:
                            return obj.get_length()
                        except Exception:
                            return default
                    if remainder == "volume" and hasattr(obj, "get_volume"):
                        try:
                            return obj.get_volume()
                        except Exception:
                            return default
            return default

        if self.kind == "property":
            path = str(self.data["path"])
            default = self.data.get("default")
            actual = _lookup_property(obj, path)
            if actual is MISSING:
                return default
            return actual

        if self.kind == "center_axis":
            center = _center_tuple(obj)
            if center is None:
                return None
            axis = str(self.data["axis"]).lower()
            if axis == "x":
                return center[0]
            if axis == "y":
                return center[1]
            if axis == "z":
                return center[2]
            raise ValueError(f"unsupported axis: {axis}")

        raise ValueError(f"unsupported key kind: {self.kind}")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "data": dict(self.data)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SerializableKey":
        return cls(kind=str(data["kind"]), data=dict(data.get("data", {})))


@dataclass(frozen=True)
class TraversalSpec:
    relation: str

    def to_dict(self) -> Dict[str, Any]:
        return {"relation": self.relation}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraversalSpec":
        return cls(relation=str(data["relation"]))


@dataclass(frozen=True)
class ShapeSelector:
    target_kind: str
    source_selector: Optional["ShapeSelector"] = None
    traversal: Optional[TraversalSpec] = None
    predicate: Optional[SerializablePredicate] = None
    order_key: Optional[SerializableKey] = None
    order_desc: bool = False
    limit_count: Optional[int] = None
    cardinality: Dict[str, int] = field(default_factory=dict)

    def where(self, predicate: SerializablePredicate) -> "ShapeSelector":
        if not isinstance(predicate, SerializablePredicate):
            raise TypeError(
                "ShapeSelector.where only supports serializable QL predicates"
            )
        if self.predicate is None:
            combined = predicate
        else:
            combined = and_(self.predicate, predicate)
            if not isinstance(combined, SerializablePredicate):
                raise TypeError("combined predicate must be serializable")
        return ShapeSelector(
            target_kind=self.target_kind,
            source_selector=self.source_selector,
            traversal=self.traversal,
            predicate=combined,
            order_key=self.order_key,
            order_desc=self.order_desc,
            limit_count=self.limit_count,
            cardinality=dict(self.cardinality),
        )

    def order_by(self, key: SerializableKey, desc: bool = False) -> "ShapeSelector":
        if not isinstance(key, SerializableKey):
            raise TypeError("ShapeSelector.order_by only supports serializable QL keys")
        return ShapeSelector(
            target_kind=self.target_kind,
            source_selector=self.source_selector,
            traversal=self.traversal,
            predicate=self.predicate,
            order_key=key,
            order_desc=bool(desc),
            limit_count=self.limit_count,
            cardinality=dict(self.cardinality),
        )

    def take(self, count: int) -> "ShapeSelector":
        if count < 0:
            raise ValueError("count must be >= 0")
        return ShapeSelector(
            target_kind=self.target_kind,
            source_selector=self.source_selector,
            traversal=self.traversal,
            predicate=self.predicate,
            order_key=self.order_key,
            order_desc=self.order_desc,
            limit_count=int(count),
            cardinality=dict(self.cardinality),
        )

    def exactly(self, count: int) -> "ShapeSelector":
        if count < 0:
            raise ValueError("count must be >= 0")
        card = dict(self.cardinality)
        card["exactly"] = int(count)
        return ShapeSelector(
            target_kind=self.target_kind,
            source_selector=self.source_selector,
            traversal=self.traversal,
            predicate=self.predicate,
            order_key=self.order_key,
            order_desc=self.order_desc,
            limit_count=self.limit_count,
            cardinality=card,
        )

    def traverse(self, relation: str, to_kind: str) -> "ShapeSelector":
        relation = str(relation).strip().lower()
        to_kind = str(to_kind).strip().lower()
        if relation != "boundary":
            raise ValueError(f"unsupported traversal relation: {relation}")
        if to_kind not in {"vertex", "edge", "wire", "face", "solid"}:
            raise ValueError(f"unsupported traversal target kind: {to_kind}")
        return ShapeSelector(
            target_kind=to_kind,
            source_selector=self,
            traversal=TraversalSpec(relation=relation),
        )

    def boundary(self, to_kind: str) -> "ShapeSelector":
        return self.traverse("boundary", to_kind)

    def resolve(self, scope: Any) -> List[Any]:
        if self.source_selector is None:
            items = _resolve_scope_items(scope, self.target_kind)
        else:
            if self.traversal is None:
                raise ValueError("traversal selector is missing traversal metadata")
            items = _traverse_items(
                self.source_selector.resolve(scope),
                self.traversal,
                self.target_kind,
            )
        if self.predicate is not None:
            items = [item for item in items if self.predicate(item)]

        if self.order_key is not None:
            order_key = self.order_key

            def _safe_key(obj: Any):
                value = order_key(obj)
                return (value is None, value)

            items = sorted(items, key=_safe_key, reverse=self.order_desc)

        if self.limit_count is not None:
            items = items[: self.limit_count]

        exact = self.cardinality.get("exactly")
        if exact is not None and len(items) != exact:
            raise ValueError(
                f"QL selector expected exactly {exact} {self.target_kind}(s), got {len(items)}"
            )
        return list(items)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "target_kind": self.target_kind,
            "order_desc": self.order_desc,
            "cardinality": dict(self.cardinality),
        }
        if self.source_selector is not None:
            payload["source"] = self.source_selector.to_dict()
        if self.traversal is not None:
            payload["traversal"] = self.traversal.to_dict()
        if self.predicate is not None:
            payload["predicate"] = self.predicate.to_dict()
        if self.order_key is not None:
            payload["order_key"] = self.order_key.to_dict()
        if self.limit_count is not None:
            payload["limit"] = self.limit_count
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShapeSelector":
        source_selector = None
        if isinstance(data.get("source"), dict):
            source_selector = ShapeSelector.from_dict(data["source"])
        traversal = None
        if isinstance(data.get("traversal"), dict):
            traversal = TraversalSpec.from_dict(data["traversal"])
        predicate = None
        if isinstance(data.get("predicate"), dict):
            predicate = SerializablePredicate.from_dict(data["predicate"])
        order_key = None
        if isinstance(data.get("order_key"), dict):
            order_key = SerializableKey.from_dict(data["order_key"])
        return cls(
            target_kind=str(data["target_kind"]),
            source_selector=source_selector,
            traversal=traversal,
            predicate=predicate,
            order_key=order_key,
            order_desc=bool(data.get("order_desc", False)),
            limit_count=(int(data["limit"]) if data.get("limit") is not None else None),
            cardinality=dict(data.get("cardinality", {})),
        )


def _shape_identity(obj: Any) -> Any:
    topo_id = getattr(obj, "topo_id", None)
    if topo_id is not None:
        return (obj.__class__.__name__, topo_id)

    topo_ref = None
    if hasattr(obj, "get_metadata"):
        try:
            topo_ref = obj.get_metadata("topo_ref")
        except Exception:
            topo_ref = None
    if isinstance(topo_ref, dict):
        ref_topo_id = topo_ref.get("topo_id")
        kind = topo_ref.get("kind")
        if ref_topo_id is not None:
            return (kind, ref_topo_id)

    return id(obj)


def _dedupe_items(items: Iterable[Any]) -> List[Any]:
    result: List[Any] = []
    seen = set()
    for item in items:
        marker = _shape_identity(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _boundary_items(scope: Any, target_kind: str) -> List[Any]:
    cls_name = scope.__class__.__name__

    if target_kind == "face":
        if hasattr(scope, "get_faces"):
            return list(scope.get_faces())
        return []

    if target_kind == "wire":
        if cls_name == "Face":
            wires = []
            if hasattr(scope, "get_outer_wire"):
                wires.append(scope.get_outer_wire())
            if hasattr(scope, "get_inner_wires"):
                wires.extend(scope.get_inner_wires())
            return wires
        if hasattr(scope, "get_faces"):
            wires = []
            for face in scope.get_faces():
                wires.extend(_boundary_items(face, "wire"))
            return _dedupe_items(wires)
        if hasattr(scope, "get_children"):
            return [
                child
                for child in scope.get_children()
                if child.__class__.__name__ == "Wire"
            ]
        return []

    if target_kind == "edge":
        if cls_name == "Face":
            edges = []
            for wire in _boundary_items(scope, "wire"):
                if hasattr(wire, "get_edges"):
                    edges.extend(wire.get_edges())
            return _dedupe_items(edges)
        if hasattr(scope, "get_edges"):
            return _dedupe_items(scope.get_edges())
        if hasattr(scope, "get_faces"):
            edges = []
            for face in scope.get_faces():
                edges.extend(_boundary_items(face, "edge"))
            return _dedupe_items(edges)
        return []

    if target_kind == "vertex":
        if cls_name == "Edge" and hasattr(scope, "get_children"):
            return [
                child
                for child in scope.get_children()
                if child.__class__.__name__ == "Vertex"
            ]
        if target_kind == "vertex" and hasattr(scope, "get_edges"):
            vertices = []
            for edge in _boundary_items(scope, "edge"):
                vertices.extend(_boundary_items(edge, "vertex"))
            return _dedupe_items(vertices)
        return []

    if target_kind == "solid":
        return [scope] if cls_name == "Solid" else []

    return []


def _traverse_items(
    items: Sequence[Any], traversal: TraversalSpec, target_kind: str
) -> List[Any]:
    if traversal.relation != "boundary":
        raise ValueError(f"unsupported traversal relation: {traversal.relation}")

    traversed: List[Any] = []
    for item in items:
        traversed.extend(_boundary_items(item, target_kind))
    return _dedupe_items(traversed)


def _resolve_scope_items(scope: Any, target_kind: str) -> List[Any]:
    if target_kind == "edge":
        if hasattr(scope, "get_edges"):
            return list(scope.get_edges())
    if target_kind == "face":
        if hasattr(scope, "get_faces"):
            return list(scope.get_faces())
    if target_kind == "wire":
        if hasattr(scope, "get_children"):
            return [
                child
                for child in scope.get_children()
                if child.__class__.__name__ == "Wire"
            ]
    if target_kind == "vertex":
        if hasattr(scope, "get_children"):
            return [
                child
                for child in scope.get_children()
                if child.__class__.__name__ == "Vertex"
            ]
    if isinstance(scope, Iterable) and not isinstance(scope, (str, bytes, dict)):
        return list(scope)
    raise TypeError(f"cannot resolve QL selector scope for target_kind={target_kind}")


def tag(pattern: str) -> SerializablePredicate:
    """Build a tag predicate for QL filtering.

    Args:
        pattern: Exact tag string or a trailing `*` prefix match.

    Returns:
        Serializable predicate that can be used in `Query.where(...)`.
    """

    if not isinstance(pattern, str):
        raise TypeError("pattern must be a string")
    pattern = pattern.strip()
    if "*" in pattern and not pattern.endswith("*"):
        raise ValueError("only trailing '*' wildcard is supported")
    return SerializablePredicate("tag", {"pattern": pattern})


def meta(path: str, op: str, value_: Any) -> SerializablePredicate:
    """Build a metadata comparison predicate for QL filtering.

    Args:
        path: Dot-separated metadata path.
        op: Comparison operator such as `==`, `!=`, `>`, `>=`, `<`, or `<=`.
        value_: Comparison value.

    Returns:
        Serializable predicate that compares metadata values.
    """

    if not isinstance(op, str):
        raise TypeError("op must be a string")
    return SerializablePredicate(
        "meta", {"path": path, "op": op.strip(), "value": value_}
    )


def value(path: str, default: Any = None) -> SerializableKey:
    """Build a value key extractor for ordering and projection in QL.

    Args:
        path: Property or metadata path to resolve.
        default: Fallback value when the path is missing.

    Returns:
        Serializable key function for `Query.order_by(...)`.
    """

    return SerializableKey("value", {"path": path, "default": default})


def key(path: str, default: Any = None) -> SerializableKey:
    return SerializableKey("property", {"path": path, "default": default})


def geo(field: str, default: Any = None) -> SerializableKey:
    """Shortcut for reading `geom.*` fields inside QL queries."""

    return value(f"geo.{field}", default)


def center_axis(axis: str) -> SerializableKey:
    axis = axis.lower().strip()
    if axis not in {"x", "y", "z"}:
        raise ValueError("axis must be one of 'x', 'y', 'z'")
    return key(f"geom.center.{axis}")


def prop(path: str, op: str, value_: Any) -> SerializablePredicate:
    if not isinstance(op, str):
        raise TypeError("op must be a string")
    return SerializablePredicate(
        "property_compare", {"path": path, "op": op.strip(), "value": value_}
    )


def curve_type(kind: str) -> SerializablePredicate:
    return prop("geom.type", "==", kind.upper())


def surface_type(kind: str) -> SerializablePredicate:
    return prop("geom.type", "==", kind.upper())


def and_(*predicates: Predicate) -> Predicate:
    """Combine predicates so all of them must match."""

    if all(isinstance(pred, SerializablePredicate) for pred in predicates):
        return SerializablePredicate(
            "and",
            children=cast(Tuple[SerializablePredicate, ...], tuple(predicates)),
        )

    def _predicate(obj: Any) -> bool:
        return all(pred(obj) for pred in predicates)

    return _predicate


def or_(*predicates: Predicate) -> Predicate:
    """Combine predicates so at least one of them must match."""

    if all(isinstance(pred, SerializablePredicate) for pred in predicates):
        return SerializablePredicate(
            "or",
            children=cast(Tuple[SerializablePredicate, ...], tuple(predicates)),
        )

    def _predicate(obj: Any) -> bool:
        return any(pred(obj) for pred in predicates)

    return _predicate


def not_(predicate: Predicate) -> Predicate:
    """Negate a QL predicate."""

    if isinstance(predicate, SerializablePredicate):
        return SerializablePredicate("not", children=(predicate,))

    def _predicate(obj: Any) -> bool:
        return not predicate(obj)

    return _predicate


def op(op_name: str, event: str = "*") -> SerializablePredicate:
    if event == "*":
        return tag(f"op.{op_name}.*")
    return tag(f"op.{op_name}.{event}")


def origin(role_name: str) -> SerializablePredicate:
    return tag(f"origin.{role_name}")


def role(role_name: str) -> SerializablePredicate:
    return tag(f"role.{role_name}.*")


class Query:
    def __init__(self, items: Iterable[Any]):
        self._items = list(items)

    def where(self, predicate: Predicate) -> "Query":
        return Query([item for item in self._items if predicate(item)])

    def order_by(self, key: KeyFn, desc: bool = False) -> "Query":
        def _safe_key(obj: Any):
            value_ = key(obj)
            return (value_ is None, value_)

        return Query(sorted(self._items, key=_safe_key, reverse=desc))

    def limit(self, count: int) -> "Query":
        if count <= 0:
            return Query([])
        return Query(self._items[:count])

    def first(self) -> Optional[Any]:
        return self._items[0] if self._items else None

    def all(self) -> List[Any]:
        return list(self._items)


def select(items: Iterable[Any]) -> Query:
    """Start a QL query over a shape collection or selector scope."""

    return Query(items)


def edges() -> ShapeSelector:
    return ShapeSelector(target_kind="edge")


def faces() -> ShapeSelector:
    return ShapeSelector(target_kind="face")


def wires() -> ShapeSelector:
    return ShapeSelector(target_kind="wire")


def vertices() -> ShapeSelector:
    return ShapeSelector(target_kind="vertex")


def selector_from_dict(data: Dict[str, Any]) -> ShapeSelector:
    return ShapeSelector.from_dict(data)
