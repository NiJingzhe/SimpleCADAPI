"""Declarative constrained sketch objects for SimpleCADAPI.

Sketches are intent-level 2D documents. Use sketch APIs to build sketch
profiles; use concrete edge/wire APIs only for paths or pure geometry.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from .core import Edge, Face, TaggedMixin, TopoMixein, Wire
from .expr import ScalarLike, evaluate_scalar


_POINT_EPS = 1e-9


def _fresh_id(prefix: str, existing: Mapping[str, Any]) -> str:
    index = 0
    while True:
        candidate = f"{prefix}_{index}"
        if candidate not in existing:
            return candidate
        index += 1


def _as_float(value: ScalarLike) -> float:
    return float(evaluate_scalar(value))


def _angle_delta(value: float) -> float:
    while value <= -math.pi:
        value += 2.0 * math.pi
    while value > math.pi:
        value -= 2.0 * math.pi
    return value


@dataclass(frozen=True)
class SketchEntity:
    """Serializable entity inside a declarative sketch."""

    entity_id: str
    kind: str
    data: Dict[str, Any] = field(default_factory=dict)
    construction: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.entity_id,
            "kind": self.kind,
            "construction": self.construction,
        }
        payload.update(self.data)
        return payload


@dataclass(frozen=True)
class SketchConstraint:
    """Serializable constraint inside a declarative sketch."""

    constraint_id: str
    kind: str
    targets: Tuple[Dict[str, Any], ...]
    value: Any = None
    driving: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.constraint_id,
            "kind": self.kind,
            "targets": [dict(target) for target in self.targets],
            "driving": bool(self.driving),
        }
        if self.value is not None:
            payload["value"] = self.value
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True)
class SketchConstraintDiagnostic:
    """Diagnostic emitted by the sketch solver."""

    constraint_id: Optional[str]
    severity: str
    code: str
    message: str
    residual: Optional[float] = None


class SketchRef(TaggedMixin):
    """Stable reference to a sketch entity or subentity."""

    def __init__(
        self,
        sketch_id: str,
        entity_id: str,
        *,
        kind: str,
        subentity: str = "geometry",
    ) -> None:
        super().__init__()
        self.sketch_id = str(sketch_id)
        self.entity_id = str(entity_id)
        self.kind = str(kind)
        self.subentity = str(subentity)

    def to_dict(self) -> Dict[str, str]:
        return {
            "sketch_id": self.sketch_id,
            "entity_id": self.entity_id,
            "kind": self.kind,
            "subentity": self.subentity,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SketchRef":
        return cls(
            str(data["sketch_id"]),
            str(data["entity_id"]),
            kind=str(data["kind"]),
            subentity=str(data.get("subentity", "geometry")),
        )

    def __repr__(self) -> str:
        return (
            "SketchRef("
            f"sketch_id={self.sketch_id!r}, entity_id={self.entity_id!r}, "
            f"kind={self.kind!r}, subentity={self.subentity!r})"
        )


@dataclass
class SketchSolveResult(TaggedMixin):
    """Result of solving a declarative sketch."""

    sketch_id: str
    status: str
    dof: int
    residual_norm: float
    iterations: int
    solved_points: Dict[str, Tuple[float, float]]
    solved_scalars: Dict[str, float]
    diagnostics: Tuple[SketchConstraintDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        TaggedMixin.__init__(self)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sketch_id": self.sketch_id,
            "status": self.status,
            "dof": int(self.dof),
            "residual_norm": float(self.residual_norm),
            "iterations": int(self.iterations),
            "solved_points": {
                key: [float(value[0]), float(value[1])]
                for key, value in self.solved_points.items()
            },
            "solved_scalars": dict(self.solved_scalars),
            "diagnostics": [diag.__dict__.copy() for diag in self.diagnostics],
        }


class Sketch(TaggedMixin, TopoMixein):
    """Declarative constrained sketch container.

    Use `make_sketch_rsketch(...)`, `add_point_rsketch(...)`,
    `add_line_rsketch(...)`, `add_circle_rsketch(...)`, and
    `constrain_*_rsketch(...)` as the canonical API for building sketch
    profiles. Public sketch construction APIs are functional and return an
    updated `Sketch` document. The legacy `curves` constructor remains only for
    reading already-built wire/edge containers.
    """

    def __init__(
        self,
        curves: Iterable[Edge | Wire] | None = None,
        *,
        name: Optional[str] = None,
        plane: Any = "XY",
        sketch_id: Optional[str] = None,
    ) -> None:
        TaggedMixin.__init__(self)
        TopoMixein.__init__(self, level=2, self_shape_ref=self)
        self.sketch_id = str(sketch_id or f"sketch_{uuid.uuid4().hex[:8]}")
        self.name = name
        self.plane = plane
        self.entities: Dict[str, SketchEntity] = {}
        self.entity_order: List[str] = []
        self.constraints: List[SketchConstraint] = []
        self._last_solve_result: Optional[SketchSolveResult] = None
        if curves is not None:
            for curve in curves:
                self.add_curve(curve)

    def add_curve(self, curve: Edge | Wire) -> "Sketch":
        if not isinstance(curve, (Edge, Wire)):
            raise ValueError("Sketch only supports Edge or Wire curve inputs")
        self.add_child(curve)
        return self

    def curves(self) -> List[Edge | Wire]:
        return list(self.get_children())

    def closed_wires(self) -> List[Wire]:
        result: List[Wire] = []
        for curve in self.curves():
            if isinstance(curve, Wire) and curve.is_closed():
                result.append(curve)
        return result

    def to_faces(self) -> List[Face]:
        if self.entities:
            return [self.to_face()]
        from .operations import make_face_from_wire_rface

        return [make_face_from_wire_rface(wire) for wire in self.closed_wires()]

    def to_face(self, profile: int | str = 0) -> Face:
        from .operations import make_face_from_sketch_rface

        return make_face_from_sketch_rface(self, profile=profile)

    def clone(self, *, include_solve: bool = True) -> "Sketch":
        cloned = Sketch(name=self.name, plane=self.plane, sketch_id=self.sketch_id)
        cloned._copy_tag_state_from(self)
        cloned._metadata = self._metadata.copy()
        cloned.entities = dict(self.entities)
        cloned.entity_order = list(self.entity_order)
        cloned.constraints = list(self.constraints)
        cloned._last_solve_result = self._last_solve_result if include_solve else None
        for curve in self.curves():
            cloned.add_curve(curve)
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sketch_id": self.sketch_id,
            "name": self.name,
            "plane": self.plane,
            "entities": [self.entities[key].to_dict() for key in self.entity_order],
            "constraints": [constraint.to_dict() for constraint in self.constraints],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Sketch":
        sketch = cls(
            name=data.get("name"),
            plane=data.get("plane", "XY"),
            sketch_id=str(data.get("sketch_id") or data.get("name") or "sketch"),
        )
        for entity_data in data.get("entities", []):
            entity_id = str(entity_data["id"])
            kind = str(entity_data["kind"])
            construction = bool(entity_data.get("construction", False))
            payload = dict(entity_data)
            payload.pop("id", None)
            payload.pop("kind", None)
            payload.pop("construction", None)
            sketch._add_entity(
                SketchEntity(entity_id, kind, payload, construction=construction)
            )
        for constraint_data in data.get("constraints", []):
            sketch.constraints.append(
                SketchConstraint(
                    constraint_id=str(constraint_data["id"]),
                    kind=str(constraint_data["kind"]),
                    targets=tuple(dict(target) for target in constraint_data.get("targets", [])),
                    value=constraint_data.get("value"),
                    driving=bool(constraint_data.get("driving", True)),
                    metadata=dict(constraint_data.get("metadata", {})),
                )
            )
        return sketch

    def ref(self, entity_id: str, *, kind: Optional[str] = None, subentity: str = "geometry") -> SketchRef:
        if entity_id not in self.entities:
            raise ValueError(f"Unknown sketch entity '{entity_id}'")
        entity = self.entities[entity_id]
        return SketchRef(self.sketch_id, entity_id, kind=kind or entity.kind, subentity=subentity)

    def point_ref(self, path: str) -> SketchRef:
        if "." in path:
            entity_id, subentity = path.split(".", 1)
            if entity_id not in self.entities:
                raise ValueError(f"Unknown sketch entity '{entity_id}'")
            entity = self.entities[entity_id]
            valid_subentities = {
                "line": {"start", "end"},
                "circle": {"center"},
                "arc": {"start", "end"},
                "bspline": {"start", "end"},
            }.get(entity.kind, set())
            if subentity not in valid_subentities:
                raise ValueError(
                    f"Sketch entity '{entity_id}' has no point subentity '{subentity}'"
                )
            return SketchRef(self.sketch_id, entity_id, kind="point", subentity=subentity)
        if path not in self.entities:
            raise ValueError(f"Unknown sketch point '{path}'")
        entity = self.entities[path]
        if entity.kind != "point":
            raise ValueError(f"Sketch entity '{path}' is kind '{entity.kind}', not 'point'")
        return SketchRef(self.sketch_id, path, kind="point")

    def resolve_target(
        self,
        target: Union[SketchRef, str],
        *,
        expected: Optional[Union[str, Sequence[str]]] = None,
    ) -> SketchRef:
        if isinstance(expected, str):
            expected_kinds = {expected}
        elif expected is None:
            expected_kinds = set()
        else:
            expected_kinds = {str(item) for item in expected}

        if isinstance(target, SketchRef):
            ref = target
        elif isinstance(target, str):
            if "." in target or expected_kinds == {"point"}:
                ref = self.point_ref(target)
            else:
                if target not in self.entities:
                    raise ValueError(f"Unknown sketch entity '{target}'")
                entity = self.entities[target]
                ref = self.point_ref(target) if entity.kind == "point" else self.ref(target)
        else:
            raise TypeError("Sketch targets must be SketchRef or string ids")

        self.validate_ref(ref)
        if expected_kinds and ref.kind not in expected_kinds:
            expected_label = ", ".join(sorted(expected_kinds))
            raise ValueError(
                f"Sketch target '{ref.entity_id}' is kind '{ref.kind}', expected {expected_label}"
            )
        return ref

    def add_point(self, point_id: str, x: ScalarLike, y: ScalarLike) -> SketchRef:
        self._add_entity(SketchEntity(point_id, "point", {"x": x, "y": y}))
        return self.point_ref(point_id)

    def add_line(
        self,
        entity_id: str,
        start: SketchRef,
        end: SketchRef,
        *,
        construction: bool = False,
    ) -> "Sketch":
        start_id = self.resolve_point_id(start)
        end_id = self.resolve_point_id(end)
        if start_id == end_id:
            raise ValueError("A sketch line requires two distinct point refs")
        self._add_entity(
            SketchEntity(
                entity_id,
                "line",
                {"start": start_id, "end": end_id},
                construction=construction,
            )
        )
        return self

    def add_circle(
        self,
        entity_id: str,
        center: SketchRef,
        radius: ScalarLike,
        *,
        construction: bool = False,
    ) -> "Sketch":
        center_id = self.resolve_point_id(center)
        if _as_float(radius) <= 0.0:
            raise ValueError("A sketch circle radius must be positive")
        self._add_entity(
            SketchEntity(
                entity_id,
                "circle",
                {"center": center_id, "radius": radius},
                construction=construction,
            )
        )
        return self

    def add_arc(
        self,
        entity_id: str,
        start: SketchRef,
        end: SketchRef,
        center: SketchRef,
        *,
        construction: bool = False,
    ) -> "Sketch":
        """Add an arc edge defined by start point, end point, and center point."""
        start_id = self.resolve_point_id(start)
        end_id = self.resolve_point_id(end)
        center_id = self.resolve_point_id(center)
        if start_id == end_id:
            raise ValueError("A sketch arc requires two distinct endpoint refs")
        self._add_entity(
            SketchEntity(
                entity_id,
                "arc",
                {"start": start_id, "end": end_id, "center": center_id},
                construction=construction,
            )
        )
        return self

    def add_bspline(
        self,
        entity_id: str,
        start: SketchRef,
        end: SketchRef,
        control_points: Sequence[Sequence[float]],
        degree: int = 3,
        knots: Optional[Sequence[float]] = None,
        multiplicities: Optional[Sequence[int]] = None,
        weights: Optional[Sequence[float]] = None,
        periodic: bool = False,
        *,
        construction: bool = False,
    ) -> "Sketch":
        """Add a B-spline curve edge defined by control points.

        The start/end point refs link the B-spline into the profile loop.
        Control points are stored as literal 2-D coordinates (not point
        entity ids) so the solver does not modify them.
        """
        start_id = self.resolve_point_id(start)
        end_id = self.resolve_point_id(end)
        if start_id == end_id:
            raise ValueError("A sketch bspline requires two distinct endpoint refs")
        if len(control_points) < degree + 1:
            raise ValueError(f"bspline requires at least degree+1 control points, got {len(control_points)}")
        literal_cps = [[float(p[0]), float(p[1])] for p in control_points]
        self._add_entity(
            SketchEntity(
                entity_id,
                "bspline",
                {
                    "start": start_id,
                    "end": end_id,
                    "control_points": literal_cps,
                    "degree": int(degree),
                    "knots": list(knots) if knots is not None else None,
                    "multiplicities": list(multiplicities) if multiplicities is not None else None,
                    "weights": list(weights) if weights is not None else None,
                    "periodic": bool(periodic),
                },
                construction=construction,
            )
        )
        return self

    def add_constraint(
        self,
        kind: str,
        targets: Sequence[SketchRef],
        *,
        value: Any = None,
        constraint_id: Optional[str] = None,
        driving: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Sketch":
        for target in targets:
            self.validate_ref(target)
        existing = {constraint.constraint_id: constraint for constraint in self.constraints}
        cid = constraint_id or _fresh_id(f"c_{kind}", existing)
        if cid in existing:
            raise ValueError(f"Duplicate sketch constraint id '{cid}'")
        self.constraints.append(
            SketchConstraint(
                constraint_id=cid,
                kind=str(kind),
                targets=tuple(target.to_dict() for target in targets),
                value=value,
                driving=driving,
                metadata=dict(metadata or {}),
            )
        )
        return self

    def solve(
        self,
        *,
        require_fully_constrained: bool = False,
        strict: bool = True,
        tolerance: float = 1e-7,
        max_iterations: int = 80,
    ) -> SketchSolveResult:
        result = _SketchSolver(self, tolerance=tolerance, max_iterations=max_iterations).solve()
        self._last_solve_result = result
        if strict and result.status in {"conflicting", "failed"}:
            raise ValueError(
                f"Sketch solve failed with status={result.status}, residual={result.residual_norm:.6g}"
            )
        if require_fully_constrained and result.dof > 0:
            raise ValueError(f"Sketch is underconstrained with {result.dof} remaining DOF")
        return result

    def solved_result(self) -> SketchSolveResult:
        if self._last_solve_result is None:
            return self.solve(strict=True)
        return self._last_solve_result

    def make_wire(
        self,
        profile: int | str = 0,
        *,
        solve_result: Optional[SketchSolveResult] = None,
    ) -> Wire:
        profile_payload = self._profile_payload(profile, solve_result=solve_result)
        return self._wire_from_profile_payload(profile_payload)

    def _wire_from_profile_payload(self, profile_payload: Mapping[str, Any]) -> Wire:
        from .operations import make_circle_redge, make_line_redge, make_wire_from_edges_rwire

        if profile_payload["kind"] == "circle":
            center = profile_payload["center"]
            edge = make_circle_redge(center, profile_payload["radius"], profile_payload["normal"])
            return make_wire_from_edges_rwire([edge])
        if profile_payload["kind"] == "line_loop":
            points = profile_payload["points"]
            edges = [
                make_line_redge(points[index], points[(index + 1) % len(points)])
                for index in range(len(points))
            ]
            return make_wire_from_edges_rwire(edges)
        if profile_payload["kind"] == "edge_loop":
            return self._wire_from_edge_loop(profile_payload)
        raise ValueError(f"Unsupported sketch profile kind '{profile_payload['kind']}'")

    def _wire_from_edge_loop(self, profile_payload: Mapping[str, Any]) -> Wire:
        """Build a wire from a mixed-edge profile (line + arc + bspline)."""
        from .operations import (
            make_angle_arc_redge,
            make_line_redge,
            make_spline_redge,
            make_wire_from_edges_rwire,
        )

        entity_ids = profile_payload["entity_ids"]
        result: SketchSolveResult = profile_payload["solve_result"]
        # Build a point_id → 3-D coordinate map from the solve result
        # (includes ALL points, not just loop vertices — needed for arc centers)
        point_map: Dict[str, Tuple[float, float, float]] = {}
        for pid, pt in result.solved_points.items():
            point_map[pid] = self._point3(pt)

        edges = []
        for eid in entity_ids:
            entity = self.entities[eid]
            if entity.kind == "line":
                start_id, end_id = str(entity.data["start"]), str(entity.data["end"])
                edges.append(make_line_redge(point_map[start_id], point_map[end_id]))
            elif entity.kind == "arc":
                start_id = str(entity.data["start"])
                end_id = str(entity.data["end"])
                center_id = str(entity.data["center"])
                sp = point_map[start_id]
                ep = point_map[end_id]
                cp = point_map[center_id]
                import math as _math
                start_angle = _math.atan2(sp[1] - cp[1], sp[0] - cp[0])
                end_angle = _math.atan2(ep[1] - cp[1], ep[0] - cp[0])
                radius = _math.hypot(sp[0] - cp[0], sp[1] - cp[1])
                if abs(end_angle - start_angle) < 1e-12:
                    end_angle += 2.0 * _math.pi
                edges.append(
                    make_angle_arc_redge(
                        center=cp, radius=radius,
                        start_angle=start_angle, end_angle=end_angle,
                        normal=(0.0, 0.0, 1.0),
                    )
                )
            elif entity.kind == "bspline":
                cps_2d = entity.data["control_points"]
                degree = int(entity.data.get("degree", 3))
                knots = entity.data.get("knots")
                multiplicities = entity.data.get("multiplicities")
                weights = entity.data.get("weights")
                periodic = bool(entity.data.get("periodic", False))
                cps_3d = [(p[0], p[1], 0.0) for p in cps_2d]
                edges.append(
                    make_spline_redge(
                        control_points=cps_3d,
                        degree=degree,
                        knots=knots,
                        multiplicities=multiplicities,
                        weights=weights,
                        periodic=periodic,
                    )
                )
            else:
                raise ValueError(f"Unsupported edge kind '{entity.kind}' in edge_loop profile")
        return make_wire_from_edges_rwire(edges)

    def make_face(
        self,
        profile: int | str = 0,
        *,
        solve_result: Optional[SketchSolveResult] = None,
    ) -> Face:
        from .operations import make_face_from_wire_rface

        wire = self.make_wire(profile=profile, solve_result=solve_result)
        return make_face_from_wire_rface(wire, normal=self._plane_normal_tuple())

    def _add_entity(self, entity: SketchEntity) -> None:
        if entity.entity_id in self.entities:
            raise ValueError(f"Duplicate sketch entity id '{entity.entity_id}'")
        self.entities[entity.entity_id] = entity
        self.entity_order.append(entity.entity_id)

    def validate_ref(self, ref: SketchRef) -> None:
        if not isinstance(ref, SketchRef):
            raise TypeError("Sketch constraints require SketchRef targets")
        if ref.sketch_id != self.sketch_id:
            raise ValueError("SketchRef belongs to a different sketch")
        if ref.entity_id not in self.entities:
            raise ValueError(f"Unknown sketch entity '{ref.entity_id}'")
        if ref.kind == "point":
            self.resolve_point_id(ref)
        elif ref.kind in {"line", "circle", "arc", "bspline"}:
            entity = self.entities[ref.entity_id]
            if entity.kind != ref.kind:
                raise ValueError(
                    f"SketchRef '{ref.entity_id}' is kind '{entity.kind}', not '{ref.kind}'"
                )

    def resolve_point_id(self, ref: SketchRef) -> str:
        if ref.sketch_id != self.sketch_id:
            raise ValueError("SketchRef belongs to a different sketch")
        if ref.entity_id not in self.entities:
            raise ValueError(f"Unknown sketch entity '{ref.entity_id}'")
        entity = self.entities[ref.entity_id]
        if ref.kind == "point" and entity.kind == "point":
            return ref.entity_id
        if entity.kind == "line" and ref.subentity in {"start", "end"}:
            return str(entity.data[ref.subentity])
        if entity.kind == "circle" and ref.subentity == "center":
            return str(entity.data["center"])
        if entity.kind in {"arc", "bspline"} and ref.subentity in {"start", "end"}:
            return str(entity.data[ref.subentity])
        raise ValueError(f"Cannot resolve {ref!r} to a sketch point")

    def _constraint_refs(self, constraint: SketchConstraint) -> List[SketchRef]:
        return [SketchRef.from_dict(target) for target in constraint.targets]

    def _plane_frame(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        plane = self.plane
        if isinstance(plane, str):
            token = plane.upper()
            if token == "XY":
                return (
                    np.array([0.0, 0.0, 0.0]),
                    np.array([1.0, 0.0, 0.0]),
                    np.array([0.0, 1.0, 0.0]),
                    np.array([0.0, 0.0, 1.0]),
                )
            if token == "XZ":
                return (
                    np.array([0.0, 0.0, 0.0]),
                    np.array([1.0, 0.0, 0.0]),
                    np.array([0.0, 0.0, 1.0]),
                    np.array([0.0, -1.0, 0.0]),
                )
            if token == "YZ":
                return (
                    np.array([0.0, 0.0, 0.0]),
                    np.array([0.0, 1.0, 0.0]),
                    np.array([0.0, 0.0, 1.0]),
                    np.array([1.0, 0.0, 0.0]),
                )
        if isinstance(plane, Mapping):
            origin = np.array(plane.get("origin", (0.0, 0.0, 0.0)), dtype=float)
            x_axis = np.array(plane.get("x_axis", (1.0, 0.0, 0.0)), dtype=float)
            y_axis = np.array(plane.get("y_axis", (0.0, 1.0, 0.0)), dtype=float)
            x_axis = x_axis / np.linalg.norm(x_axis)
            y_axis = y_axis / np.linalg.norm(y_axis)
            normal = np.cross(x_axis, y_axis)
            normal = normal / np.linalg.norm(normal)
            return origin, x_axis, y_axis, normal
        raise ValueError("Sketch plane must be 'XY', 'XZ', 'YZ', or a plane mapping")

    def _point3(self, point: Tuple[float, float]) -> Tuple[float, float, float]:
        origin, x_axis, y_axis, _normal = self._plane_frame()
        vec = origin + float(point[0]) * x_axis + float(point[1]) * y_axis
        return (float(vec[0]), float(vec[1]), float(vec[2]))

    def _plane_normal_tuple(self) -> Tuple[float, float, float]:
        _origin, _x_axis, _y_axis, normal = self._plane_frame()
        return (float(normal[0]), float(normal[1]), float(normal[2]))

    def _profile_payload(
        self,
        profile: int | str = 0,
        *,
        solve_result: Optional[SketchSolveResult] = None,
    ) -> Dict[str, Any]:
        result = solve_result or self.solved_result()
        profiles = self._profiles_from_solution(result)
        if not profiles:
            raise ValueError("Sketch does not contain a closed non-construction profile")
        if isinstance(profile, str):
            for item in profiles:
                if item.get("id") == profile:
                    return item
            raise ValueError(f"Unknown sketch profile '{profile}'")
        index = int(profile)
        if index < 0 or index >= len(profiles):
            raise ValueError(f"Sketch profile index {index} is out of range")
        return profiles[index]

    def _profiles_from_solution(self, result: SketchSolveResult) -> List[Dict[str, Any]]:
        profiles: List[Dict[str, Any]] = []
        for entity_id in self.entity_order:
            entity = self.entities[entity_id]
            if entity.construction:
                continue
            if entity.kind == "circle":
                center_id = str(entity.data["center"])
                scalar_key = f"circle:{entity_id}:radius"
                center = result.solved_points[center_id]
                profiles.append(
                    {
                        "id": entity_id,
                        "kind": "circle",
                        "entity_ids": [entity_id],
                        "center": self._point3(center),
                        "radius": float(result.solved_scalars[scalar_key]),
                        "normal": self._plane_normal_tuple(),
                    }
                )
        profiles.extend(self._edge_loop_profiles(result))
        return profiles

    # --- Edge kinds that participate in closed-loop profiles ---
    _EDGE_KINDS = frozenset({"line", "arc", "bspline"})

    @staticmethod
    def _edge_endpoints(entity: SketchEntity) -> Tuple[str, str]:
        """Extract (start_point_id, end_point_id) from any edge entity."""
        return str(entity.data["start"]), str(entity.data["end"])

    def _edge_loop_profiles(self, result: SketchSolveResult) -> List[Dict[str, Any]]:
        edge_ids = [
            entity_id
            for entity_id in self.entity_order
            if self.entities[entity_id].kind in self._EDGE_KINDS
            and not self.entities[entity_id].construction
        ]
        unused = set(edge_ids)
        profiles: List[Dict[str, Any]] = []
        while unused:
            first_edge = min(unused, key=self.entity_order.index)
            component = self._edge_component(first_edge, unused)
            unused.difference_update(component)
            ordered = self._ordered_edge_loop(component)
            if ordered is None:
                continue
            point_ids, ordered_edge_ids = ordered
            profiles.append(
                {
                    "id": component[0],
                    "kind": "edge_loop",
                    "entity_ids": list(ordered_edge_ids),
                    "point_ids": list(point_ids),
                    "points": [self._point3(result.solved_points[pid]) for pid in point_ids],
                    "solve_result": result,
                }
            )
        return profiles

    def _edge_component(self, first_edge: str, candidates: set[str]) -> List[str]:
        queue = [first_edge]
        seen_edges: set[str] = set()
        seen_points: set[str] = set()
        while queue:
            edge_id = queue.pop(0)
            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)
            entity = self.entities[edge_id]
            for point_id in self._edge_endpoints(entity):
                if point_id in seen_points:
                    continue
                seen_points.add(point_id)
                for other_id in candidates:
                    other = self.entities[other_id]
                    if point_id in set(self._edge_endpoints(other)):
                        queue.append(other_id)
        return sorted(seen_edges, key=self.entity_order.index)

    def _ordered_edge_loop(self, edge_ids: Sequence[str]) -> Optional[Tuple[List[str], List[str]]]:
        adjacency: Dict[str, List[str]] = {}
        for edge_id in edge_ids:
            entity = self.entities[edge_id]
            start, end = self._edge_endpoints(entity)
            adjacency.setdefault(start, []).append(edge_id)
            adjacency.setdefault(end, []).append(edge_id)
        if not adjacency or any(len(edges) != 2 for edges in adjacency.values()):
            return None

        start_edge = edge_ids[0]
        entity = self.entities[start_edge]
        start_point, current_point = self._edge_endpoints(entity)
        used_edges = {start_edge}
        ordered_points = [start_point, current_point]
        ordered_edge_ids = [start_edge]

        while current_point != start_point:
            options = [eid for eid in adjacency[current_point] if eid not in used_edges]
            if not options:
                return None
            next_edge = options[0]
            used_edges.add(next_edge)
            ordered_edge_ids.append(next_edge)
            next_entity = self.entities[next_edge]
            next_start, next_end = self._edge_endpoints(next_entity)
            current_point = next_end if next_start == current_point else next_start
            if current_point != start_point:
                ordered_points.append(current_point)
            if len(used_edges) > len(edge_ids):
                return None
        if len(used_edges) != len(edge_ids):
            return None
        return ordered_points, ordered_edge_ids


class _SketchSolver:
    def __init__(self, sketch: Sketch, *, tolerance: float, max_iterations: int) -> None:
        self.sketch = sketch
        self.tolerance = float(tolerance)
        self.max_iterations = int(max_iterations)
        self.point_ids = [
            entity_id
            for entity_id in sketch.entity_order
            if sketch.entities[entity_id].kind == "point"
        ]
        self.scalar_ids = [
            f"circle:{entity_id}:radius"
            for entity_id in sketch.entity_order
            if sketch.entities[entity_id].kind == "circle"
        ]
        self.var_names = [f"point:{pid}:x" for pid in self.point_ids]
        self.var_names.extend(f"point:{pid}:y" for pid in self.point_ids)
        self.var_names.extend(self.scalar_ids)

    def solve(self) -> SketchSolveResult:
        if not self.var_names:
            return SketchSolveResult(
                sketch_id=self.sketch.sketch_id,
                status="solved",
                dof=0,
                residual_norm=0.0,
                iterations=0,
                solved_points={},
                solved_scalars={},
            )
        x = self._initial_vector()
        diagnostics: List[SketchConstraintDiagnostic] = []
        iterations = 0
        residual = self._residual_vector(x)
        best_norm = float(np.linalg.norm(residual))
        damping = 1e-6
        for iterations in range(self.max_iterations):
            if best_norm <= self.tolerance:
                break
            jacobian = self._finite_difference_jacobian(x, residual)
            lhs = jacobian.T @ jacobian + damping * np.eye(len(x))
            rhs = -(jacobian.T @ residual)
            try:
                step = np.linalg.solve(lhs, rhs)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(lhs, rhs, rcond=None)[0]
            if not np.all(np.isfinite(step)):
                diagnostics.append(
                    SketchConstraintDiagnostic(None, "error", "nonfinite_step", "Sketch solver produced a non-finite step.")
                )
                break
            accepted = False
            scale = 1.0
            while scale >= 1e-4:
                candidate = x + scale * step
                candidate_residual = self._residual_vector(candidate)
                candidate_norm = float(np.linalg.norm(candidate_residual))
                if candidate_norm <= best_norm:
                    x = candidate
                    residual = candidate_residual
                    best_norm = candidate_norm
                    accepted = True
                    damping = max(damping * 0.5, 1e-12)
                    break
                scale *= 0.5
            if not accepted:
                damping = min(damping * 10.0, 1e6)
        final_jacobian = self._finite_difference_jacobian(x, residual)
        rank = int(np.linalg.matrix_rank(final_jacobian, tol=1e-7)) if final_jacobian.size else 0
        dof = max(0, len(x) - rank)
        if len(residual) > rank and best_norm <= self.tolerance:
            diagnostics.append(
                SketchConstraintDiagnostic(None, "warning", "redundant_constraints", "Sketch has redundant but consistent constraints.")
            )
        if best_norm > self.tolerance:
            status = "conflicting"
            diagnostics.append(
                SketchConstraintDiagnostic(None, "error", "residual_too_large", "Sketch constraints could not be satisfied.", best_norm)
            )
        elif dof > 0:
            status = "underconstrained"
            diagnostics.append(
                SketchConstraintDiagnostic(None, "warning", "underconstrained", f"Sketch has {dof} remaining DOF.")
            )
        else:
            status = "solved"
        points, scalars = self._state_from_vector(x)
        return SketchSolveResult(
            sketch_id=self.sketch.sketch_id,
            status=status,
            dof=dof,
            residual_norm=best_norm,
            iterations=iterations,
            solved_points=points,
            solved_scalars=scalars,
            diagnostics=tuple(diagnostics),
        )

    def _initial_vector(self) -> np.ndarray:
        values: List[float] = []
        for point_id in self.point_ids:
            entity = self.sketch.entities[point_id]
            values.append(_as_float(entity.data["x"]))
        for point_id in self.point_ids:
            entity = self.sketch.entities[point_id]
            values.append(_as_float(entity.data["y"]))
        for scalar_id in self.scalar_ids:
            _prefix, entity_id, _name = scalar_id.split(":", 2)
            entity = self.sketch.entities[entity_id]
            values.append(_as_float(entity.data["radius"]))
        return np.array(values, dtype=float)

    def _state_from_vector(self, x: np.ndarray) -> Tuple[Dict[str, Tuple[float, float]], Dict[str, float]]:
        points: Dict[str, Tuple[float, float]] = {}
        offset_y = len(self.point_ids)
        for idx, point_id in enumerate(self.point_ids):
            points[point_id] = (float(x[idx]), float(x[offset_y + idx]))
        scalars: Dict[str, float] = {}
        scalar_offset = 2 * len(self.point_ids)
        for idx, scalar_id in enumerate(self.scalar_ids):
            scalars[scalar_id] = float(x[scalar_offset + idx])
        return points, scalars

    def _finite_difference_jacobian(self, x: np.ndarray, residual: np.ndarray) -> np.ndarray:
        if len(residual) == 0:
            return np.zeros((0, len(x)))
        jacobian = np.zeros((len(residual), len(x)), dtype=float)
        for idx in range(len(x)):
            step = 1e-6 * max(1.0, abs(float(x[idx])))
            shifted = x.copy()
            shifted[idx] += step
            jacobian[:, idx] = (self._residual_vector(shifted) - residual) / step
        return jacobian

    def _residual_vector(self, x: np.ndarray) -> np.ndarray:
        points, scalars = self._state_from_vector(x)
        residuals: List[float] = []
        for constraint in self.sketch.constraints:
            residuals.extend(self._constraint_residuals(constraint, points, scalars))
        return np.array(residuals, dtype=float)

    def _constraint_residuals(
        self,
        constraint: SketchConstraint,
        points: Mapping[str, Tuple[float, float]],
        scalars: Mapping[str, float],
    ) -> List[float]:
        refs = self.sketch._constraint_refs(constraint)
        kind = constraint.kind
        if kind == "fix":
            return self._fix_residuals(refs[0], points, scalars)
        if kind == "coincident":
            a = self._point(refs[0], points)
            b = self._point(refs[1], points)
            return [a[0] - b[0], a[1] - b[1]]
        if kind == "horizontal":
            a, b = self._line_points(refs[0], points)
            return [b[1] - a[1]]
        if kind == "vertical":
            a, b = self._line_points(refs[0], points)
            return [b[0] - a[0]]
        if kind == "parallel":
            return [self._cross_normalized(refs[0], refs[1], points)]
        if kind == "perpendicular":
            return [self._dot_normalized(refs[0], refs[1], points)]
        if kind == "collinear":
            a, _b = self._line_points(refs[0], points)
            return [self._cross_normalized(refs[0], refs[1], points), self._point_line_distance(a, refs[1], points)]
        if kind == "equal_length":
            return [self._line_length(refs[0], points) - self._line_length(refs[1], points)]
        if kind == "equal_radius":
            return [self._circle_radius(refs[0], scalars) - self._circle_radius(refs[1], scalars)]
        if kind == "distance":
            return [self._point_distance(refs[0], refs[1], points) - _as_float(constraint.value)]
        if kind == "distance_x":
            a = self._point(refs[0], points)
            b = self._point(refs[1], points)
            return [(b[0] - a[0]) - _as_float(constraint.value)]
        if kind == "distance_y":
            a = self._point(refs[0], points)
            b = self._point(refs[1], points)
            return [(b[1] - a[1]) - _as_float(constraint.value)]
        if kind == "length":
            return [self._line_length(refs[0], points) - _as_float(constraint.value)]
        if kind == "angle":
            return [self._line_angle_delta(refs[0], refs[1], points, _as_float(constraint.value))]
        if kind == "radius":
            return [self._circle_radius(refs[0], scalars) - _as_float(constraint.value)]
        if kind == "diameter":
            return [2.0 * self._circle_radius(refs[0], scalars) - _as_float(constraint.value)]
        if kind == "point_on":
            return self._point_on_residuals(refs[0], refs[1], points, scalars)
        if kind == "concentric":
            a = self._circle_center(refs[0], points)
            b = self._circle_center(refs[1], points)
            return [a[0] - b[0], a[1] - b[1]]
        if kind == "midpoint":
            point = self._point(refs[0], points)
            a, b = self._line_points(refs[1], points)
            return [point[0] - 0.5 * (a[0] + b[0]), point[1] - 0.5 * (a[1] + b[1])]
        if kind == "tangent":
            return [self._tangent_residual(refs[0], refs[1], points, scalars)]
        if kind == "symmetric":
            a = self._point(refs[0], points)
            b = self._point(refs[1], points)
            axis_a, axis_b = self._line_points(refs[2], points)
            axis = self._sub(axis_b, axis_a)
            mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
            return [self._point_line_distance(mid, refs[2], points), self._dot(self._sub(a, b), axis) / max(self._norm(axis), _POINT_EPS)]
        raise ValueError(f"Unsupported sketch constraint kind '{kind}'")

    def _fix_residuals(
        self,
        ref: SketchRef,
        points: Mapping[str, Tuple[float, float]],
        scalars: Mapping[str, float],
    ) -> List[float]:
        entity = self.sketch.entities[ref.entity_id]
        if ref.kind == "point" or entity.kind == "point":
            pid = self.sketch.resolve_point_id(ref)
            target = self.sketch.entities[pid]
            point = points[pid]
            return [point[0] - _as_float(target.data["x"]), point[1] - _as_float(target.data["y"])]
        if entity.kind == "line":
            start = self._fix_residuals(self.sketch.point_ref(f"{ref.entity_id}.start"), points, scalars)
            end = self._fix_residuals(self.sketch.point_ref(f"{ref.entity_id}.end"), points, scalars)
            return start + end
        if entity.kind == "circle":
            center = self._fix_residuals(self.sketch.point_ref(f"{ref.entity_id}.center"), points, scalars)
            radius_key = f"circle:{ref.entity_id}:radius"
            return center + [scalars[radius_key] - _as_float(entity.data["radius"])]
        raise ValueError(f"Cannot fix sketch entity kind '{entity.kind}'")

    def _point(self, ref: SketchRef, points: Mapping[str, Tuple[float, float]]) -> Tuple[float, float]:
        return points[self.sketch.resolve_point_id(ref)]

    def _line_points(
        self, ref: SketchRef, points: Mapping[str, Tuple[float, float]]
    ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        entity = self.sketch.entities[ref.entity_id]
        if entity.kind != "line":
            raise ValueError(f"Expected line ref, got '{entity.kind}'")
        return points[str(entity.data["start"])], points[str(entity.data["end"])]

    def _circle_center(self, ref: SketchRef, points: Mapping[str, Tuple[float, float]]) -> Tuple[float, float]:
        entity = self.sketch.entities[ref.entity_id]
        if entity.kind != "circle":
            raise ValueError(f"Expected circle ref, got '{entity.kind}'")
        return points[str(entity.data["center"])]

    def _circle_radius(self, ref: SketchRef, scalars: Mapping[str, float]) -> float:
        entity = self.sketch.entities[ref.entity_id]
        if entity.kind != "circle":
            raise ValueError(f"Expected circle ref, got '{entity.kind}'")
        return scalars[f"circle:{ref.entity_id}:radius"]

    def _point_distance(
        self, a: SketchRef, b: SketchRef, points: Mapping[str, Tuple[float, float]]
    ) -> float:
        return self._norm(self._sub(self._point(b, points), self._point(a, points)))

    def _line_length(self, ref: SketchRef, points: Mapping[str, Tuple[float, float]]) -> float:
        a, b = self._line_points(ref, points)
        return self._norm(self._sub(b, a))

    def _cross_normalized(self, a_ref: SketchRef, b_ref: SketchRef, points: Mapping[str, Tuple[float, float]]) -> float:
        a0, a1 = self._line_points(a_ref, points)
        b0, b1 = self._line_points(b_ref, points)
        a = self._sub(a1, a0)
        b = self._sub(b1, b0)
        return self._cross(a, b) / max(self._norm(a) * self._norm(b), _POINT_EPS)

    def _dot_normalized(self, a_ref: SketchRef, b_ref: SketchRef, points: Mapping[str, Tuple[float, float]]) -> float:
        a0, a1 = self._line_points(a_ref, points)
        b0, b1 = self._line_points(b_ref, points)
        a = self._sub(a1, a0)
        b = self._sub(b1, b0)
        return self._dot(a, b) / max(self._norm(a) * self._norm(b), _POINT_EPS)

    def _line_angle_delta(
        self,
        a_ref: SketchRef,
        b_ref: SketchRef,
        points: Mapping[str, Tuple[float, float]],
        target: float,
    ) -> float:
        a0, a1 = self._line_points(a_ref, points)
        b0, b1 = self._line_points(b_ref, points)
        a = self._sub(a1, a0)
        b = self._sub(b1, b0)
        angle = math.atan2(self._cross(a, b), self._dot(a, b))
        return _angle_delta(angle - target)

    def _point_on_residuals(
        self,
        point_ref: SketchRef,
        entity_ref: SketchRef,
        points: Mapping[str, Tuple[float, float]],
        scalars: Mapping[str, float],
    ) -> List[float]:
        point = self._point(point_ref, points)
        entity = self.sketch.entities[entity_ref.entity_id]
        if entity.kind == "line":
            return [self._point_line_distance(point, entity_ref, points)]
        if entity.kind == "circle":
            center = self._circle_center(entity_ref, points)
            radius = self._circle_radius(entity_ref, scalars)
            return [self._norm(self._sub(point, center)) - radius]
        raise ValueError(f"Unsupported point_on target kind '{entity.kind}'")

    def _point_line_distance(
        self,
        point: Tuple[float, float],
        line_ref: SketchRef,
        points: Mapping[str, Tuple[float, float]],
    ) -> float:
        a, b = self._line_points(line_ref, points)
        ab = self._sub(b, a)
        return self._cross(self._sub(point, a), ab) / max(self._norm(ab), _POINT_EPS)

    def _tangent_residual(
        self,
        a_ref: SketchRef,
        b_ref: SketchRef,
        points: Mapping[str, Tuple[float, float]],
        scalars: Mapping[str, float],
    ) -> float:
        a_kind = self.sketch.entities[a_ref.entity_id].kind
        b_kind = self.sketch.entities[b_ref.entity_id].kind
        if {a_kind, b_kind} == {"line", "circle"}:
            line_ref = a_ref if a_kind == "line" else b_ref
            circle_ref = b_ref if a_kind == "line" else a_ref
            center = self._circle_center(circle_ref, points)
            return abs(self._point_line_distance(center, line_ref, points)) - self._circle_radius(circle_ref, scalars)
        if a_kind == "circle" and b_kind == "circle":
            a_center = self._circle_center(a_ref, points)
            b_center = self._circle_center(b_ref, points)
            return self._norm(self._sub(a_center, b_center)) - (
                self._circle_radius(a_ref, scalars) + self._circle_radius(b_ref, scalars)
            )
        raise ValueError(f"Unsupported tangent target kinds '{a_kind}' and '{b_kind}'")

    @staticmethod
    def _sub(a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
        return (float(a[0] - b[0]), float(a[1] - b[1]))

    @staticmethod
    def _dot(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return float(a[0] * b[0] + a[1] * b[1])

    @staticmethod
    def _cross(a: Tuple[float, float], b: Tuple[float, float]) -> float:
        return float(a[0] * b[1] - a[1] * b[0])

    @staticmethod
    def _norm(a: Tuple[float, float]) -> float:
        return float(math.hypot(a[0], a[1]))


__all__ = [
    "Sketch",
    "SketchRef",
    "SketchSolveResult",
    "SketchConstraint",
    "SketchConstraintDiagnostic",
]
