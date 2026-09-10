#!/usr/bin/env python3
"""Decode WHUCAD vector sequences (h5 `vec` arrays) into feature objects.

Self-contained port of fazhihe/WHUCAD ``cadlib`` decode paths (numpy only —
no torch, no matplotlib). The decoded model is in the dataset's normalized
units (the released vectors are quantized to 256 levels after unit-cube
normalization); recovering the original absolute scale is impossible from the
vector alone, so downstream FTC output is scale-normalized and validation
compares shape, not absolute volume.

Conventions (verified against WHUCAD's own CATIA rebuild code):
    - quantized values: coordinates/lengths centered (v/256*2 - 1 → [-1, 1]);
      sketch size (v/256*2 → [0, 2]); angles full-range (v/256*2π or v/255*360);
      enum indices (extent type, operation, select/body type) NOT scaled.
    - profile 2D → real: denormalize(sketch_size): (p - 128) * size / 95,
      with 95 = 256/2 * NORM_FACTOR - 1 (the offset reverses normalize()'s
      centering of the profile start point at (128, 128)).
    - 3D assembly: origin = sketch_pos; p3 = origin + x_axis * px + y_axis * py.
    - revolve axis: OriginElements no=1 → sketch x axis (H), else y axis (V).

The decoder ONLY decodes — translation decisions live in whucad_to_ftc.py,
audit/acceptance in whucad_profile.py / whucad_validate.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# macro constants (verbatim from cadlib/macro.py)

ALL_COMMANDS = ['Line', 'Arc', 'Circle', 'Spline', 'SCP', 'EOS', 'SOL', 'Ext', 'Rev', 'Pocket',
                'Groove', 'Shell', 'Chamfer', 'Fillet', 'Draft', 'Mirror', 'Hole', 'Topo',
                'Select', 'MirrorStart', 'NoSharedIncluded', 'NoSharedIncludedEnd',
                'AllOrientedIncluded1', 'AllOrientedIncluded2', 'AllOrientedIncludedEnd',
                'AllPartiallySharedIncluded', 'AllPartiallySharedIncludedEnd']
LINE_IDX = ALL_COMMANDS.index('Line')
ARC_IDX = ALL_COMMANDS.index('Arc')
CIRCLE_IDX = ALL_COMMANDS.index('Circle')
SPLINE_IDX = ALL_COMMANDS.index('Spline')
SCP_IDX = ALL_COMMANDS.index('SCP')
EOS_IDX = ALL_COMMANDS.index('EOS')
SOL_IDX = ALL_COMMANDS.index('SOL')
EXT_IDX = ALL_COMMANDS.index('Ext')
REV_IDX = ALL_COMMANDS.index('Rev')
POCKET_IDX = ALL_COMMANDS.index('Pocket')
GROOVE_IDX = ALL_COMMANDS.index('Groove')
SHELL_IDX = ALL_COMMANDS.index('Shell')
CHAMFER_IDX = ALL_COMMANDS.index('Chamfer')
FILLET_IDX = ALL_COMMANDS.index('Fillet')
DRAFT_IDX = ALL_COMMANDS.index('Draft')
MIRROR_IDX = ALL_COMMANDS.index('Mirror')
HOLE_IDX = ALL_COMMANDS.index('Hole')
TOPO_IDX = ALL_COMMANDS.index('Topo')
SELECT_IDX = ALL_COMMANDS.index('Select')
MIRROR_START_IDX = ALL_COMMANDS.index('MirrorStart')

BOOLEAN_OPERATIONS = ["AddFeatureOperation", "CutFeatureOperation", "IntersectFeatureOperation"]
EXTENT_TYPE = ["OffsetLimit", "UpToNextLimit", "UpToLastLimit", "UpToPlaneLimit",
               "UpToSurfaceLimit", "UpThruNextLimit"]
SELECT_TYPE = ["Wire", "Face", "Edge", "Multiply_Face", "Sub_Face"]
BODY_TYPE = ["None", "OriginElements", "Sketch", "Pad", "Shaft", 'Pocket', "Add", "Remove",
             "Intersect", "Shell", "Chamfer", "EdgeFillet", "Mirror", "Hole"]

N_ARGS_SKETCH = 5
N_ARGS_PLANE = 3
N_ARGS_TRANS = 4
N_ARGS_BODY_PARAM = 7
N_ARGS_FINISH_PARAM = 9
N_ARGS_SELECT_PARAM = 4
N_ARGS_EXT = N_ARGS_PLANE + N_ARGS_TRANS + N_ARGS_BODY_PARAM
N_ARGS = N_ARGS_SKETCH + N_ARGS_EXT + N_ARGS_FINISH_PARAM + N_ARGS_SELECT_PARAM

ARGS_N = 256
NORM_FACTOR = 0.75
# normalize(size=256) maps the profile bbox to (128 * NORM_FACTOR - 1)
DENORM_SCALE_DENOM = ARGS_N / 2 * NORM_FACTOR - 1  # 95.0


def _denorm_centered(v: float, n: int = ARGS_N) -> float:
    return v / n * 2.0 - 1.0


def _denorm_size(v: float, n: int = ARGS_N) -> float:
    return v / n * 2.0


# ---------------------------------------------------------------------------
# geometry helpers (port of cadlib/Geometry_utils.py, the decode-relevant part)


def polar2cartesian(vec: Sequence[float]) -> np.ndarray:
    r = 1.0 if len(vec) == 2 else vec[2]
    theta, phi = vec[0], vec[1]
    return np.array([r * math.sin(theta) * math.cos(phi),
                     r * math.sin(theta) * math.sin(phi),
                     r * math.cos(theta)])


def rotate_by_y(vec: Sequence[float], theta: float) -> np.ndarray:
    v = np.asarray(vec, dtype=float)
    return np.array([v[0] * math.cos(theta) + v[2] * math.sin(theta),
                     v[1],
                     -v[0] * math.sin(theta) + v[2] * math.cos(theta)])


def rotate_by_z(vec: Sequence[float], phi: float) -> np.ndarray:
    v = np.asarray(vec, dtype=float)
    return np.array([v[0] * math.cos(phi) - v[1] * math.sin(phi),
                     v[0] * math.sin(phi) + v[1] * math.cos(phi),
                     v[2]])


def polar_parameterization_inverse(theta: float, phi: float, gamma: float):
    normal_3d = polar2cartesian([theta, phi])
    ref_x = rotate_by_z(rotate_by_y(np.array([1.0, 0.0, 0.0]), theta), phi)
    ref_y = np.cross(normal_3d, ref_x)
    x_axis_3d = ref_x * math.cos(gamma) + ref_y * math.sin(gamma)
    return normal_3d, x_axis_3d


def vec2arc(pos: Sequence[float], center: Sequence[float]) -> float:
    """Angle (0~2pi) of vector (pos - center) against the x axis."""
    vec = np.array([pos[0] - center[0], pos[1] - center[1]])
    length = np.linalg.norm(vec)
    if length == 0:
        return 0.0
    cos_x = vec[0] / length
    cos_y = vec[1] / length
    if cos_y > 0:
        return math.acos(max(-1.0, min(1.0, cos_x)))
    if cos_y < 0:
        return math.pi * 2 - math.acos(max(-1.0, min(1.0, cos_x)))
    return 0.0 if cos_x >= 0 else math.pi


# ---------------------------------------------------------------------------
# decoded curve model (quantized or real depending on stage; fields as in cadlib)


@dataclass
class Line:
    start_point: np.ndarray
    end_point: np.ndarray

    def reverse(self) -> None:
        self.start_point, self.end_point = self.end_point, self.start_point

    def scale(self, s: float) -> None:
        self.start_point = self.start_point * s
        self.end_point = self.end_point * s

    def shift(self, d: np.ndarray) -> None:
        self.start_point = self.start_point + d
        self.end_point = self.end_point + d


@dataclass
class Circle:
    center: np.ndarray
    radius: float

    @property
    def start_point(self) -> np.ndarray:
        return np.array([self.center[0] - self.radius, self.center[1]])

    @property
    def end_point(self) -> np.ndarray:
        return np.array([self.center[0] + self.radius, self.center[1]])

    def scale(self, s: float) -> None:
        self.center = self.center * s
        self.radius = abs(self.radius * s)

    def shift(self, d: np.ndarray) -> None:
        self.center = self.center + d


@dataclass
class Arc:
    center: np.ndarray
    radius: float
    start_arc: float
    end_arc: float
    mid_arc: float

    @property
    def mid_point(self) -> np.ndarray:
        return self.center + self.radius * np.array([math.cos(self.mid_arc), math.sin(self.mid_arc)])

    @property
    def start_point(self) -> np.ndarray:
        return np.array([self.center[0] + math.cos(self.start_arc) * self.radius,
                         self.center[1] + math.sin(self.start_arc) * self.radius])

    @property
    def end_point(self) -> np.ndarray:
        return np.array([self.center[0] + math.cos(self.end_arc) * self.radius,
                         self.center[1] + math.sin(self.end_arc) * self.radius])

    def reverse(self) -> None:
        self.start_arc, self.end_arc = self.end_arc, self.start_arc

    def scale(self, s: float) -> None:
        self.center = self.center * s
        self.radius = abs(self.radius * s)

    def shift(self, d: np.ndarray) -> None:
        self.center = self.center + d


@dataclass
class Spline:
    point_list: List[np.ndarray]

    def reverse(self) -> None:
        self.point_list = list(reversed(self.point_list))

    @property
    def start_point(self) -> np.ndarray:
        return self.point_list[0]

    @property
    def end_point(self) -> np.ndarray:
        return self.point_list[-1]

    def scale(self, s: float) -> None:
        self.point_list = [p * s for p in self.point_list]

    def shift(self, d: np.ndarray) -> None:
        self.point_list = [p + d for p in self.point_list]


Curve = Any  # Line | Circle | Arc | Spline


def _line_from_vector(vec: np.ndarray, start_point: np.ndarray) -> Line:
    return Line(np.asarray(start_point, dtype=float), np.asarray(vec[1:3], dtype=float))


def _circle_from_vector(vec: np.ndarray) -> Circle:
    return Circle(np.asarray(vec[1:3], dtype=float), float(vec[5]))


def _arc_from_vector(vec: np.ndarray, start_point: np.ndarray) -> Optional[Arc]:
    """vec: single command row (1 + N_ARGS)."""
    end_point = np.asarray(vec[1:3], dtype=float)
    sweep_angle = float(vec[3]) / ARGS_N * 2.0 * math.pi
    clock_sign = int(vec[4])
    s2e = end_point - start_point
    if np.linalg.norm(s2e) == 0:
        return None
    radius = (np.linalg.norm(s2e) / 2.0) / math.sin(sweep_angle / 2.0)
    s2e_mid = (start_point + end_point) / 2.0
    vertical = np.cross(s2e, [0.0, 0.0, 1.0])[:2]
    vertical = vertical / np.linalg.norm(vertical)
    if clock_sign == 0:
        vertical = -vertical
    center_point = s2e_mid - vertical * (radius * math.cos(sweep_angle / 2.0))
    start_arc = vec2arc(start_point, center_point)
    end_arc = vec2arc(end_point, center_point)
    if clock_sign == 0:
        if end_arc < start_arc:
            mid_arc = (start_arc + end_arc) / 2.0
        else:
            mid_arc = (start_arc + end_arc + 2.0 * math.pi) / 2.0
    else:
        if start_arc < end_arc:
            mid_arc = (start_arc + end_arc) / 2.0
        else:
            mid_arc = (start_arc + end_arc + 2.0 * math.pi) / 2.0
    return Arc(center_point, radius, start_arc, end_arc, mid_arc)


def _spline_from_vector(vec: np.ndarray, start_point: np.ndarray) -> Spline:
    point_list = [np.asarray(start_point, dtype=float)]
    for i in range(vec.shape[0]):
        point_list.append(np.asarray(vec[i][1:3], dtype=float))
    return Spline(point_list)


def _curve_from_vector(vec: np.ndarray, start_point: np.ndarray) -> Optional[Curve]:
    """Reconstruct one curve; illed arcs degrade to lines (as in their builder).

    ``vec`` is either a single command row (1-D) or a Spline row block (2-D).
    """
    kind = int(vec[0][0]) if vec.ndim > 1 else int(vec[0])
    if kind == LINE_IDX:
        return _line_from_vector(vec, start_point)
    if kind == CIRCLE_IDX:
        return _circle_from_vector(vec)
    if kind == ARC_IDX:
        arc = _arc_from_vector(vec, start_point)
        if arc is None:
            return _line_from_vector(vec, start_point)
        return arc
    if kind == SPLINE_IDX:
        return _spline_from_vector(vec, start_point)
    raise ValueError(f"unsupported curve command {kind}")


# ---------------------------------------------------------------------------
# loop / profile (quantized stage)


@dataclass
class Loop:
    curves: List[Curve]

    @property
    def start_point(self) -> np.ndarray:
        return self.curves[0].start_point

    @property
    def end_point(self) -> np.ndarray:
        return self.curves[-1].end_point

    @property
    def bbox(self) -> np.ndarray:
        boxes = []
        for c in self.curves:
            boxes.append(_curve_bbox(c))
        pts = np.concatenate(boxes, axis=0)
        return np.stack([pts.min(axis=0), pts.max(axis=0)], axis=0)

    @property
    def bbox_size(self) -> float:
        lo, hi = self.bbox[0], self.bbox[1]
        return float(np.max(np.abs(np.concatenate([hi - self.start_point, lo - self.start_point]))))


@dataclass
class Profile:
    loops: List[Loop]

    @property
    def start_point(self) -> np.ndarray:
        return self.loops[0].start_point

    @property
    def bbox_size(self) -> float:
        return max(loop.bbox_size for loop in self.loops)


def _curve_bbox(c: Curve) -> np.ndarray:
    if isinstance(c, Circle):
        return np.stack([c.center - c.radius, c.center + c.radius], axis=0)
    if isinstance(c, Arc):
        pts = [c.start_point, c.end_point]
        a0, a1 = c.start_arc, c.end_arc
        span = (a1 - a0) % (2.0 * math.pi)
        for axis_angle, delta in ((0.0, 0.0), (math.pi / 2, 0.0), (math.pi, 0.0), (3 * math.pi / 2, 0.0)):
            if ((axis_angle - a0) % (2.0 * math.pi)) <= span:
                pts.append(c.center + c.radius * np.array([math.cos(axis_angle), math.sin(axis_angle)]))
        arr = np.stack(pts, axis=0)
        return np.stack([arr.min(axis=0), arr.max(axis=0)], axis=0)
    if isinstance(c, Line):
        return np.stack([c.start_point, c.end_point], axis=0)
    return np.stack([np.array(p, dtype=float) for p in c.point_list], axis=0)


def _loop_from_vector(vec: np.ndarray, start_point: Optional[np.ndarray] = None) -> Loop:
    if start_point is None:
        for i in range(vec.shape[0]):
            if vec[i][0] == EOS_IDX:
                start_point = vec[i - 1][1:3]
                break
    curves: List[Curve] = []
    i = 0
    while i < vec.shape[0]:
        kind = vec[i][0]
        if kind == SOL_IDX:
            i += 1
            continue
        if kind == EOS_IDX:
            break
        if kind == SPLINE_IDX:
            j = i + 1
            while j < vec.shape[0] and vec[j][0] == SCP_IDX:
                j += 1
            curve = _curve_from_vector(vec[i:j], start_point)
            start_point = curve.end_point
            i = j - 1
        else:
            curve = _curve_from_vector(vec[i], start_point)
            start_point = vec[i][1:3]
        curves.append(curve)
        i += 1
    return Loop(curves)


def _profile_from_vector(vec: np.ndarray) -> Profile:
    loops: List[Loop] = []
    command = vec[:, 0]
    end_idx = command.tolist().index(EOS_IDX)
    indices = np.where(command[:end_idx] == SOL_IDX)[0].tolist() + [end_idx]
    for i in range(len(indices) - 1):
        loop_vec = vec[indices[i]:indices[i + 1]]
        loop_vec = np.concatenate([loop_vec, np.array([EOS_IDX, *([-1] * N_ARGS)])[np.newaxis]], axis=0)
        if loop_vec[0][0] == SOL_IDX and loop_vec[1][0] not in (SOL_IDX, EOS_IDX):
            loops.append(_loop_from_vector(loop_vec))
    return Profile(loops)


# ---------------------------------------------------------------------------
# coord system


@dataclass
class CoordSystem:
    origin: np.ndarray
    theta: float
    phi: float
    gamma: float

    @staticmethod
    def from_quantized(vec6: np.ndarray) -> "CoordSystem":
        """(theta, phi, gamma, ox, oy, oz) quantized → real."""
        theta, phi, gamma = (_denorm_centered(float(v)) * math.pi for v in vec6[:3])
        origin = np.array([_denorm_centered(float(v)) for v in vec6[3:6]])
        return CoordSystem(origin, theta, phi, gamma)

    @property
    def normal(self) -> np.ndarray:
        return polar_parameterization_inverse(self.theta, self.phi, self.gamma)[0]

    @property
    def x_axis(self) -> np.ndarray:
        return polar_parameterization_inverse(self.theta, self.phi, self.gamma)[1]

    @property
    def y_axis(self) -> np.ndarray:
        return np.cross(self.normal, self.x_axis)


# ---------------------------------------------------------------------------
# select tree (faithful port of Select.to_select state machine)


@dataclass
class Select:
    select_type: str
    body_type: str
    body_no: int
    no: int
    operation_list: List["Select"] = field(default_factory=list)
    no_shared_included: List["Select"] = field(default_factory=list)
    all_oriented_included: Dict[str, List["Select"]] = field(default_factory=dict)
    all_partially_included: List["Select"] = field(default_factory=list)


def _to_select(vec: np.ndarray) -> "Select":
    """Port of Select.to_select: parse ONE Topo→Select block into a single
    Select tree (mirrors their `return select_list[0]`)."""
    select_list: List[Select] = []
    no_shared_included: List[Select] = []
    partially_shared_included: List[Select] = []
    all_oriented_limits1: List[Select] = []
    all_oriented_limits2: List[Select] = []
    mirror_list: List[Select] = []
    mode = 0  # 0 select, 1 no_shared, 2 oriented limits1, 3 oriented limits2, 4 partially
    start_mirror = 0
    time_to_no_shared = False
    time_to_partially_shared = False
    time_to_all_oriented1 = False
    time_to_all_oriented2 = False

    def flush_flags(target: Select) -> None:
        nonlocal time_to_no_shared, time_to_partially_shared, time_to_all_oriented1, time_to_all_oriented2
        if time_to_no_shared:
            time_to_no_shared = False
            target.no_shared_included = list(no_shared_included)
            no_shared_included.clear()
        if time_to_partially_shared:
            time_to_partially_shared = False
            target.all_partially_included = list(partially_shared_included)
            partially_shared_included.clear()
        if time_to_all_oriented1:
            time_to_all_oriented1 = False
            target.all_oriented_included['Limits1'] = list(all_oriented_limits1)
            all_oriented_limits1.clear()
        if time_to_all_oriented2:
            time_to_all_oriented2 = False
            target.all_oriented_included['Limits2'] = list(all_oriented_limits2)
            all_oriented_limits2.clear()

    def bucket(mode: int) -> List[Select]:
        return {0: select_list, 1: no_shared_included, 2: all_oriented_limits1,
                3: all_oriented_limits2, 4: partially_shared_included}[mode]

    def make(sel: np.ndarray, ops: List[Select], body: Optional[str] = None) -> Select:
        return Select(SELECT_TYPE[int(sel[0])],
                      body if body is not None else BODY_TYPE[int(sel[1])],
                      int(sel[2]), int(sel[3]), list(ops), [], {})

    def pop_two(target: List[Select]) -> List[Select]:
        ops = [target.pop(-2), target.pop(-1)]
        return ops

    for i in range(vec.shape[0]):
        row = vec[i]
        cmd = int(row[0])
        if cmd == TOPO_IDX:
            mode = 0
        elif cmd == MIRROR_START_IDX:
            start_mirror += 1
        elif cmd == ALL_COMMANDS.index('NoSharedIncluded'):
            mode = 1
        elif cmd == ALL_COMMANDS.index('AllOrientedIncluded1'):
            mode = 2
        elif cmd == ALL_COMMANDS.index('AllOrientedIncluded2'):
            mode = 3
        elif cmd == ALL_COMMANDS.index('AllPartiallySharedIncluded'):
            mode = 4
        elif cmd == ALL_COMMANDS.index('NoSharedIncludedEnd'):
            time_to_no_shared = True
            mode = 0
        elif cmd == ALL_COMMANDS.index('AllPartiallySharedIncludedEnd'):
            time_to_partially_shared = True
            mode = 0
        elif cmd == ALL_COMMANDS.index('AllOrientedIncludedEnd'):
            if mode == 2:
                time_to_all_oriented1 = True
            elif mode == 3:
                time_to_all_oriented2 = True
            mode = 0
        elif cmd == SELECT_IDX:
            sel = row[-4:]
            stype, btype = int(sel[0]), int(sel[1])
            if stype == SELECT_TYPE.index("Wire"):
                target = mirror_list if start_mirror > 0 else bucket(mode)
                target.append(make(sel, []))
                if start_mirror == 0 and mode == 0:
                    flush_flags(select_list[-1])
            elif stype == SELECT_TYPE.index("Face"):
                if btype == BODY_TYPE.index("Shell"):
                    ops = []
                    if start_mirror > 0:
                        ops.append(mirror_list.pop())
                        mirror_list.append(make(sel, ops))
                    elif mode == 0:
                        ops.append(select_list.pop())
                        select_list.append(make(sel, ops))
                        flush_flags(select_list[-1])
                    else:
                        b = bucket(mode)
                        ops.append(b.pop())
                        b.append(make(sel, ops))
                elif btype in (BODY_TYPE.index("Chamfer"), BODY_TYPE.index("EdgeFillet")):
                    if start_mirror > 0:
                        ops = pop_two(mirror_list)
                        mirror_list.append(make(sel, ops))
                    elif mode == 0:
                        ops = pop_two(select_list)
                        select_list.append(make(sel, ops))
                        flush_flags(select_list[-1])
                    else:
                        b = bucket(mode)
                        ops = pop_two(b)
                        b.append(make(sel, ops))
                elif btype == BODY_TYPE.index("Mirror"):
                    start_mirror -= 1
                    ops = [mirror_list.pop()]
                    target = mirror_list if start_mirror > 0 else bucket(mode)
                    target.append(make(sel, ops))
                elif btype == BODY_TYPE.index("Hole"):
                    if start_mirror > 0:
                        ops = [mirror_list.pop()]
                        mirror_list.append(make(sel, ops))
                    elif mode == 0:
                        select_list.append(make(sel, []))
                        flush_flags(select_list[-1])
                    else:
                        bucket(mode).append(make(sel, []))
                elif int(sel[3]) == 0:
                    ops = []
                    if start_mirror > 0:
                        ops.append(mirror_list.pop())
                        mirror_list.append(make(sel, ops))
                    elif mode == 0:
                        ops.append(select_list.pop())
                        select_list.append(make(sel, ops))
                        flush_flags(select_list[-1])
                    else:
                        b = bucket(mode)
                        ops.append(b.pop())
                        b.append(make(sel, ops))
                else:
                    if start_mirror > 0:
                        mirror_list.append(make(sel, []))
                    elif mode == 0:
                        select_list.append(make(sel, []))
                        flush_flags(select_list[-1])
                    else:
                        bucket(mode).append(make(sel, []))
            elif stype == SELECT_TYPE.index("Sub_Face"):
                if btype in (BODY_TYPE.index("Chamfer"), BODY_TYPE.index("EdgeFillet")):
                    if start_mirror > 0:
                        ops = pop_two(mirror_list)
                        mirror_list.append(make(sel, ops))
                    elif mode == 0:
                        ops = pop_two(select_list)
                        select_list.append(make(sel, ops))
                    else:
                        b = bucket(mode)
                        ops = pop_two(b)
                        b.append(make(sel, ops))
                elif btype == BODY_TYPE.index("Shell"):
                    if start_mirror > 0:
                        ops = [mirror_list.pop()]
                        mirror_list.append(make(sel, ops))
                        flush_flags(mirror_list[-1])
                    elif mode == 0:
                        ops = [select_list.pop()]
                        select_list.append(make(sel, ops))
                        flush_flags(select_list[-1])
                    else:
                        b = bucket(mode)
                        ops = [b.pop()]
                        b.append(make(sel, ops))
                elif btype == BODY_TYPE.index("Mirror"):
                    start_mirror -= 1
                    ops = [mirror_list.pop()]
                    target = mirror_list if start_mirror > 0 else bucket(mode)
                    target.append(make(sel, ops))
                else:
                    if start_mirror > 0:
                        mirror_list.append(make(sel, []))
                    elif mode == 0:
                        select_list.append(make(sel, []))
                        flush_flags(select_list[-1])
                    else:
                        bucket(mode).append(make(sel, []))
            elif stype == SELECT_TYPE.index("Multiply_Face"):
                ops = []
                if start_mirror > 0:
                    while mirror_list and mirror_list[-1].select_type == SELECT_TYPE.index('Sub_Face'):
                        ops.append(mirror_list.pop())
                    ops.reverse()
                    mirror_list.append(make(sel, ops, body='None'))
                elif mode == 0:
                    while select_list and select_list[-1].select_type == SELECT_TYPE.index('Sub_Face'):
                        ops.append(select_list.pop())
                    ops.reverse()
                    select_list.append(make(sel, ops, body='None'))
                    flush_flags(select_list[-1])
                else:
                    b = bucket(mode)
                    while b and b[-1].select_type == SELECT_TYPE.index('Sub_Face'):
                        ops.append(b.pop())
                    ops.reverse()
                    b.append(make(sel, ops, body='None'))
            elif stype == SELECT_TYPE.index("Edge"):
                # Edge selects carry body_type None and bind the two preceding
                # face selects (the edge shared by / created from them).
                if start_mirror > 0:
                    ops = pop_two(mirror_list)
                    mirror_list.append(make(sel, ops, body='None'))
                elif mode == 0:
                    ops = pop_two(select_list)
                    select_list.append(make(sel, ops, body='None'))
                    flush_flags(select_list[-1])
                else:
                    b = bucket(mode)
                    if btype == 2:  # their mode-2 branch pops after append (kept as-is)
                        b.append(make(sel, [], body='None'))
                        ops = pop_two(b)
                    else:
                        ops = pop_two(b)
                        b.append(make(sel, ops, body='None'))
    return select_list[0]


# ---------------------------------------------------------------------------
# feature model


@dataclass
class SketchPlan:
    """Decoded sketch: real 2D curves on the feature plane + plane frame."""
    plane_origin: np.ndarray
    plane_normal: np.ndarray
    plane_x_axis: np.ndarray
    plane_y_axis: np.ndarray
    profile: Profile           # curves in real 2D coords (denormalized)
    profile_quantized: Profile  # as-decoded quantized curves (audit reference)


@dataclass
class ExtrudeFeature:
    kind: str                  # 'Ext' | 'Pocket'
    operation: str             # BOOLEAN_OPERATIONS value ('Pocket' → cut)
    sketch: SketchPlan
    extent_one: float
    extent_two: float
    extent_type1: str
    extent_type2: str
    select_list: List[Select]  # UpTo targets when present


@dataclass
class RevolveFeature:
    kind: str                  # 'Rev' | 'Groove'
    operation: str
    sketch: SketchPlan
    angle_one: float           # degrees, start angle from sketch plane (CATIA FirstAngle)
    angle_two: float           # degrees, opposite side (CATIA SecondAngle)
    axis_select: Select


@dataclass
class FinishFeature:
    kind: str                  # 'Shell' | 'Chamfer' | 'Fillet'
    select_list: List[Select]
    params: Dict[str, float]


@dataclass
class HoleFeature:
    kind: str
    sketch: SketchPlan         # plane under the hole; point_pos 2D on that plane
    point_pos: np.ndarray
    radius: float
    depth: float
    bottom_mode: str
    plane_ref: Select
    select_list: List[Select]


@dataclass
class UnsupportedFeature:
    kind: str                  # 'Draft' | 'Mirror'
    detail: str


Feature = Any


def _sketch_plan(plane6: np.ndarray, sket_pos: np.ndarray, sket_size: float,
                 profile_q: Profile) -> SketchPlan:
    """Assemble the real sketch frame.

    ``plane6`` carries (theta, phi, gamma) quantized + origin quantized — the
    CoordSystem origin IS sketch_pos (verified in Extrude.from_vector). Profile
    curves denormalize via (p - 128) * size / 95, the inverse of
    normalize(size=256) as used by the dataset's own CATIA rebuild.
    """
    theta, phi, gamma = (_denorm_centered(float(v)) * math.pi for v in plane6[:3])
    origin = np.array([_denorm_centered(float(v)) for v in sket_pos])
    normal, x_axis = polar_parameterization_inverse(theta, phi, gamma)
    y_axis = np.cross(normal, x_axis)

    real = _denormalize_profile(profile_q, _denorm_size(float(sket_size)))
    return SketchPlan(origin, normal, x_axis, y_axis, real, profile_q)


def _denormalize_profile(profile_q: Profile, size: float) -> Profile:
    scale = size / DENORM_SCALE_DENOM
    offset = np.array([ARGS_N / 2.0, ARGS_N / 2.0])
    loops = []
    for loop in profile_q.loops:
        curves = []
        for c in loop.curves:
            c2 = _copy_curve(c)
            _curve_shift(c2, -offset)
            _curve_scale(c2, scale)
            curves.append(c2)
        loops.append(Loop(curves))
    return Profile(loops)


def _copy_curve(c: Curve) -> Curve:
    if isinstance(c, Line):
        return Line(c.start_point.copy(), c.end_point.copy())
    if isinstance(c, Circle):
        return Circle(c.center.copy(), c.radius)
    if isinstance(c, Arc):
        return Arc(c.center.copy(), c.radius, c.start_arc, c.end_arc, c.mid_arc)
    return Spline([p.copy() for p in c.point_list])


def _curve_shift(c: Curve, d: np.ndarray) -> None:
    if isinstance(c, Line):
        c.start_point = c.start_point + d
        c.end_point = c.end_point + d
    elif isinstance(c, Circle):
        c.center = c.center + d
    elif isinstance(c, Arc):
        c.center = c.center + d
    else:
        c.point_list = [p + d for p in c.point_list]


def _curve_scale(c: Curve, s: float) -> None:
    if isinstance(c, Line):
        c.start_point = c.start_point * s
        c.end_point = c.end_point * s
    elif isinstance(c, (Circle, Arc)):
        c.center = c.center * s
        c.radius = c.radius * s
    else:
        c.point_list = [p * s for p in c.point_list]


def _split_profile_rows(vec: np.ndarray) -> np.ndarray:
    """Rows before the first Topo marker or the trailing feature command —
    mirrors their scan for TOPO_IDX / feature idx (Extrude.from_vector)."""
    body = vec[:-1] if vec.shape[0] else vec
    stops = np.where((body[:, 0] == TOPO_IDX) | (body[:, 0] == EOS_IDX))[0]
    cut = int(stops[0]) if len(stops) else body.shape[0]
    return body[:cut]


def _parse_select_rows(vec: np.ndarray) -> List[Select]:
    """Select blocks between profile rows and the trailing feature command —
    one Select tree per Topo group, mirroring their from_vector slicing."""
    commands = vec[:, 0]
    indices = np.where(commands == TOPO_IDX)[0].tolist()
    if not indices:
        return []
    groups = [vec[indices[i]:indices[i + 1]] for i in range(len(indices) - 1)]
    groups.append(vec[indices[-1]:])
    return [_to_select(g) for g in groups]


def _plane_args(row: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    ext_vec = row[1 + N_ARGS_SKETCH:1 + N_ARGS_SKETCH + N_ARGS_EXT]
    return ext_vec[:3], ext_vec[N_ARGS_PLANE:N_ARGS_PLANE + 3], float(ext_vec[N_ARGS_PLANE + N_ARGS_TRANS - 1])


def _body_param(row: np.ndarray) -> np.ndarray:
    """Trailing 7 body params of the feature row: ext1, ext2, type1, type2,
    -1, -1, operation (their ext_vec[N_ARGS_PLANE + N_ARGS_TRANS:])."""
    base = 1 + N_ARGS_SKETCH + N_ARGS_PLANE + N_ARGS_TRANS
    return row[base:base + N_ARGS_BODY_PARAM]


def _finish_param(row: np.ndarray, start: int, count: int) -> np.ndarray:
    base = 1 + N_ARGS_SKETCH + N_ARGS_EXT
    return row[base + start:base + start + count]


def _decode_ext_like(vec: np.ndarray, cmd_idx: int, is_numerical: bool) -> Feature:
    """Ext and Pocket share the block layout [profile..., (Topo/Select...), cmd]."""
    kind = 'Ext' if cmd_idx == EXT_IDX else 'Pocket'
    profile_rows = _split_profile_rows(vec)
    profile_q = _profile_from_vector(np.concatenate([profile_rows, _eos_row()]))
    last = vec[-1]
    plane_ang, sket_pos_q, sket_size_q = _plane_args(last)
    param = _body_param(last)
    selects = _parse_select_rows(vec[:-1])
    if is_numerical:
        extent_one = _denorm_centered(float(param[0]))
        extent_two = _denorm_centered(float(param[1]))
        extent_type1 = EXTENT_TYPE[int(param[2])]
        extent_type2 = EXTENT_TYPE[int(param[3])]
    else:
        extent_one, extent_two = float(param[0]), float(param[1])
        extent_type1, extent_type2 = EXTENT_TYPE[int(param[2])], EXTENT_TYPE[int(param[3])]
    operation = BOOLEAN_OPERATIONS[int(param[6])] if kind == 'Ext' else 'CutFeatureOperation'
    sketch = _sketch_plan(plane_ang, sket_pos_q, sket_size_q, profile_q)
    return ExtrudeFeature(kind, operation, sketch, extent_one, extent_two,
                          extent_type1, extent_type2, selects)


def _decode_rev_like(vec: np.ndarray, cmd_idx: int, is_numerical: bool) -> Feature:
    """Rev (Shaft) and Groove: [profile..., Topo/Select(axis), cmd]."""
    kind = 'Rev' if cmd_idx == REV_IDX else 'Groove'
    profile_rows = _split_profile_rows(vec)
    profile_q = _profile_from_vector(np.concatenate([profile_rows, _eos_row()]))
    last = vec[-1]
    plane_ang, sket_pos_q, sket_size_q = _plane_args(last)
    param = _body_param(last)
    axis_select = _to_select(np.array([vec[-2]]))
    if is_numerical:
        angle_one = float(param[4]) / (ARGS_N - 1) * 360.0
        angle_two = float(param[5]) / (ARGS_N - 1) * 360.0
        operation = BOOLEAN_OPERATIONS[int(param[6])] if kind == 'Rev' else 'CutFeatureOperation'
    else:
        angle_one, angle_two = float(param[4]), float(param[5])
        operation = BOOLEAN_OPERATIONS[int(param[6])]
    sketch = _sketch_plan(plane_ang, sket_pos_q, sket_size_q, profile_q)
    return RevolveFeature(kind, operation, sketch, angle_one, angle_two, axis_select)


def _decode_finish(vec: np.ndarray, cmd_idx: int, is_numerical: bool) -> Feature:
    kind = {SHELL_IDX: 'Shell', CHAMFER_IDX: 'Chamfer', FILLET_IDX: 'Fillet'}[cmd_idx]
    last = vec[-1]
    selects = _parse_select_rows(vec[:-1])
    if kind == 'Shell':
        raw = _finish_param(last, 0, 2)
        params = {'thickness': _denorm_centered(float(raw[0])),
                  'second_thickness': _denorm_centered(float(raw[1]))}
    elif kind == 'Chamfer':
        raw = _finish_param(last, 2, 2)
        params = {'length1': _denorm_centered(float(raw[0])),
                  'angle_or_length2': _denorm_centered(float(raw[1]))}
    else:
        raw = _finish_param(last, 4, 1)
        params = {'radius': _denorm_centered(float(raw[0]))}
    return FinishFeature(kind, selects, params)


def _decode_hole(vec: np.ndarray, is_numerical: bool) -> Feature:
    last = vec[-1]
    selects = _parse_select_rows(vec[:-1])
    plane_ref = selects[0] if selects else None
    select_list = selects[1:] if len(selects) > 1 else []
    point_q = np.array([float(last[1]), float(last[2])])
    plane_ang = last[1 + N_ARGS_SKETCH:1 + N_ARGS_SKETCH + 6]
    radius_q = float(_finish_param(last, 6, 1)[0])
    depth_q = float(_finish_param(last, 7, 1)[0])
    bottom_idx = int(_finish_param(last, 8, 1)[0])
    if is_numerical:
        point_pos = np.array([_denorm_centered(v) for v in point_q])
        radius = _denorm_centered(radius_q)
        depth = _denorm_centered(depth_q)
        bottom_mode = EXTENT_TYPE[bottom_idx]
    else:
        point_pos, radius, depth, bottom_mode = point_q, radius_q, depth_q, EXTENT_TYPE[bottom_idx]
    # Hole plane: (theta, phi, gamma, origin) quantized; origin at plane_vec[0:3]
    theta, phi, gamma = (_denorm_centered(float(v)) * math.pi for v in plane_ang[:3])
    origin = np.array([_denorm_centered(float(v)) for v in plane_ang[3:6]])
    normal, x_axis = polar_parameterization_inverse(theta, phi, gamma)
    sketch = SketchPlan(origin, normal, x_axis, np.cross(normal, x_axis),
                        Profile([]), Profile([]))
    return HoleFeature('Hole', sketch, point_pos, radius, depth, bottom_mode, plane_ref, select_list)


def _eos_row() -> np.ndarray:
    return np.array([EOS_IDX, *([-1] * N_ARGS)])[np.newaxis]


def decode_vec(vec: np.ndarray, is_numerical: bool = True) -> List[Feature]:
    """Decode a quantized command matrix (len, 1 + N_ARGS) into features."""
    vec = np.asarray(vec)[:, :1 + N_ARGS]
    commands = vec[:, 0]
    feature_cmds = (EXT_IDX, REV_IDX, SHELL_IDX, CHAMFER_IDX, FILLET_IDX,
                    POCKET_IDX, DRAFT_IDX, MIRROR_IDX, GROOVE_IDX, HOLE_IDX)
    op_indices = [-1] + np.where(np.isin(commands, feature_cmds))[0].tolist()
    features: List[Feature] = []
    for i in range(len(op_indices) - 1):
        start, end = op_indices[i], op_indices[i + 1]
        block = vec[start + 1:end + 1]
        cmd = int(commands[end])
        if cmd in (EXT_IDX, POCKET_IDX):
            features.append(_decode_ext_like(block, cmd, is_numerical))
        elif cmd in (REV_IDX, GROOVE_IDX):
            features.append(_decode_rev_like(block, cmd, is_numerical))
        elif cmd in (SHELL_IDX, CHAMFER_IDX, FILLET_IDX):
            features.append(_decode_finish(block, cmd, is_numerical))
        elif cmd == HOLE_IDX:
            features.append(_decode_hole(block, is_numerical))
        elif cmd in (DRAFT_IDX, MIRROR_IDX):
            features.append(UnsupportedFeature('Draft' if cmd == DRAFT_IDX else 'Mirror', ''))
    return features


def load_h5(path) -> List[Feature]:
    import h5py

    with h5py.File(path, "r") as fp:
        vec = fp["vec"][:].astype(int)
    return decode_vec(vec, is_numerical=True)
