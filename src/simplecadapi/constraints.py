"""Declarative assembly constraints module.

This module adds an optional assembly tree and constraint-solving layer on top of
the existing imperative modeling API, allowing imperative and declarative usage
to be mixed.

The current version focuses on rigid-body pose solving without modifying part
topology, and supports:
- assembly trees (parent/child hierarchy and local/world transforms)
- coincident, concentric, axial offset, and point-distance constraints
- one-dimensional stack layout
"""

from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from typing import Dict, List, Literal, Optional, Sequence, Tuple, Union
import math

import cadquery as cq
import numpy as np
from OCP.gp import gp_Trsf

from .core import Solid, Face
from .tagging import resolve_anchor_tag_candidates


Vec3Like = Union[Tuple[float, float, float], List[float], np.ndarray]
AxisLike = Union[str, Vec3Like]


def _as_vec3(vector: Vec3Like, name: str = "vector") -> np.ndarray:
    arr = np.asarray(vector, dtype=float)
    if arr.shape != (3,):
        raise ValueError(f"{name} 必须是长度为3的向量")
    return arr


def _normalize(vector: Vec3Like, name: str = "vector") -> np.ndarray:
    arr = _as_vec3(vector, name)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError(f"{name} 不能是零向量")
    return arr / norm


def _identity4() -> np.ndarray:
    return np.eye(4, dtype=float)


def _translation_matrix(vector: Vec3Like) -> np.ndarray:
    mat = _identity4()
    mat[:3, 3] = _as_vec3(vector, "translation")
    return mat


def _rotation_matrix_axis_angle(
    axis: Vec3Like,
    angle_deg: float,
    origin: Vec3Like = (0.0, 0.0, 0.0),
) -> np.ndarray:
    k = _normalize(axis, "axis")
    theta = math.radians(float(angle_deg))
    if abs(theta) <= 1e-12:
        return _identity4()

    kx, ky, kz = k
    skew = np.array(
        [
            [0.0, -kz, ky],
            [kz, 0.0, -kx],
            [-ky, kx, 0.0],
        ],
        dtype=float,
    )
    r = (
        np.eye(3, dtype=float)
        + math.sin(theta) * skew
        + (1.0 - math.cos(theta)) * (skew @ skew)
    )

    o = _as_vec3(origin, "origin")
    mat = _identity4()
    mat[:3, :3] = r
    mat[:3, 3] = o - r @ o
    return mat


def _transform_point(transform: np.ndarray, point: Vec3Like) -> np.ndarray:
    p = _as_vec3(point, "point")
    return transform[:3, :3] @ p + transform[:3, 3]


def _transform_vector(transform: np.ndarray, vector: Vec3Like) -> np.ndarray:
    v = _as_vec3(vector, "vector")
    return transform[:3, :3] @ v


def _axis_name_to_unit(axis: AxisLike) -> np.ndarray:
    if isinstance(axis, str):
        token = axis.lower().strip()
        if token == "x":
            return np.array([1.0, 0.0, 0.0], dtype=float)
        if token == "y":
            return np.array([0.0, 1.0, 0.0], dtype=float)
        if token == "z":
            return np.array([0.0, 0.0, 1.0], dtype=float)
        raise ValueError("axis 字符串仅支持 'x'/'y'/'z'")
    return _normalize(axis, "axis")


def _axis_index(axis: str) -> int:
    token = axis.lower().strip()
    if token == "x":
        return 0
    if token == "y":
        return 1
    if token == "z":
        return 2
    raise ValueError("axis 仅支持 'x'/'y'/'z'")


def _rotation_from_to(source_dir: Vec3Like, target_dir: Vec3Like) -> np.ndarray:
    a = _normalize(source_dir, "source_dir")
    b = _normalize(target_dir, "target_dir")

    dot_ab = float(np.dot(a, b))
    dot_ab = max(-1.0, min(1.0, dot_ab))

    if dot_ab >= 1.0 - 1e-12:
        return np.eye(3, dtype=float)

    if dot_ab <= -1.0 + 1e-12:
        # 180度旋转，选择与a不平行的向量构造旋转轴
        basis = np.array([1.0, 0.0, 0.0], dtype=float)
        if abs(float(np.dot(a, basis))) > 0.9:
            basis = np.array([0.0, 1.0, 0.0], dtype=float)
        axis = _normalize(np.cross(a, basis), "rotation_axis")
        return _rotation_matrix_axis_angle(axis, 180.0)[:3, :3]

    v = np.cross(a, b)
    s = float(np.linalg.norm(v))
    vx = np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ],
        dtype=float,
    )
    r = np.eye(3, dtype=float) + vx + (vx @ vx) * ((1.0 - dot_ab) / (s * s))
    return r


def _rotation_about_point_matrix(rotation: np.ndarray, point: Vec3Like) -> np.ndarray:
    p = _as_vec3(point, "point")
    mat = _identity4()
    mat[:3, :3] = rotation
    mat[:3, 3] = p - rotation @ p
    return mat


@dataclass(frozen=True)
class PointAnchor:
    """Point anchor defined in a part's local coordinate system."""

    part: str
    local_point: Tuple[float, float, float]
    label: str = ""


@dataclass(frozen=True)
class AxisAnchor:
    """Axis anchor defined in a part's local coordinate system: point + direction."""

    part: str
    local_point: Tuple[float, float, float]
    local_direction: Tuple[float, float, float]
    label: str = ""


@dataclass(frozen=True)
class SolveReport:
    """Solve report."""

    converged: bool
    iterations: int
    max_delta: float
    diagnostics: Tuple[str, ...] = ()


@dataclass
class _PartNode:
    name: str
    solid: Solid
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    local_transform: np.ndarray = field(default_factory=_identity4)
    _world_cache: Optional[np.ndarray] = None
    _dirty: bool = True


class PartHandle:
    """Handle for a part in an assembly, used to create anchors."""

    def __init__(self, assembly: "Assembly", name: str):
        self._assembly = assembly
        self.name = name

    def point(self, point: Vec3Like, label: str = "") -> PointAnchor:
        p = _as_vec3(point, "point")
        return PointAnchor(self.name, (float(p[0]), float(p[1]), float(p[2])), label)

    def axis(
        self,
        axis: AxisLike = "z",
        through: Union[str, PointAnchor, Vec3Like] = "bbox.center",
        label: str = "",
    ) -> AxisAnchor:
        direction = _axis_name_to_unit(axis)

        if isinstance(through, str):
            point_anchor = self.anchor(through)
            local_point = np.asarray(point_anchor.local_point, dtype=float)
        elif isinstance(through, PointAnchor):
            if through.part != self.name:
                raise ValueError("through 锚点必须属于同一个零件")
            local_point = np.asarray(through.local_point, dtype=float)
        else:
            local_point = _as_vec3(through, "through")

        return AxisAnchor(
            self.name,
            (float(local_point[0]), float(local_point[1]), float(local_point[2])),
            (float(direction[0]), float(direction[1]), float(direction[2])),
            label,
        )

    def bbox(self, where: str = "center") -> PointAnchor:
        local_point = self._assembly._bbox_point(self.name, where)
        return PointAnchor(
            self.name,
            (float(local_point[0]), float(local_point[1]), float(local_point[2])),
            f"bbox.{where}",
        )

    def face_center(self, tag: str) -> PointAnchor:
        face = self._assembly._find_tagged_face(self.name, tag)
        center = face.get_center()
        return PointAnchor(self.name, (center.x, center.y, center.z), f"face:{tag}")

    def face_axis(self, tag: str) -> AxisAnchor:
        face = self._assembly._find_tagged_face(self.name, tag)
        center = face.get_center()
        normal = face.get_normal_at()
        direction = _normalize((normal.x, normal.y, normal.z), f"face:{tag}.normal")
        return AxisAnchor(
            self.name,
            (center.x, center.y, center.z),
            (float(direction[0]), float(direction[1]), float(direction[2])),
            f"face-axis:{tag}",
        )

    def anchor(self, name: str) -> PointAnchor:
        raw = name.strip()
        token = raw.lower()
        if token == "origin":
            return self.point((0.0, 0.0, 0.0), "origin")
        if token.startswith("bbox."):
            return self.bbox(raw.split(".", 1)[1])
        if token.startswith("face:"):
            return self.face_center(raw.split(":", 1)[1])
        raise ValueError("不支持的锚点名称。支持: origin, bbox.*, face:<tag>")


class _Constraint:
    def apply(self, assembly: "Assembly") -> float:
        raise NotImplementedError

    def involved_parts(self) -> Tuple[str, ...]:
        raise NotImplementedError


@dataclass
class _CoincidentConstraint(_Constraint):
    reference: PointAnchor
    moving: PointAnchor

    def apply(self, assembly: "Assembly") -> float:
        ref = assembly._eval_point(self.reference)
        mov = assembly._eval_point(self.moving)
        delta = ref - mov
        norm = float(np.linalg.norm(delta))
        if norm <= 1e-10:
            return 0.0
        assembly._apply_world_delta(self.moving.part, _translation_matrix(delta))
        return norm

    def involved_parts(self) -> Tuple[str, ...]:
        return (self.reference.part, self.moving.part)


@dataclass
class _ConcentricConstraint(_Constraint):
    reference: AxisAnchor
    moving: AxisAnchor
    same_direction: bool = False

    def apply(self, assembly: "Assembly") -> float:
        ref_point, ref_dir = assembly._eval_axis(self.reference)
        mov_point, mov_dir = assembly._eval_axis(self.moving)

        target_dir = ref_dir.copy()
        dot_md = float(np.dot(mov_dir, ref_dir))
        if not self.same_direction and dot_md < 0.0:
            target_dir = -target_dir

        r_align = _rotation_from_to(mov_dir, target_dir)
        dot_for_angle = dot_md if self.same_direction else abs(dot_md)
        angle_before = math.degrees(math.acos(max(-1.0, min(1.0, dot_for_angle))))

        if not np.allclose(r_align, np.eye(3), atol=1e-10):
            rot_delta = _rotation_about_point_matrix(r_align, mov_point)
            assembly._apply_world_delta(self.moving.part, rot_delta)

        mov_point2, _ = assembly._eval_axis(self.moving)
        along = float(np.dot(ref_point - mov_point2, target_dir))
        translation = (ref_point - mov_point2) - target_dir * along

        shift_norm = float(np.linalg.norm(translation))
        if shift_norm > 1e-10:
            assembly._apply_world_delta(
                self.moving.part, _translation_matrix(translation)
            )

        return max(angle_before, shift_norm)

    def involved_parts(self) -> Tuple[str, ...]:
        return (self.reference.part, self.moving.part)


@dataclass
class _AxisOffsetConstraint(_Constraint):
    reference: PointAnchor
    moving: PointAnchor
    axis: Tuple[float, float, float]
    distance: float

    def apply(self, assembly: "Assembly") -> float:
        axis_unit = _normalize(self.axis, "offset_axis")
        ref = assembly._eval_point(self.reference)
        mov = assembly._eval_point(self.moving)

        current = float(np.dot(mov - ref, axis_unit))
        delta = float(self.distance) - current
        if abs(delta) <= 1e-10:
            return 0.0

        assembly._apply_world_delta(
            self.moving.part, _translation_matrix(axis_unit * delta)
        )
        return abs(delta)

    def involved_parts(self) -> Tuple[str, ...]:
        return (self.reference.part, self.moving.part)


@dataclass
class _PointDistanceConstraint(_Constraint):
    reference: PointAnchor
    moving: PointAnchor
    distance: float
    fallback_axis: Tuple[float, float, float] = (1.0, 0.0, 0.0)

    def apply(self, assembly: "Assembly") -> float:
        ref = assembly._eval_point(self.reference)
        mov = assembly._eval_point(self.moving)

        vec = mov - ref
        current = float(np.linalg.norm(vec))
        if current <= 1e-12:
            direction = _normalize(self.fallback_axis, "fallback_axis")
        else:
            direction = vec / current

        delta = float(self.distance) - current
        if abs(delta) <= 1e-10:
            return 0.0

        assembly._apply_world_delta(
            self.moving.part, _translation_matrix(direction * delta)
        )
        return abs(delta)

    def involved_parts(self) -> Tuple[str, ...]:
        return (self.reference.part, self.moving.part)


class AssemblyResult:
    """Immutable snapshot of a solved assembly."""

    def __init__(
        self,
        transforms: Dict[str, np.ndarray],
        solids: Dict[str, Solid],
        report: SolveReport,
    ):
        self._transforms = {k: v.copy() for k, v in transforms.items()}
        self._solids = dict(solids)
        self.report = report

    def part_names(self) -> List[str]:
        return list(self._solids.keys())

    def solids(self) -> List[Solid]:
        return [self._solids[name] for name in self.part_names()]

    def get_solid(self, name: str) -> Solid:
        if name not in self._solids:
            raise KeyError(f"未知零件: {name}")
        return self._solids[name]

    def get_transform(self, name: str) -> np.ndarray:
        if name not in self._transforms:
            raise KeyError(f"未知零件: {name}")
        return self._transforms[name].copy()


class Assembly:
    """Declarative assembly tree.

    Design goals:
    - coexist with the imperative API
    - allow coarse positioning with imperative transforms, then refine it with
      declarative constraints
    """

    def __init__(self, name: str = "assembly"):
        self.name = name
        self._parts: Dict[str, _PartNode] = {}
        self._order: List[str] = []
        self._constraints: List[_Constraint] = []

    def copy(self) -> "Assembly":
        """Deep-copy the current assembly object."""

        copied = Assembly(self.name)
        copied._order = list(self._order)

        for name in self._order:
            node = self._parts[name]
            copied._parts[name] = _PartNode(
                name=node.name,
                solid=node.solid,
                parent=node.parent,
                children=list(node.children),
                local_transform=node.local_transform.copy(),
                _world_cache=(
                    None if node._world_cache is None else node._world_cache.copy()
                ),
                _dirty=node._dirty,
            )

        copied._constraints = deepcopy(self._constraints)
        return copied

    def add_part(
        self,
        name: str,
        solid: Solid,
        parent: Optional[Union[str, PartHandle]] = None,
        local_transform: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
    ) -> PartHandle:
        if not name:
            raise ValueError("零件名称不能为空")
        if name in self._parts:
            raise ValueError(f"零件已存在: {name}")
        if not isinstance(solid, Solid):
            raise ValueError("add_part 仅支持 Solid 类型")

        parent_name: Optional[str] = None
        if parent is not None:
            parent_name = self._resolve_part_name(parent)
            if parent_name not in self._parts:
                raise ValueError(f"父零件不存在: {parent_name}")

        if local_transform is None:
            mat = _identity4()
        else:
            mat = np.asarray(local_transform, dtype=float)
            if mat.shape != (4, 4):
                raise ValueError("local_transform 必须是 4x4 矩阵")

        self._parts[name] = _PartNode(
            name=name,
            solid=solid,
            parent=parent_name,
            local_transform=mat,
        )
        self._order.append(name)

        if parent_name is not None:
            self._parts[parent_name].children.append(name)

        self._mark_dirty_subtree(name)
        return PartHandle(self, name)

    def part(self, part: Union[str, PartHandle]) -> PartHandle:
        name = self._resolve_part_name(part)
        if name not in self._parts:
            raise ValueError(f"零件不存在: {name}")
        return PartHandle(self, name)

    def part_names(self) -> List[str]:
        return list(self._order)

    def clear_constraints(self) -> "Assembly":
        self._constraints.clear()
        return self

    # ------------------------------------------------------------------
    # imperative API
    # ------------------------------------------------------------------
    def translate_part(
        self,
        part: Union[str, PartHandle],
        vector: Vec3Like,
        frame: Literal["world", "local"] = "world",
    ) -> "Assembly":
        name = self._resolve_part_name(part)
        delta = _translation_matrix(vector)
        if frame == "world":
            self._apply_world_delta(name, delta)
        elif frame == "local":
            node = self._parts[name]
            node.local_transform = delta @ node.local_transform
            self._mark_dirty_subtree(name)
        else:
            raise ValueError("frame 仅支持 'world' 或 'local'")
        return self

    def rotate_part(
        self,
        part: Union[str, PartHandle],
        angle_deg: float,
        axis: AxisLike = "z",
        origin: Vec3Like = (0.0, 0.0, 0.0),
        frame: Literal["world", "local"] = "world",
    ) -> "Assembly":
        name = self._resolve_part_name(part)
        delta = _rotation_matrix_axis_angle(_axis_name_to_unit(axis), angle_deg, origin)
        if frame == "world":
            self._apply_world_delta(name, delta)
        elif frame == "local":
            node = self._parts[name]
            node.local_transform = delta @ node.local_transform
            self._mark_dirty_subtree(name)
        else:
            raise ValueError("frame 仅支持 'world' 或 'local'")
        return self

    # ------------------------------------------------------------------
    # declarative constraints
    # ------------------------------------------------------------------
    def coincident(self, reference: PointAnchor, moving: PointAnchor) -> "Assembly":
        self._constraints.append(_CoincidentConstraint(reference, moving))
        return self

    def concentric(
        self,
        reference: AxisAnchor,
        moving: AxisAnchor,
        same_direction: bool = False,
    ) -> "Assembly":
        self._constraints.append(
            _ConcentricConstraint(reference, moving, same_direction=same_direction)
        )
        return self

    def offset(
        self,
        reference: PointAnchor,
        moving: PointAnchor,
        distance: float,
        axis: AxisLike = "z",
    ) -> "Assembly":
        axis_vec = _axis_name_to_unit(axis)
        self._constraints.append(
            _AxisOffsetConstraint(
                reference=reference,
                moving=moving,
                axis=(float(axis_vec[0]), float(axis_vec[1]), float(axis_vec[2])),
                distance=float(distance),
            )
        )
        return self

    def distance(
        self,
        reference: PointAnchor,
        moving: PointAnchor,
        distance: float,
        fallback_axis: AxisLike = "x",
    ) -> "Assembly":
        fb = _axis_name_to_unit(fallback_axis)
        self._constraints.append(
            _PointDistanceConstraint(
                reference=reference,
                moving=moving,
                distance=float(distance),
                fallback_axis=(float(fb[0]), float(fb[1]), float(fb[2])),
            )
        )
        return self

    def solve(
        self,
        max_iterations: int = 30,
        tolerance: float = 1e-6,
    ) -> AssemblyResult:
        if max_iterations <= 0:
            raise ValueError("max_iterations 必须大于0")
        if tolerance <= 0:
            raise ValueError("tolerance 必须大于0")

        converged = True
        max_delta = 0.0
        iterations = 0
        diagnostics: List[str] = []

        if self._constraints:
            converged = False
            for i in range(1, max_iterations + 1):
                iterations = i
                max_delta = 0.0
                for constraint in self._constraints:
                    delta = float(constraint.apply(self))
                    if not math.isfinite(delta):
                        raise ValueError("约束求解出现非有限数值，请检查约束定义")
                    max_delta = max(max_delta, delta)

                if max_delta <= tolerance:
                    converged = True
                    break

            if not converged:
                diagnostics.append(
                    f"约束求解未在 {max_iterations} 次迭代内收敛，当前最大残差约为 {max_delta:.6g}"
                )

            constrained_parts = {
                part_name
                for constraint in self._constraints
                for part_name in constraint.involved_parts()
            }
            for name in self._order:
                if name not in constrained_parts:
                    diagnostics.append(
                        f"零件 '{name}' 未被任何约束引用，将保持当前位姿"
                    )

        transforms = {name: self._world_transform(name).copy() for name in self._order}
        solids = {
            name: self._transform_solid_with_world_transform(
                self._parts[name].solid, transforms[name]
            )
            for name in self._order
        }

        report = SolveReport(
            converged=converged,
            iterations=iterations,
            max_delta=max_delta,
            diagnostics=tuple(diagnostics),
        )
        return AssemblyResult(transforms=transforms, solids=solids, report=report)

    # ------------------------------------------------------------------
    # internal tree / transform helpers
    # ------------------------------------------------------------------
    def _resolve_part_name(self, part: Union[str, PartHandle]) -> str:
        if isinstance(part, PartHandle):
            return part.name
        if not isinstance(part, str):
            raise ValueError("part 只能是零件名字符串或 PartHandle")
        return part

    def _mark_dirty_subtree(self, name: str) -> None:
        node = self._parts[name]
        node._dirty = True
        node._world_cache = None
        for child in node.children:
            self._mark_dirty_subtree(child)

    def _world_transform(self, name: str) -> np.ndarray:
        node = self._parts[name]
        if not node._dirty and node._world_cache is not None:
            return node._world_cache

        if node.parent is None:
            world = node.local_transform
        else:
            world = self._world_transform(node.parent) @ node.local_transform

        node._world_cache = world
        node._dirty = False
        return world

    def _apply_world_delta(self, name: str, world_delta: np.ndarray) -> None:
        if world_delta.shape != (4, 4):
            raise ValueError("world_delta 必须是 4x4 矩阵")

        node = self._parts[name]
        if node.parent is None:
            node.local_transform = world_delta @ node.local_transform
        else:
            parent_world = self._world_transform(node.parent)
            parent_inv = np.linalg.inv(parent_world)
            local_delta = parent_inv @ world_delta @ parent_world
            node.local_transform = local_delta @ node.local_transform

        self._mark_dirty_subtree(name)

    # ------------------------------------------------------------------
    # internal anchor helpers
    # ------------------------------------------------------------------
    def _eval_point(self, anchor: PointAnchor) -> np.ndarray:
        if anchor.part not in self._parts:
            raise ValueError(f"锚点引用未知零件: {anchor.part}")
        world = self._world_transform(anchor.part)
        return _transform_point(world, anchor.local_point)

    def _eval_axis(self, anchor: AxisAnchor) -> Tuple[np.ndarray, np.ndarray]:
        if anchor.part not in self._parts:
            raise ValueError(f"锚点引用未知零件: {anchor.part}")
        world = self._world_transform(anchor.part)
        point = _transform_point(world, anchor.local_point)
        direction = _normalize(
            _transform_vector(world, anchor.local_direction), "axis_dir"
        )
        return point, direction

    def _bbox_point(self, part_name: str, where: str) -> np.ndarray:
        node = self._parts[part_name]
        bb = node.solid.cq_solid.BoundingBox()

        cx = 0.5 * (bb.xmin + bb.xmax)
        cy = 0.5 * (bb.ymin + bb.ymax)
        cz = 0.5 * (bb.zmin + bb.zmax)

        key = where.strip().lower()
        mapping: Dict[str, Tuple[float, float, float]] = {
            "center": (cx, cy, cz),
            "min": (bb.xmin, bb.ymin, bb.zmin),
            "max": (bb.xmax, bb.ymax, bb.zmax),
            "top": (cx, cy, bb.zmax),
            "bottom": (cx, cy, bb.zmin),
            "left": (bb.xmin, cy, cz),
            "right": (bb.xmax, cy, cz),
            "front": (cx, bb.ymax, cz),
            "back": (cx, bb.ymin, cz),
        }

        if key not in mapping:
            raise ValueError(
                "bbox 锚点仅支持: center/min/max/top/bottom/left/right/front/back"
            )
        return np.asarray(mapping[key], dtype=float)

    def _part_span_along_axis_local(self, part_name: str, axis: str) -> float:
        node = self._parts[part_name]
        bb = node.solid.cq_solid.BoundingBox()
        token = axis.lower().strip()
        if token == "x":
            return float(bb.xmax - bb.xmin)
        if token == "y":
            return float(bb.ymax - bb.ymin)
        if token == "z":
            return float(bb.zmax - bb.zmin)
        raise ValueError("axis 仅支持 'x'/'y'/'z'")

    def _find_tagged_face(self, part_name: str, tag: str) -> Face:
        node = self._parts[part_name]
        candidates = resolve_anchor_tag_candidates(tag)
        for candidate in candidates:
            faces = [face for face in node.solid.get_faces() if face.has_tag(candidate)]
            if faces:
                return faces[0]
        raise ValueError(
            f"零件 '{part_name}' 未找到标签为 '{tag}' 的面，请先执行 auto_tag_faces() 或手动打标签"
        )

    # ------------------------------------------------------------------
    # output helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _transform_solid_with_world_transform(
        solid: Solid, transform: np.ndarray
    ) -> Solid:
        if transform.shape != (4, 4):
            raise ValueError("transform 必须是 4x4 矩阵")

        tr = gp_Trsf()
        tr.SetValues(
            float(transform[0, 0]),
            float(transform[0, 1]),
            float(transform[0, 2]),
            float(transform[0, 3]),
            float(transform[1, 0]),
            float(transform[1, 1]),
            float(transform[1, 2]),
            float(transform[1, 3]),
            float(transform[2, 0]),
            float(transform[2, 1]),
            float(transform[2, 2]),
            float(transform[2, 3]),
        )

        transformed_cq = solid.cq_solid.located(cq.Location(tr))
        transformed = Solid(transformed_cq)
        transformed._tags = solid._tags.copy()
        transformed._metadata = solid._metadata.copy()
        return transformed


def make_assembly_rassembly(
    parts: Sequence[Tuple[str, Solid]],
    name: str = "assembly",
    parents: Optional[Dict[str, str]] = None,
    local_transforms: Optional[
        Dict[str, Union[np.ndarray, Sequence[Sequence[float]]]]
    ] = None,
) -> Assembly:
    """Type-1 mapping: lift a parameter description into an assembly object."""

    asm = Assembly(name=name)
    parent_map = dict(parents or {})
    transform_map = dict(local_transforms or {})

    pending: Dict[str, Solid] = {}
    for part_name, solid in parts:
        if part_name in pending:
            raise ValueError(f"重复零件名: {part_name}")
        pending[part_name] = solid

    while pending:
        progressed = False
        for part_name, solid in list(pending.items()):
            parent_name = parent_map.get(part_name)
            if parent_name is not None and parent_name not in asm._parts:
                continue

            asm.add_part(
                part_name,
                solid,
                parent=parent_name,
                local_transform=transform_map.get(part_name),
            )
            del pending[part_name]
            progressed = True

        if not progressed:
            unresolved = ", ".join(sorted(pending.keys()))
            raise ValueError(
                f"无法解析父子关系（可能父节点缺失或存在循环依赖）: {unresolved}"
            )

    return asm


def clone_assembly_rassembly(assembly: Assembly) -> Assembly:
    """Type-2 mapping: clone one assembly object into another."""

    if not isinstance(assembly, Assembly):
        raise ValueError("clone_assembly_rassembly 仅接受 Assembly")
    return assembly.copy()


def add_part_rassembly(
    assembly: Assembly,
    name: str,
    solid: Solid,
    parent: Optional[Union[str, PartHandle]] = None,
    local_transform: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None,
) -> Assembly:
    """Type-2 mapping: add a part in assembly space and return a new assembly."""

    copied = assembly.copy()
    copied.add_part(name, solid, parent=parent, local_transform=local_transform)
    return copied


def clear_constraints_rassembly(assembly: Assembly) -> Assembly:
    """Type-2 mapping: clear constraints and return a new assembly."""

    copied = assembly.copy()
    copied.clear_constraints()
    return copied


def translate_part_rassembly(
    assembly: Assembly,
    part: Union[str, PartHandle],
    vector: Vec3Like,
    frame: Literal["world", "local"] = "world",
) -> Assembly:
    """Type-2 mapping: translate a part and return a new assembly."""

    copied = assembly.copy()
    copied.translate_part(part, vector, frame=frame)
    return copied


def rotate_part_rassembly(
    assembly: Assembly,
    part: Union[str, PartHandle],
    angle_deg: float,
    axis: AxisLike = "z",
    origin: Vec3Like = (0.0, 0.0, 0.0),
    frame: Literal["world", "local"] = "world",
) -> Assembly:
    """Type-2 mapping: rotate a part and return a new assembly."""

    copied = assembly.copy()
    copied.rotate_part(part, angle_deg, axis=axis, origin=origin, frame=frame)
    return copied


def constrain_coincident_rassembly(
    assembly: Assembly,
    reference: PointAnchor,
    moving: PointAnchor,
) -> Assembly:
    """Type-2 mapping: add a coincident constraint and return a new assembly."""

    copied = assembly.copy()
    copied.coincident(reference, moving)
    return copied


def constrain_concentric_rassembly(
    assembly: Assembly,
    reference: AxisAnchor,
    moving: AxisAnchor,
    same_direction: bool = False,
) -> Assembly:
    """Type-2 mapping: add a concentric constraint and return a new assembly."""

    copied = assembly.copy()
    copied.concentric(reference, moving, same_direction=same_direction)
    return copied


def constrain_offset_rassembly(
    assembly: Assembly,
    reference: PointAnchor,
    moving: PointAnchor,
    distance: float,
    axis: AxisLike = "z",
) -> Assembly:
    """Type-2 mapping: add an axial offset constraint and return a new assembly."""

    copied = assembly.copy()
    copied.offset(reference, moving, distance, axis=axis)
    return copied


def constrain_distance_rassembly(
    assembly: Assembly,
    reference: PointAnchor,
    moving: PointAnchor,
    distance: float,
    fallback_axis: AxisLike = "x",
) -> Assembly:
    """Type-2 mapping: add a point-distance constraint and return a new assembly."""

    copied = assembly.copy()
    copied.distance(reference, moving, distance, fallback_axis=fallback_axis)
    return copied


def stack_rassembly(
    assembly: Assembly,
    parts: Sequence[Union[str, PartHandle]],
    axis: str = "z",
    gap: float = 0.0,
    align: Literal["center", "start", "end"] = "center",
    justify: Literal["start", "center", "end", "space-between"] = "start",
    bounds: Optional[Tuple[PointAnchor, PointAnchor]] = None,
) -> Assembly:
    """Type-2 mapping: apply a stack layout and return a new assembly."""

    copied = assembly.copy()
    stack(
        copied,
        parts=parts,
        axis=axis,
        gap=gap,
        align=align,
        justify=justify,
        bounds=bounds,
    )
    return copied


def solve_assembly_rresult(
    assembly: Assembly,
    max_iterations: int = 30,
    tolerance: float = 1e-6,
) -> AssemblyResult:
    """Type-2 mapping: map an assembly to a solve result without mutating it."""

    copied = assembly.copy()
    return copied.solve(max_iterations=max_iterations, tolerance=tolerance)


def stack(
    assembly: Assembly,
    parts: Sequence[Union[str, PartHandle]],
    axis: str = "z",
    gap: float = 0.0,
    align: Literal["center", "start", "end"] = "center",
    justify: Literal["start", "center", "end", "space-between"] = "start",
    bounds: Optional[Tuple[PointAnchor, PointAnchor]] = None,
) -> Assembly:
    """Declaratively stack multiple parts along the specified axis.

    Semantics:
    - sequential stacking: part i is placed after part i-1 with the given gap
    - cross-axis alignment: the other two axes are aligned according to `align`
    - main-axis distribution: `justify` controls how the whole stack is placed
      within the bounds

    BBox-first note:
    - This function uses axis-aligned bounding-box (AABB) anchors such as
      `bbox.top` and `bbox.bottom` to approximate Flexbox-like box semantics.
    - For parts with large rotations, the AABB changes with pose, so the layout
      result changes as well. This is expected in the current MVP stage.

    Note:
    - This is container-level sugar that compiles into a set of `offset(...)`
      constraints internally.
    """

    names: List[str] = [assembly._resolve_part_name(part) for part in parts]
    if len(names) <= 1:
        return assembly

    axis_token = axis.lower().strip()
    _axis_index(axis_token)

    if gap < 0:
        raise ValueError("gap 必须大于等于0")
    if align not in {"center", "start", "end"}:
        raise ValueError("align 仅支持 'center'/'start'/'end'")
    if justify not in {"start", "center", "end", "space-between"}:
        raise ValueError("justify 仅支持 'start'/'center'/'end'/'space-between'")

    min_anchor = {"x": "bbox.left", "y": "bbox.back", "z": "bbox.bottom"}
    max_anchor = {"x": "bbox.right", "y": "bbox.front", "z": "bbox.top"}

    if justify in {"center", "end", "space-between"} and bounds is None:
        raise ValueError("justify 为 center/end/space-between 时必须提供 bounds")

    effective_gap = float(gap)
    lead_space = 0.0
    start_anchor: Optional[PointAnchor] = None

    if bounds is not None:
        start_anchor, end_anchor = bounds
        axis_unit = _axis_name_to_unit(axis_token)
        start_point = assembly._eval_point(start_anchor)
        end_point = assembly._eval_point(end_anchor)
        available_span = float(np.dot(end_point - start_point, axis_unit))

        if available_span < -1e-9:
            raise ValueError("bounds 的结束锚点必须位于开始锚点的主轴正方向")

        total_parts_span = sum(
            assembly._part_span_along_axis_local(name, axis_token) for name in names
        )

        if justify == "space-between":
            if len(names) == 1:
                effective_gap = 0.0
            else:
                effective_gap = (available_span - total_parts_span) / float(
                    len(names) - 1
                )
            if effective_gap < -1e-9:
                raise ValueError("bounds 空间不足，无法满足 space-between 布局")
            effective_gap = max(0.0, effective_gap)

        used_span = total_parts_span + effective_gap * float(len(names) - 1)
        if available_span + 1e-9 < used_span:
            raise ValueError("bounds 空间不足，无法容纳当前 stack 布局")

        remaining = max(0.0, available_span - used_span)
        if justify in {"start", "space-between"}:
            lead_space = 0.0
        elif justify == "center":
            lead_space = 0.5 * remaining
        else:  # justify == "end"
            lead_space = remaining

    for idx in range(1, len(names)):
        prev = assembly.part(names[idx - 1])
        curr = assembly.part(names[idx])

        assembly.offset(
            prev.anchor(max_anchor[axis_token]),
            curr.anchor(min_anchor[axis_token]),
            effective_gap,
            axis=axis_token,
        )

        for ortho_axis in [a for a in ("x", "y", "z") if a != axis_token]:
            if align == "center":
                assembly.offset(
                    prev.anchor("bbox.center"),
                    curr.anchor("bbox.center"),
                    0.0,
                    axis=ortho_axis,
                )
            elif align == "start":
                assembly.offset(
                    prev.anchor(min_anchor[ortho_axis]),
                    curr.anchor(min_anchor[ortho_axis]),
                    0.0,
                    axis=ortho_axis,
                )
            else:  # align == "end"
                assembly.offset(
                    prev.anchor(max_anchor[ortho_axis]),
                    curr.anchor(max_anchor[ortho_axis]),
                    0.0,
                    axis=ortho_axis,
                )

    if start_anchor is not None:
        first = assembly.part(names[0])
        assembly.offset(
            start_anchor,
            first.anchor(min_anchor[axis_token]),
            lead_space,
            axis=axis_token,
        )

    return assembly


__all__ = [
    "make_assembly_rassembly",
    "clone_assembly_rassembly",
    "add_part_rassembly",
    "clear_constraints_rassembly",
    "translate_part_rassembly",
    "rotate_part_rassembly",
    "constrain_coincident_rassembly",
    "constrain_concentric_rassembly",
    "constrain_offset_rassembly",
    "constrain_distance_rassembly",
    "stack_rassembly",
    "solve_assembly_rresult",
    "Assembly",
    "AssemblyResult",
    "SolveReport",
    "PartHandle",
    "PointAnchor",
    "AxisAnchor",
    "stack",
]
