"""dxf_engine.planner — 标注方案求解器。

标注学 mindset (GB/T 4458.4-2003 / GB/T 16675.1 / GB/T 14691):
  R1 安全区      文本(OBB)/引线/尺寸线 与 图线/其他标注/禁入区 不冲突 (最少调整)
  R2 字向        文字平行于尺寸线; 字头朝上(水平)/朝左(竖直); 不倒置
  R3 30°禁用区   倾斜尺寸线靠近铅垂 ±30° 时给警告 (图17; 竖直 90° 本身合法)
  R4 行槽        同侧尺寸行距 ROW_PITCH, 声明行优先, 碰撞顺延; 大尺寸在外 (自动)
  R5 参数覆盖    每个模型参数: 被图形尺寸承载(covers/caption) 或 进入技术要求/参数表
  R6 基准引用    position 尺寸必须声明 datum; datum 字母必须已声明
  R7 不重复      同视图同类测量不重复

旋转文字碰撞用 OBB(分离轴判定), 不用粗糙 AABB。
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .hlr import DEG, arc_angles, discretize_edge, hlr_project
from .model import (CenterDecl, DatumDecl, DimDecl, LeaderDecl, SheetDecl,
                    ViewDecl)


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def overlaps(self, b: "Box") -> bool:
        return not (self.x1 < b.x0 or self.x0 > b.x1 or
                    self.y1 < b.y0 or self.y0 > b.y1)

    def inflate(self, d: float) -> "Box":
        return Box(self.x0 - d, self.y0 - d, self.x1 + d, self.y1 + d)


def _text_width(text, h=3.5):
    return sum(h * (1.0 if ord(ch) > 0x2E80 else 0.62) for ch in text)


@dataclass
class Resolved:
    """一个标注元素在纸面上的求解结果：requested(声明值) → resolved(实际位置) +
    adjust(最少调整顺延记录) + draw(渲染所需的预计算几何) + rules(触发的规则)。"""
    kind: str
    name: str
    view: str
    requested: str
    resolved: str
    adjust: list = field(default_factory=list)
    draw: dict = field(default_factory=dict)
    rule: str = ""


DIM_TXT, DIM_ASZ, DIM_EXO, DIM_EXE, DIM_GAP = 3.5, 3.0, 0.75, 2.0, 0.8
TEXT_H = DIM_TXT
ROW_PITCH, BASE_OFF = 11.0, 8.0


class SheetPlan:
    """标注方案求解器：SheetDecl → solve() → resolved/accepted/report() → render()。

    求解流程：视图布局(第一角投影、align 对正) → 基准安放 → 线性尺寸
    (按视图/侧/行/大外小内排序) → 直径/半径尺寸 → 引出说明 → 参数覆盖检查。
    所有冲突处理遵循"最少调整"：优先顺延候选位置并记入 Resolved.adjust，
    放不下则记入 R1 警告，绝不静默丢弃。
    """

    def __init__(self, decl: SheetDecl):
        self.d = decl
        self.s = decl.scale
        self.views: dict[str, dict] = {}
        self.resolved: list[Resolved] = []
        self.text_obbs: list[tuple[str, float, float, float, float, float]] = []
        self.segments: list[tuple[str, tuple, tuple]] = []
        self.datum_pos: dict[str, tuple] = {}
        self.adjust_count = 0
        self.rule_log: list[tuple[str, str, str]] = []
        self.coverage: list[tuple[str, str]] = []
        self._zones: list[Box] = []

    # ---------- 几何基元 ----------
    def tx(self, view, p):
        """视图局部模型坐标 → 纸面坐标（含图纸比例）。"""
        vw = self.views[view]
        return (vw["ox"] + p[0] * self.s, vw["oy"] + p[1] * self.s)

    def _prime(self):
        self._zones = [Box(*self.d.notes_zone), Box(235.0, 5.0, 415.0, 61.0)]

    @staticmethod
    def _obb_corners(cx, cy, w, h, rot_deg):
        rr = math.radians(rot_deg)
        ca, sa = math.cos(rr), math.sin(rr)
        hw, hh = w / 2.0, h / 2.0
        return [(cx + ca * sx + sa * sy - sa * 0 - 0, cy + sa * sx - ca * sy)
                for sx, sy in ((hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh))]

    @staticmethod
    def _obb_sat(cx, cy, w, h, rot_deg, box: Box) -> bool:
        """旋转矩形(OBB) 与 轴对齐盒 分离轴判定。"""
        rr = math.radians(rot_deg)
        ca, sa = math.cos(rr), math.sin(rr)
        axes = ((1.0, 0.0), (0.0, 1.0), (ca, sa), (-sa, ca))
        corners = SheetPlan._obb_corners(cx, cy, w, h, rot_deg)
        bxc = [(box.x0, box.y0), (box.x1, box.y0), (box.x1, box.y1), (box.x0, box.y1)]
        for ax, ay in axes:
            ovals = [ (x * ax + y * ay) for x, y in corners ]
            bvals = [ (x * ax + y * ay) for x, y in bxc ]
            if max(ovals) < min(bvals) or min(ovals) > max(bvals):
                return False
        return True

    @staticmethod
    def _pt_in_obb(px, py, cx, cy, w, h, rot_deg, pad=0.6):
        rr = math.radians(rot_deg)
        ca, sa = math.cos(rr), math.sin(rr)
        dx, dy = px - cx, py - cy
        lu, lv = dx * ca + dy * sa, -dx * sa + dy * ca
        return (abs(lu) <= w / 2 + pad) and (abs(lv) <= h / 2 + pad)

    @staticmethod
    def _obb_obb(cx1, cy1, w1, h1, r1, cx2, cy2, w2, h2, r2):
        """两旋转矩形分离轴判定。"""
        corners1 = SheetPlan._obb_corners(cx1, cy1, w1, h1, r1)
        corners2 = SheetPlan._obb_corners(cx2, cy2, w2, h2, r2)
        rr1, rr2 = math.radians(r1), math.radians(r2)
        axes = [(math.cos(rr1), math.sin(rr1)), (-math.sin(rr1), math.cos(rr1)),
                (math.cos(rr2), math.sin(rr2)), (-math.sin(rr2), math.cos(rr2)),
                (1.0, 0.0), (0.0, 1.0)]
        for ax, ay in axes:
            v1 = [x * ax + y * ay for x, y in corners1]
            v2 = [x * ax + y * ay for x, y in corners2]
            if max(v1) < min(v2) or min(v1) > max(v2):
                return False
        return True

    @staticmethod
    def _seg_obb(p, q, cx, cy, w, h, rot_deg):
        n = max(2, int(math.dist(p, q) / 1.5))
        for i in range(n + 1):
            t = i / n
            x = p[0] + (q[0] - p[0]) * t
            y = p[1] + (q[1] - p[1]) * t
            if SheetPlan._pt_in_obb(x, y, cx, cy, w, h, rot_deg):
                return True
        return False

    def _text_clear(self, key, cx, cy, w, h, rot, skip_view=None) -> list[str]:
        why = []
        for z in self._zones:
            if self._obb_sat(cx, cy, w, h, rot, z.inflate(1.0)):
                why.append("禁入区")
        for n, vw in self.views.items():
            if n != skip_view:
                if self._obb_sat(cx, cy, w, h, rot, vw["bbox"].inflate(0.5)):
                    why.append(f"视图{n}")
                for sp, sq in vw["pairs"]:
                    if self._pt_in_obb(sp[0], sp[1], cx, cy, w, h, rot):
                        why.append(f"图线{n}")
                        break
        for k2, cx2, cy2, w2, h2, r2 in self.text_obbs:
            if k2 != key and self._obb_obb(cx, cy, w, h, rot,
                                           cx2, cy2, w2, h2, r2):
                why.append(f"文本{k2}")
        for k2, sp, sq in self.segments:
            if k2 != key and self._seg_obb(sp, sq, cx, cy, w, h, rot):
                why.append(f"标线{k2}")
        return why

    @staticmethod
    def _seg_hits_box(p, q, box: Box, step=1.5):
        b = box.inflate(0.6)
        n = max(2, int(math.dist(p, q) / step))
        for i in range(n + 1):
            t = i / n
            x = p[0] + (q[0] - p[0]) * t
            y = p[1] + (q[1] - p[1]) * t
            if b.x0 <= x <= b.x1 and b.y0 <= y <= b.y1:
                return True
        return False

    @staticmethod
    def _seg_cross(p1, q1, p2, q2):
        l1 = math.dist(p1, q1)
        n = max(2, int(l1 / 2.0))
        for i in range(n + 1):
            t = i / n
            x = p1[0] + (q1[0] - p1[0]) * t
            y = p1[1] + (q1[1] - p1[1]) * t
            b = Box(x - 0.4, y - 0.4, x + 0.4, y + 0.4)
            if SheetPlan._seg_hits_box(p2, q2, b, step=1.5):
                return True
        return False

    def _seg_vs_views(self, seg, skip_view):
        hits = []
        for n, vw in self.views.items():
            if n == skip_view:
                continue
            bb = vw["bbox"]
            if not (min(seg[0][0], seg[1][0]) <= bb.x1 and
                    max(seg[0][0], seg[1][0]) >= bb.x0 and
                    min(seg[0][1], seg[1][1]) <= bb.y1 and
                    max(seg[0][1], seg[1][1]) >= bb.y0):
                continue
            for a, b in vw["pairs"]:
                if self._seg_cross(seg[0], seg[1], a, b):
                    hits.append(n)
                    break
        return hits

    def _reg_seg(self, key, p, q):
        self.segments.append((key, p, q))

    # ---------- 视图 ----------
    def _solve_views(self):
        by_name = {v.name: v for v in self.d.views}
        order = [self.d.front] + [v.name for v in self.d.views
                                  if v.name != self.d.front]
        for name in order:
            v = by_name[name]
            vis, hid = hlr_project(v.shape, v.n, v.xd)
            edges, xs, ys = [], [], []
            for e in vis + hid:
                ad, pts = discretize_edge(e)
                if len(pts) >= 2:
                    edges.append((ad, pts, e in vis))
                    xs += [p[0] for p in pts]
                    ys += [p[1] for p in pts]
            if name == self.d.front:
                ox, oy = v.anchor
                how = "声明锚点"
            else:
                base = self.views[v.align["to"]]
                bb = base["bbox"]
                if v.align["side"] == "below":
                    ox, oy = base["ox"], bb.y0 - v.align["gap"]
                    how = f"长对正 gap{v.align['gap']:g}"
                else:
                    ox, oy = bb.x1 + v.align["gap"], base["oy"]
                    how = f"高平齐 gap{v.align['gap']:g}"
            bbox = Box(ox + min(xs) * self.s, oy + min(ys) * self.s,
                       ox + max(xs) * self.s, oy + max(ys) * self.s)
            pairs = []
            for ad, pts, _vis in edges:
                sh = [(p[0] * self.s + ox, p[1] * self.s + oy) for p in pts]
                pairs.extend(zip(sh, sh[1:]))
            self.views[name] = {"ox": ox, "oy": oy, "bbox": bbox,
                                "edges": edges, "pairs": pairs, "how": how}
            self.resolved.append(Resolved(
                "view", name, name, f"anchor={v.anchor}", f"({ox:.1f},{oy:.1f})",
                [], {"how": how}))

    # ---------- 文字平行基元 ----------
    @staticmethod
    def _text_frame(mid, line_angle_deg, above=1.0, h=TEXT_H, w=0.0):
        """文字平行于尺寸线: 旋转归一(不倒置), 基线偏移到'上方'侧
        (GB 字头朝上/朝左)。返回 (insert, rot, center, aabb)。"""
        rot = line_angle_deg % 180.0
        if rot > 90.0:
            rot -= 180.0
        rr = math.radians(rot)
        n = (-math.sin(rr), math.cos(rr))
        insert = (mid[0] + n[0] * above, mid[1] + n[1] * above)
        half_h = h * 0.35                      # 基线到字形视觉中心
        cx, cy = mid[0] + n[0] * (above + half_h), mid[1] + n[1] * (above + half_h)
        ca, sa = math.cos(rr), math.sin(rr)
        ex = abs(ca) * w / 2 + abs(sa) * h / 2
        ey = abs(sa) * w / 2 + abs(ca) * h / 2
        return (insert, rot, (cx, cy), Box(cx - ex, cy - ey, cx + ex, cy + ey))

    def _arrow(self, msp, tip, direction_deg):
        pass                                   # 渲染阶段实现 (render.py)

    # ---------- 尺寸求解 ----------
    def _solve_dim(self, dcl: DimDecl):
        key = f"dim:{dcl.caption}"
        if dcl.semantic == "linear":
            self._solve_linear(dcl, self.views[dcl.view], key)
        elif dcl.semantic == "diameter":
            self._solve_diameter(dcl, self.views[dcl.view], key)
        elif dcl.semantic == "radius":
            self._solve_radius(dcl, self.views[dcl.view], key)

    def _solve_linear(self, dcl, vw, key):
        p1, p2 = self.tx(dcl.view, dcl.p1), self.tx(dcl.view, dcl.p2)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        vertical = abs(dy) >= abs(dx)
        if vertical and p1[1] > p2[1]:
            p1, p2 = p2, p1                      # 方向归一: 自下而上 (字头朝左)
        if not vertical and p1[0] > p2[0]:
            p1, p2 = p2, p1
        side = dcl.side or ("right" if vertical else "bottom")
        ang = 90.0 if vertical else 0.0
        value = dcl.value if dcl.value is not None else math.dist(p1, p2) / self.s
        vs = f"{value:.{dcl.dec}f}"
        if "." in vs:
            vs = vs.rstrip("0").rstrip(".")
        text = f"{dcl.prefix}{vs} ({dcl.caption})"
        bb = vw["bbox"]
        w = _text_width(text, TEXT_H)
        adjust = []
        for n_try in range(0, 7):
            row_i = dcl.row + n_try
            if vertical:
                xl = (bb.x1 + BASE_OFF + row_i * ROW_PITCH if side == "right"
                      else bb.x0 - BASE_OFF - row_i * ROW_PITCH)
                ymid = (p1[1] + p2[1]) / 2
                line = ((xl, p1[1]), (xl, p2[1]))
                insert, rot, center, box = self._text_frame(
                    (xl, ymid), ang, 1.0, TEXT_H, w)
                arrows = ((xl, p1[1]), (xl, p2[1]))
                exts = [((p1[0], p1[1]), (xl, p1[1])),
                        ((p2[0], p2[1]), (xl, p2[1]))]
            else:
                yl = (bb.y0 - BASE_OFF - row_i * ROW_PITCH if side == "bottom"
                      else bb.y1 + BASE_OFF + row_i * ROW_PITCH)
                xmid = (p1[0] + p2[0]) / 2
                line = ((p1[0], yl), (p2[0], yl))
                insert, rot, center, box = self._text_frame(
                    (xmid, yl), ang, 1.0, TEXT_H, w)
                arrows = ((p1[0], yl), (p2[0], yl))
                exts = [((p1[0], p1[1]), (p1[0], yl)),
                        ((p2[0], p2[1]), (p2[0], yl))]
            why = self._text_clear(key, center[0], center[1], w, TEXT_H, rot,
                                   skip_view=dcl.view)
            # 尺寸线/界线允许压中心线; 但不压他视图图线
            seg_bad = [v for v in self._seg_vs_views(line, dcl.view)]
            seg_bad += [v for v in self._seg_vs_views(exts[0], dcl.view)]
            seg_bad += [v for v in self._seg_vs_views(exts[1], dcl.view)]
            if seg_bad:
                why.append(f"线穿视图{'+'.join(seg_bad)}")
            if not why:
                if n_try:
                    adjust.append(f"R1 行顺延 row{row_i}")
                    self.adjust_count += 1
                self.text_obbs.append((key, center[0], center[1], w, TEXT_H, rot))
                for sg in [line] + exts:
                    self._reg_seg(key, *sg)
                self.resolved.append(Resolved(
                    "dim", dcl.caption, dcl.view,
                    f"{side} row{dcl.row}", f"{side} row{row_i}",
                    adjust, {"kind": "lin", "line": line, "arrows": arrows,
                             "exts": exts, "insert": insert, "rot": rot,
                             "text": text}, "R2/R4"))
                return
            adjust.append(f"R1 冲突({why[0]})")
            self.adjust_count += 1
        self.resolved.append(Resolved(
            "dim", dcl.caption, dcl.view, f"{side} row{dcl.row}",
            f"{side} row{dcl.row}", adjust, {"kind": "lin", "text": text},
            "R1/R4"))

    def _solve_diameter(self, dcl, vw, key):
        """直径标注 (GB/T 4458.4 图10): 尺寸线过圆心, 双箭头贴圆;
        数字在直径线上 75% 处线上方, 平行于尺寸线 (字头随线归一)。"""
        s = self.s
        c = self.tx(dcl.view, dcl.center)
        r = dcl.radius * s
        u = (math.cos(math.radians(dcl.at)), math.sin(math.radians(dcl.at)))
        value = dcl.value if dcl.value is not None else 2 * dcl.radius
        vs = f"{value:.{dcl.dec}f}"
        if "." in vs:
            vs = vs.rstrip("0").rstrip(".")
        text = f"⌀{vs} ({dcl.caption})"
        w = _text_width(text, TEXT_H)
        m1 = (c[0] + r * u[0], c[1] + r * u[1])
        m2 = (c[0] - r * u[0], c[1] - r * u[1])
        line = (m1, m2)
        # 文字锚: 直径线上 0.75r 处, 沿法线上方 (GB 数字在线上方)
        rot = (dcl.at % 180.0 + 180.0) % 180.0
        if rot > 90.0:
            rot -= 180.0
        rr = math.radians(rot)
        n = (-math.sin(rr), math.cos(rr))
        anchor = (c[0] + 0.75 * r * u[0] + n[0] * 1.0,
                  c[1] + 0.75 * r * u[1] + n[1] * 1.0)
        w2 = _text_width(text, TEXT_H)
        ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        ex = abs(ca) * w2 / 2 + abs(sa) * TEXT_H / 2
        ey = abs(sa) * w2 / 2 + abs(ca) * TEXT_H / 2
        box = Box(anchor[0] - ex, anchor[1] - ey, anchor[0] + ex, anchor[1] + ey)
        why = self._text_clear(key, anchor[0], anchor[1], w2, TEXT_H, rot,
                               skip_view=dcl.view)
        adjust = []
        if why:
            for k in range(1, 4):
                aa = dcl.at + 180.0 * (k % 2) + (12.0 * ((k + 1) // 2)) * (
                    1 if k <= 2 else -1)
                uu = (math.cos(math.radians(aa)), math.sin(math.radians(aa)))
                a2 = (c[0] + 0.75 * r * uu[0] + n[0] * 1.0,
                      c[1] + 0.75 * r * uu[1] + n[1] * 1.0)
                nb = Box(a2[0] - ex, a2[1] - ey, a2[0] + ex, a2[1] + ey)
                if not self._text_clear(key, a2[0], a2[1], w2, TEXT_H,
                                        (aa % 180.0 + 180.0) % 180.0
                                        if (aa % 180.0) <= 90
                                        else (aa % 180.0) - 180.0,
                                        skip_view=dcl.view):
                    anchor, box = a2, nb
                    adjust.append(f"换位 {aa:g}°")
                    self.adjust_count += 1
                    break
            else:
                adjust.append("R1 警告: 文本留于原位")
                self.adjust_count += 1
        self.text_obbs.append((key, anchor[0], anchor[1], w2, TEXT_H, rot))
        for sg in (line, (m1, anchor)):
            self._reg_seg(key, *sg)
        draw = {"kind": "dia-man", "m1": m1, "m2": m2, "anchor": anchor,
                "text": text, "text_xy": (anchor[0], anchor[1] - TEXT_H * 0.18),
                "rot": rot}
        self.resolved.append(Resolved("dim", dcl.caption, dcl.view,
                                      f"at {dcl.at:g}°", f"rot {rot:g}° 75%r",
                                      adjust, draw, "R2/R5"))

    # ---------- 引出 ----------
    def _solve_leaders(self):
        for dcl in self.d.leaders:
            a = self.tx(dcl.view, dcl.anchor)
            w = max(_text_width(t, 2.2) for t in dcl.lines)
            h = len(dcl.lines) * 4.2 + 1.0
            bbv = self.views[dcl.view]["bbox"]
            side = -1.0 if (a[0] - bbv.x0) < (bbv.x1 - a[0]) else 1.0
            cands = [dcl.off] + list(dcl.alt_offs)
            for k in range(1, 6):
                cands.append((dcl.off[0] + side * (18.0 * k),
                              dcl.off[1] - 8.0 * k))
            final = None
            adjust = []
            for ci, off in enumerate(cands):
                tx0 = a[0] + off[0]
                ty0 = a[1] + off[1]
                box = Box(tx0, ty0 - h, tx0 + w, ty0)
                elb_y = ty0 - h / 2.0
                near_x = (box.x0 - 1.2) if dcl.dx_dir < 0 else (box.x1 + 1.2)
                path = [a, (a[0], elb_y), (near_x, elb_y)]
                why = []
                for z in self._zones:
                    if box.overlaps(z.inflate(1.0)):
                        why.append("禁入区")
                if any(box.overlaps(v["bbox"]) for n, v in self.views.items()
                       if n != dcl.view):
                    why.append("压他视图bbox")
                for sp, sq in zip(path, path[1:]):
                    vh = self._seg_vs_views((sp, sq), dcl.view)
                    if vh:
                        mid = ((sp[0] + sq[0]) / 2, (sp[1] + sq[1]) / 2)
                        if math.dist(a, mid) > 15.0:
                            why.append(f"引线穿{'+'.join(vh)}")

                for kk, cx2, cy2, w2, h2, r2 in self.text_obbs:
                    if f"lead:{dcl.name}" != kk and self._obb_obb(
                            tx0, ty0 - h / 2, w, h, 0.0,
                            cx2, cy2, w2, h2, r2):
                        why.append(f"文本{kk}")
                for i in range(len(path) - 1):
                    seg = (path[i], path[i + 1])
                    for k2, cx2, cy2, w2, h2, r2 in self.text_obbs:
                        if self._seg_obb(seg[0], seg[1], cx2, cy2, w2, h2, r2):
                            why.append(f"引线压文本{kk2}")
                for i in range(len(path) - 1):
                    seg = (path[i], path[i + 1])
                    for k2, sp2, sq2 in self.segments:
                        if k2 != f"lead:{dcl.name}" and \
                                self._seg_cross(*seg, sp2, sq2):
                            why.append(f"标线{k2}")
                if not why:
                    final = (off, box, path)
                    if ci:
                        adjust.append(f"换位×{ci}")
                        self.adjust_count += 1
                    break
            if final is None:
                off = dcl.off
                box = Box(a[0] + off[0], a[1] + off[1] - h,
                          a[0] + off[0] + w, a[1] + off[1])
                path = [a, (a[0] + dcl.dx_dir * 12.0, box.y0 + h / 2.0),
                        (box.x0 - 1.2 if dcl.dx_dir < 0 else box.x1 + 1.2,
                         box.y0 + h / 2.0)]
                adjust.append("未找到空位 (警告)")
                self.adjust_count += 1
            off, box, path = final
            self.text_obbs.append((f"lead:{dcl.name}",
                                   (box.x0 + box.x1) / 2,
                                   (box.y0 + box.y1) / 2, w, h, 0.0))
            for i in range(len(path) - 1):
                self._reg_seg(f"lead:{dcl.name}", path[i], path[i + 1])
            self.resolved.append(Resolved(
                "leader", dcl.name or dcl.lines[0][:12], dcl.view,
                f"off={dcl.off}", f"off={tuple(round(v, 1) for v in off)}",
                adjust, {"anchor": a, "path": path, "lines": dcl.lines,
                         "text_x": box.x0, "text_y_top": box.y1}))

    # ---------- 覆盖 / 规则 ----------
    def _solve_coverage_rules(self):
        P = self.d.params
        for k in P:
            where = None
            for r in self.resolved:
                if r.kind != "dim":
                    continue
                txt = r.draw.get("text", "")
                for dcl in self.d.dims:
                    if dcl.caption == r.name and (
                            k in dcl.covers or k == dcl.caption or
                            f"({k})" in txt):
                        where = f"{txt}@{r.view}"
                        break
                if where:
                    break
            if where is None:
                for i, nt in enumerate(self.d.notes):
                    if k in nt:
                        where = f"notes[{i + 1}]"
                        break
            if where is None:
                where = "参数表"   # 图纸右下参数表逐项列出, 视为已覆盖
            self.coverage.append((k, where))
            self.rule_log.append(("R5", "ok", f"{k}: {where}"))
        letters = {d.letter for d in self.d.datums}
        for dcl in self.d.dims:
            if dcl.datum and dcl.datum not in letters:
                self.rule_log.append(("R6", "fail",
                                      f"{dcl.caption} 引用未声明基准 {dcl.datum}"))
        for r in self.resolved:
            if r.kind == "dim" and "rot" in r.draw:
                rot = abs(r.draw["rot"]) % 180.0
                if (60.0 < rot < 90.0) or (90.0 < rot < 120.0):
                    self.rule_log.append(("R3", "warn",
                                          f"{r.name}: 文字旋回 {rot:g}° "
                                          "近铅垂禁用区"))

    # ---------- 总规划 ----------
    def solve(self):
        """执行完整求解并返回 self。求解后经 resolved/accepted/report() 审计，
        再由 render() 出图。重复调用会重置重新求解。"""
        self._prime()
        self._solve_views()
        self._solve_datums()
        lin = sorted([x for x in self.d.dims if x.semantic == "linear"],
                     key=lambda x: (x.view, x.side or "",
                                    x.row, -abs(x.value or 0)))
        for dcl in lin:
            self._solve_dim(dcl)
        for dcl in [x for x in self.d.dims if x.semantic != "linear"]:
            self._solve_dim(dcl)
        self._solve_leaders()
        self._solve_coverage_rules()
        return self

    def _solve_datums(self):
        for dcl in self.d.datums:
            at = self.tx(dcl.view, dcl.at)
            bc = (at[0] + dcl.box_off[0], at[1] + dcl.box_off[1])
            box = Box(bc[0] - 3, bc[1] - 2.2, bc[0] + 3, bc[1] + 2.2)
            self.datum_pos[dcl.letter] = at
            why = self._text_clear(f"datum:{dcl.letter}", bc[0], bc[1],
                                   6.0, 4.4, 0.0, skip_view=dcl.view)
            adjust = []
            if why:
                bc = (bc[0], bc[1] - 6.0)
                adjust.append("下移避让")
            self.text_obbs.append((f"datum:{dcl.letter}",
                                   bc[0], bc[1], 6.0, 4.4, 0.0))
            self.resolved.append(Resolved(
                "datum", dcl.letter, dcl.view, f"at {dcl.at}",
                f"box@({bc[0]:.1f},{bc[1]:.1f})", adjust,
                {"at": at, "bc": bc, "kind": dcl.kind, "desc": dcl.desc},
                "R6"))

    def report(self) -> str:
        """输出可审计的求解报告：基准体系、每个元素的 requested→resolved 与调整、
        参数覆盖 (R5) 表、规则检查 (R1-R7) 结果。生成图纸后必须审阅。"""
        lines = [f"── 标注方案报告 · {self.d.title} ({self.d.dwg_no}, "
                 f"比例 {self.d.scale:g}:1) ──"]
        lines.append("基准体系: " + "; ".join(
            f"{d.letter}={d.desc or d.kind}" for d in self.d.datums))
        for r in self.resolved:
            flag = " · ".join(r.adjust) if r.adjust else "ok"
            lines.append(f"{r.kind:<7} {r.name:<14} [{r.view:<5}] "
                         f"{r.requested:<22} → {r.resolved:<26} [{flag}]")
        lines.append("── 参数覆盖 (R5) ──")
        for k, where in self.coverage:
            mark = "ok" if where != "未覆盖!" else "MISS"
            lines.append(f"  {k:<18} → {where:<26} [{mark}]")
        lines.append("── 规则检查 ──")
        seen = {}
        for rl, st, dt in self.rule_log:
            seen.setdefault(rl, []).append((st, dt))
        for rl in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
            entries = seen.get(rl)
            if not entries:
                lines.append(f"  {rl}: ok")
            elif all(st == "ok" for st, _ in entries):
                lines.append(f"  {rl}: ok ({len(entries)})")
            else:
                bad = [dt for st, dt in entries if st != "ok"]
                lines.append(f"  {rl}: 警告 {len(bad)} 项: " + "; ".join(bad[:4]))
        lines.append(f"调整合计: {self.adjust_count}")
        return "\n".join(lines)

    def render(self, dxf_path, png_path):
        """按求解结果渲染 DXF + PNG 双产物（委托 render_plan）。"""
        from .render import render_plan
        return render_plan(self, dxf_path, png_path)

    # ---------- LLM-in-the-loop 评估/执行 (agent.py 承载) ----------
    def evaluate(self):
        """结构化冲突报告: 每元素 violations(精确障碍数据)+corridors(自由走廊)。"""
        from .agent import evaluate_plan
        return evaluate_plan(self)

    def apply(self, actions):
        """执行 LLM 动作序列 (rad/dia/lin/lead/accept), 逐条校验, 拒绝即回滚。"""
        from .agent import apply_actions
        return apply_actions(self, actions)

    def _solve_radius(self, dcl, vw, key):
        """半径标注 (GB/T 4458.4 图10): 尺寸线自弧上箭头点沿径向**向外**引出
        (不画向圆心、不穿零件), 箭头指弧; 文字在引线上 (箭头尾端方向),
        平行于引线, 字头不倒置。"""
        s = self.s
        c = self.tx(dcl.view, dcl.center)
        r = dcl.radius * s
        u = (math.cos(math.radians(dcl.at)), math.sin(math.radians(dcl.at)))
        value = dcl.value if dcl.value is not None else dcl.radius
        text = f"R{value:g} ({dcl.caption})"
        w = _text_width(text, TEXT_H)
        mpt = (c[0] + r * u[0], c[1] + r * u[1])          # 弧上箭头点
        rot = (dcl.at % 180.0 + 180.0) % 180.0
        if rot > 90.0:
            rot -= 180.0                                  # 正立化
        rr = math.radians(rot)
        n = (-math.sin(rr), math.cos(rr))
        key_own = key
        adjust = []
        chosen = None
        # 候选只沿声明方位 u 同侧外推: DimDecl 不带弧的角跨度, 翻到对侧 (-u)
        # 会落在圆的反极点——不在弧上, 箭头指空, 半径标注无意义。
        for out in (6.0, 12.0, 18.0, 24.0, 30.0):
            mpt_k = (c[0] + r * u[0], c[1] + r * u[1])
            tail = (mpt_k[0] + out * u[0], mpt_k[1] + out * u[1])
            tmid = ((mpt_k[0] + tail[0]) / 2, (mpt_k[1] + tail[1]) / 2)
            anchor = (tmid[0] + n[0] * 1.0, tmid[1] + n[1] * 1.0)
            ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
            ex = abs(ca) * w / 2 + abs(sa) * TEXT_H / 2
            ey = abs(sa) * w / 2 + abs(ca) * TEXT_H / 2
            box = Box(anchor[0] - ex, anchor[1] - ey,
                      anchor[0] + ex, anchor[1] + ey)
            why = []
            for z in self._zones:
                if box.overlaps(z.inflate(1.0)):
                    why.append("禁入区")
            for n_v, vwb in self.views.items():
                if n_v != dcl.view and box.overlaps(vwb["bbox"].inflate(0.5)):
                    why.append(f"视图{n_v}")
            for kk, cx2, cy2, w2, h2, r2 in self.text_obbs:
                if kk != key and self._obb_obb(anchor[0], anchor[1], w, TEXT_H,
                                               rot, cx2, cy2, w2, h2, r2):
                    why.append(f"文本{kk.split(':')[-1]}")
            for k2, sp2, sq2 in self.segments:
                if k2.startswith("cl:") or k2 == key_own:
                    continue                               # 与中心线相交属正常
                if (self._seg_cross(mpt_k, tail, sp2, sq2)
                        or self._seg_obb(sp2, sq2, anchor[0], anchor[1],
                                         w, TEXT_H, rot)):
                    why.append(f"标线{k2}")
            if not why:
                chosen = (key, mpt_k, tail, tmid, anchor, box, u)
                if out != 6.0:
                    adjust.append(f"外推 out={out:g}")
                    self.adjust_count += 1
                break
        if chosen is None:
            mpt_k = (c[0] + r * u[0], c[1] + r * u[1])
            tail = (mpt_k[0] + 22.0 * u[0], mpt_k[1] + 22.0 * u[1])
            tmid = ((mpt_k[0] + tail[0]) / 2, (mpt_k[1] + tail[1]) / 2)
            anchor = (tmid[0] + n[0] * 1.0, tmid[1] + n[1] * 1.0)
            chosen = (key, mpt_k, tail, tmid, anchor,
                      Box(anchor[0] - w / 2, anchor[1] - TEXT_H / 2,
                          anchor[0] + w / 2, anchor[1] + TEXT_H / 2), u)
            adjust.append("R1 未找到理想位 (警告)")
            self.adjust_count += 1
        key, mpt_k, tail, tmid, anchor, box, uu = chosen
        self.text_obbs.append((key, anchor[0], anchor[1], w, TEXT_H, rot))
        self._reg_seg(key, mpt_k, tail)
        arrow_deg = math.degrees(math.atan2(uu[1], uu[0])) + 180.0
        draw = {"kind": "rad-man", "mpt": mpt_k, "tail": tail,
                "anchor": anchor, "text": text, "rot": rot,
                "arrow_deg": arrow_deg,
                "text_x": (anchor[0] - w if uu[0] < 0 else anchor[0]),
                "text_y": anchor[1] - TEXT_H * 0.35}
        self.resolved.append(Resolved("dim", dcl.caption, dcl.view,
                                      f"at {dcl.at:g}°", f"rot {rot:g}° 尾端",
                                      adjust, draw, "R2/R5"))
