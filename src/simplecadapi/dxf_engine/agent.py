"""dxf_engine.agent — LLM-in-the-loop 评估/执行接口。

角色分工 (评估器 + 提示器, 决策权在 LLM):
  引擎(确定性)  精确冲突数据 / 自由走廊度量 / 动作校验落地 (拒绝即回滚)
  LLM(决策)     在评估数据上选点/取舍, 经 apply 提交动作, 引擎全量复检
几何真值不出代码: LLM 永不提供裸顶点之外的算术结果, mpt/箭头等语义约束
由引擎从 (at,out,rot) 重推导 —— 箭头恒落在真实圆周上。
评估政策与各求解器一致: 文本/标线不查本视图图线 (标注可压自身视图)。
"""
from __future__ import annotations

import math

from .planner import BASE_OFF, Box, ROW_PITCH, TEXT_H, _text_width


def _r(v, nd=1):
    return round(float(v), nd)


def _element_geom(r):
    """Resolved → (key, view, cx, cy, w, h, rot, segs)；几何不全返回 None。"""
    dr = r.draw
    if r.kind == "dim":
        text = dr.get("text", "")
        w = _text_width(text, TEXT_H)
        if dr.get("kind") == "lin" and "insert" in dr:
            ins = dr["insert"]
            return (f"dim:{r.name}", r.view, ins[0], ins[1], w, TEXT_H, dr["rot"],
                    [tuple(dr["line"])] + [tuple(s) for s in dr["exts"]])
        if dr.get("kind") == "dia-man":
            a = dr["anchor"]
            return (f"dim:{r.name}", r.view, a[0], a[1], w, TEXT_H, dr["rot"],
                    [(tuple(dr["m1"]), tuple(dr["m2"])),
                     (tuple(dr["m1"]), tuple(dr["insert"]))])
        if dr.get("kind") == "rad-man":
            a = dr["anchor"]
            return (f"dim:{r.name}", r.view, a[0], a[1], w, TEXT_H, dr["rot"],
                    [(tuple(dr["mpt"]), tuple(dr["tail"]))])
        return None
    if r.kind == "leader" and r.name:
        x0, y1 = dr["text_x"], dr["text_y_top"]
        w = max(_text_width(t, 2.2) for t in dr["lines"])
        h = len(dr["lines"]) * 4.2 + 1.0
        p = dr["path"]
        return (f"lead:{r.name}", r.view, x0 + w / 2, y1 - h / 2, w, h, 0.0,
                [(tuple(p[i]), tuple(p[i + 1])) for i in range(len(p) - 1)])
    if r.kind == "datum":
        bc = dr["bc"]
        return (f"datum:{r.name}", r.view, bc[0], bc[1], 6.0, 4.4, 0.0, [])
    return None


def _proper_cross(a, b, c, d, eps=0.5):
    """严格 X 交叉: 两段互相跨立且无共端点。共端点(共用测量点)/共线(共用界线)/
    丁字(界线端点落在他人线上)均为 GB 正常画法, 不计冲突。"""
    if min(math.dist(a, c), math.dist(a, d),
           math.dist(b, c), math.dist(b, d)) < eps:
        return False

    def ori(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)

    o1, o2 = ori(a, b, c), ori(a, b, d)
    o3, o4 = ori(c, d, a), ori(c, d, b)
    return o1 == -o2 and o3 == -o4 and o1 != 0 and o3 != 0


def _conflicts(plan, key, view, cx, cy, w, h, rot, segs):
    """单元素放置的确定性冲突检测, 返回结构化障碍数据 (纸面坐标 mm)。"""
    out = []
    for i, z in enumerate(plan._zones):
        if plan._obb_sat(cx, cy, w, h, rot, z.inflate(1.0)):
            out.append({"rule": "R1", "type": "禁入区", "id": f"zone{i}",
                        "bbox": [_r(z.x0), _r(z.y0), _r(z.x1), _r(z.y1)]})
    for n, vw in plan.views.items():
        bb = vw["bbox"]
        if n != view and plan._obb_sat(cx, cy, w, h, rot, bb.inflate(0.5)):
            out.append({"rule": "R1", "type": "视图bbox", "id": f"view:{n}",
                        "bbox": [_r(bb.x0), _r(bb.y0), _r(bb.x1), _r(bb.y1)]})
        if n != view:
            nh = sum(1 for sp, _sq in vw["pairs"]
                     if plan._pt_in_obb(sp[0], sp[1], cx, cy, w, h, rot))
            if nh:
                out.append({"rule": "R1", "type": "图线", "id": f"figure:{n}",
                            "points": nh})
    for k2, cx2, cy2, w2, h2, r2 in plan.text_obbs:
        if k2 != key and plan._obb_obb(cx, cy, w, h, rot, cx2, cy2, w2, h2, r2):
            out.append({"rule": "R1", "type": "文本", "id": k2,
                        "center": [_r(cx2), _r(cy2)], "w": _r(w2), "h": _r(h2),
                        "rot": _r(r2)})
    for k2, sp, sq in plan.segments:
        if k2 == key:
            continue
        if (plan._seg_obb(sp, sq, cx, cy, w, h, rot)
                or any(_proper_cross(s[0], s[1], sp, sq) for s in segs)):
            out.append({"rule": "R1", "type": "标线", "id": k2,
                        "seg": [[_r(sp[0]), _r(sp[1])], [_r(sq[0]), _r(sq[1])]]})
    for s in segs:
        for n in plan._seg_vs_views(s, view):
            out.append({"rule": "R1", "type": "标线穿他视图图线", "id": f"figure:{n}"})
    return out


def _corridors(plan, key, view, cx, cy, w, h, rot, maxd=60.0, step=1.0):
    """文本 OBB 沿 ±x/±y 平移的最大无冲突距离 (仅文本碰撞, 不含标线)。"""
    res = {}
    for label, dx, dy in (("+x", 1, 0), ("-x", -1, 0), ("+y", 0, 1), ("-y", 0, -1)):
        d = 0.0
        while d < maxd and not _conflicts(plan, key, view,
                                          cx + dx * (d + step), cy + dy * (d + step),
                                          w, h, rot, []):
            d += step
        res[label] = _r(d)
    return res


def evaluate_plan(plan):
    accepted = getattr(plan, "accepted", {})
    elements = []
    for r in plan.resolved:
        if r.kind == "view":                      # 视图非标注元素, 不评估
            continue
        g = _element_geom(r)
        key = g[0] if g else f"{r.kind}:{r.name}"
        entry = {"id": key, "kind": r.kind, "view": r.view}
        if g is None:
            entry["status"] = "unsolved"
            elements.append(entry)
            continue
        _k, view, cx, cy, w, h, rot, segs = g
        conf = _conflicts(plan, key, view, cx, cy, w, h, rot, segs)
        rules = sorted({c["rule"] for c in conf})
        if (60.0 < rot % 180.0 < 90.0) or (90.0 < rot % 180.0 < 120.0):
            rules.append("R3")                    # 竖直 90° 本身合法 (GB 图17)
        entry.update(text=r.draw.get("text")
                     or (r.draw.get("lines") and " / ".join(r.draw["lines"])),
                     anchor=[_r(cx), _r(cy)], w=_r(w), h=_r(h), rot=_r(rot))
        if key in accepted:
            entry.update(status="accepted",
                         reason=accepted.get(key) if isinstance(accepted, dict)
                         else None)
        elif conf:
            entry.update(status="warn", rules=rules, violations=conf,
                         corridors=_corridors(plan, key, view, cx, cy, w, h, rot))
        else:
            entry["status"] = "ok"
            if "R3" in rules:
                entry["rules"] = ["R3"]
        elements.append(entry)
    n_warn = sum(1 for e in elements if e["status"] == "warn")
    return {"sheet": plan.d.title, "dwg_no": plan.d.dwg_no,
            "n_elements": len(elements), "n_warn": n_warn, "elements": elements}


def _find_dim(plan, caption):
    for d in plan.d.dims:
        if d.caption == caption:
            return d
    raise KeyError(f"dim {caption}")


def _find_resolved(plan, key):
    for r in plan.resolved:
        g = _element_geom(r)
        if g and g[0] == key:
            return r
    raise KeyError(key)


def _unregister(plan, key):
    old_ob = [t for t in plan.text_obbs if t[0] == key]
    old_sg = [t for t in plan.segments if t[0] == key]
    plan.text_obbs = [t for t in plan.text_obbs if t[0] != key]
    plan.segments = [t for t in plan.segments if t[0] != key]
    return old_ob, old_sg


def _restore(plan, old):
    plan.text_obbs += old[0]
    plan.segments += old[1]


def _commit(plan, key, cx, cy, w, h, rot, segs):
    plan.text_obbs.append((key, cx, cy, w, h, rot))
    for sp, sq in segs:
        plan.segments.append((key, sp, sq))


def _reject(plan, act, key, view, conf, cx, cy, w, h, rot):
    return {"op": act["op"], "element": key, "ok": False, "violations": conf,
            "corridors": _corridors(plan, key, view, cx, cy, w, h, rot)}


def _norm_rot(at):
    rot = (at % 180.0 + 180.0) % 180.0
    return rot - 180.0 if rot > 90.0 else rot


def _apply_rad(plan, act):
    """半径: 动作只仲裁 at(方位角, 可选 s 滑移提示; s<0 为弧内侧——文字沿过圆心
    的尺寸线置于圆内, 箭头自圆心侧指弧)。基线恒在线上方、引线派生延长;
    rot 恒等于线向 (R2 不可覆盖), mpt 恒取 c+r·u —— 箭头必在圆周。"""
    dcl = _find_dim(plan, act["name"])
    key = f"dim:{dcl.caption}"
    dr = _find_resolved(plan, key).draw
    c = plan.tx(dcl.view, dcl.center)
    rr = dcl.radius * plan.s
    at0 = math.degrees(math.atan2(dr["mpt"][1] - c[1], dr["mpt"][0] - c[0]))
    at = act.get("at", at0)
    u = (math.cos(math.radians(at)), math.sin(math.radians(at)))
    rot = _norm_rot(at)
    n = (-math.sin(math.radians(rot)), math.cos(math.radians(rot)))
    w = _text_width(dr["text"], TEXT_H)
    mpt = (c[0] + rr * u[0], c[1] + rr * u[1])
    if "s" in act:
        cands = [float(act["s"])]
    else:
        cands = list(3.0 + 6.0 * k for k in range(5)) + [-(w + 4.0),
                                                         -(w + 10.0),
                                                         -(w + 18.0)]
    old = _unregister(plan, key)
    conf = anchor = None
    for s0 in cands:
        inner = (s0 + w) < 0.0
        tail_k = s0 - 1.5 if inner else s0 + w + 1.5
        insert = (mpt[0] + s0 * u[0] + n[0] * 1.0,
                  mpt[1] + s0 * u[1] + n[1] * 1.0)
        anchor = (insert[0] + u[0] * w / 2 + n[0] * TEXT_H * 0.35,
                  insert[1] + u[1] * w / 2 + n[1] * TEXT_H * 0.35)
        tail = (mpt[0] + tail_k * u[0], mpt[1] + tail_k * u[1])
        segs = [(mpt, tail)]
        conf = _conflicts(plan, key, dcl.view, anchor[0], anchor[1], w, TEXT_H,
                          rot, segs)
        if not conf or act.get("force"):
            arrow_deg = math.degrees(math.atan2(u[1], u[0]))
            if not inner:
                arrow_deg += 180.0
            dr.update(mpt=mpt, tail=tail, insert=insert, anchor=anchor, rot=rot,
                      arrow_deg=arrow_deg)
            _commit(plan, key, anchor[0], anchor[1], w, TEXT_H, rot, segs)
            _log(plan, key, f"at={at:g}° {'弧内' if inner else '弧外'} s={s0:g}")
            return {"op": "rad", "element": key, "ok": True,
                    "anchor": [_r(anchor[0]), _r(anchor[1])], "rot": _r(rot)}
    _restore(plan, old)
    return _reject(plan, act, key, dcl.view, conf, anchor[0], anchor[1], w,
                   TEXT_H, rot)


def _apply_dia(plan, act):
    """直径: at(尺寸线方位)。尺寸线过圆心, 文字锚 0.75r 线上方
    (insert=基线左端, anchor=OBB 中心), rot 恒等于线向 (R2)。"""
    dcl = _find_dim(plan, act["name"])
    key = f"dim:{dcl.caption}"
    dr = _find_resolved(plan, key).draw
    c = plan.tx(dcl.view, dcl.center)
    rr = dcl.radius * plan.s
    at0 = math.degrees(math.atan2(dr["m1"][1] - c[1], dr["m1"][0] - c[0]))
    at = act.get("at", at0)
    u = (math.cos(math.radians(at)), math.sin(math.radians(at)))
    m1 = (c[0] + rr * u[0], c[1] + rr * u[1])
    m2 = (c[0] - rr * u[0], c[1] - rr * u[1])
    rot = _norm_rot(at)
    n = (-math.sin(math.radians(rot)), math.cos(math.radians(rot)))
    w = _text_width(dr["text"], TEXT_H)
    insert = (c[0] + 0.75 * rr * u[0] + n[0] * 1.0,
              c[1] + 0.75 * rr * u[1] + n[1] * 1.0)
    anchor = (insert[0] + u[0] * w / 2 + n[0] * TEXT_H * 0.35,
              insert[1] + u[1] * w / 2 + n[1] * TEXT_H * 0.35)
    segs = [(m1, m2), (m1, insert)]
    old = _unregister(plan, key)
    conf = _conflicts(plan, key, dcl.view, anchor[0], anchor[1], w, TEXT_H, rot, segs)
    if conf and not act.get("force"):
        _restore(plan, old)
        return _reject(plan, act, key, dcl.view, conf, anchor[0], anchor[1], w, TEXT_H, rot)
    dr.update(m1=m1, m2=m2, insert=insert, anchor=anchor, rot=rot)
    _commit(plan, key, anchor[0], anchor[1], w, TEXT_H, rot, segs)
    _log(plan, key, f"at={at:g}°")
    return {"op": "dia", "element": key, "ok": True,
            "anchor": [_r(anchor[0]), _r(anchor[1])], "rot": _r(rot)}


def _apply_lin(plan, act):
    """线性: side/row 结构位 + slide 沿线 1-DOF。几何与 solver 共用
    _lin_geometry 派生 (文字滑出测量段时尺寸线自动侧延长), 不存在自由文本位。"""
    dcl = _find_dim(plan, act["name"])
    key = f"dim:{dcl.caption}"
    dr = _find_resolved(plan, key).draw
    p1, p2 = plan.tx(dcl.view, dcl.p1), plan.tx(dcl.view, dcl.p2)
    vertical = abs(p2[1] - p1[1]) >= abs(p2[0] - p1[0])
    side = act.get("side", dcl.side or ("right" if vertical else "bottom"))
    row = act.get("row", dcl.row)
    slide = float(act.get("slide", 0.0))
    g = plan._lin_geometry(dcl, side, row, slide, dr["text"])
    w = _text_width(dr["text"], TEXT_H)
    segs = [g["line"]] + g["exts"]
    old = _unregister(plan, key)
    conf = _conflicts(plan, key, dcl.view, g["center"][0], g["center"][1],
                      w, TEXT_H, g["rot"], segs)
    if conf and not act.get("force"):
        _restore(plan, old)
        return _reject(plan, act, key, dcl.view, conf, g["center"][0],
                       g["center"][1], w, TEXT_H, g["rot"])
    dr.update(kind="lin", line=g["line"], arrows=g["arrows"], exts=g["exts"],
              insert=g["insert"], rot=g["rot"])
    _commit(plan, key, g["center"][0], g["center"][1], w, TEXT_H, g["rot"], segs)
    _log(plan, key, f"{side} row{row} slide{slide:+g}"
         + (" 线延长" if g["extended"] else ""))
    return {"op": "lin", "element": key, "ok": True,
            "anchor": [_r(g["center"][0]), _r(g["center"][1])],
            "rot": _r(g["rot"])}


def _apply_lead(plan, act):
    """引出: off=[dx,dy] 文本框相对锚点偏移 (纸面 mm)。路径随框重推。"""
    dcl = next((d for d in plan.d.leaders
                if (d.name or d.lines[0][:12]) == act["name"]), None)
    if dcl is None:
        raise KeyError(f"leader {act['name']}")
    key = f"lead:{dcl.name}"
    dr = _find_resolved(plan, key).draw
    a = plan.tx(dcl.view, dcl.anchor)
    w = max(_text_width(t, 2.2) for t in dcl.lines)
    h = len(dcl.lines) * 4.2 + 1.0
    off = act.get("off", [dr["text_x"] - a[0], dr["text_y_top"] - a[1]])
    tx0, ty0 = a[0] + off[0], a[1] + off[1]
    box = Box(tx0, ty0 - h, tx0 + w, ty0)
    # 肘点取框顶上方: 多行文本时框中部肘线会划过第二行字高带
    elb_y = ty0 + 0.8
    near_x = (box.x0 - 1.2) if dcl.dx_dir < 0 else (box.x1 + 1.2)
    path = [a, (a[0], elb_y), (near_x, elb_y)]
    segs = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
    old = _unregister(plan, key)
    conf = _conflicts(plan, key, dcl.view, tx0 + w / 2, ty0 - h / 2, w, h, 0.0, segs)
    if conf and not act.get("force"):
        _restore(plan, old)
        return _reject(plan, act, key, dcl.view, conf, tx0 + w / 2, ty0 - h / 2, w, h, 0.0)
    dr.update(anchor=a, path=path, text_x=tx0, text_y_top=ty0)
    _commit(plan, key, tx0 + w / 2, ty0 - h / 2, w, h, 0.0, segs)
    _log(plan, key, f"off=({off[0]:g},{off[1]:g})")
    return {"op": "lead", "element": key, "ok": True,
            "anchor": [_r(tx0 + w / 2), _r(ty0 - h / 2)]}


def _apply_accept(plan, act):
    """接受某元素的现存冲突并记录理由 —— 显式取舍, 非静默放行。"""
    if not hasattr(plan, "accepted"):
        plan.accepted = {}
    plan.accepted[act["name"]] = act.get("reason", "")
    plan.rule_log.append(("R1", "accepted",
                          f"{act['name']}: {act.get('reason', '')}"))
    return {"op": "accept", "element": act["name"], "ok": True}


def _log(plan, key, desc):
    r = _find_resolved(plan, key)
    r.resolved = f"agent {desc}"
    r.adjust.append(f"agent: {desc}")
    plan.adjust_count += 1


def _cjk_font_path():
    """matplotlib 用 CJK 字体全路径 (与 render._cjk_font_name 同一候选序)。"""
    import glob
    import os

    want = ("pingfang", "songti", "stheiti", "hiragino", "simsun", "simhei",
            "msyh", "arial unicode")
    pats = ["/System/Library/Fonts/PingFang*", "/System/Library/Fonts/Supplemental/*",
            "/System/Library/Fonts/*", "/Library/Fonts/*.ttf",
            "C:/Windows/Fonts/sim*.tt?", "C:/Windows/Fonts/msyh*"]
    for pat in pats:
        for f in sorted(glob.glob(pat)):
            low = os.path.basename(f).lower()
            if any(w in low for w in want) and low.endswith((".ttf", ".ttc", ".otf")):
                return f
    return None


def annotate_plan(plan, png_path, ev=None, crop_warn=True):
    """冲突可视化: 元素 OBB 打标 + 障碍叠加 (browser-use DOM 打标的制图版)。

    徽标 [N] 对应 evaluate() 输出 elements[N] 的 id, 供 LLM 图文对齐:
    灰边=ok / 红边红底=warn / 橙=accepted; 蓝=障碍 (bbox 虚线框, 标线实线);
    黑点线=视图 bbox, 灰细线=视图图线。统一纸面坐标 (mm)。
    crop_warn=True 时对每个 warn 元素另存局部放大图 `<stem>__<id>.png`
    (视野 = 元素 OBB ∪ 障碍范围 外扩)。"""
    from pathlib import Path

    ev = ev or evaluate_plan(plan)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    from .planner import SheetPlan

    fp = _cjk_font_path()
    if fp:
        from matplotlib import font_manager
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=fp).get_name()
    plt.rcParams["axes.unicode_minus"] = False

    png_path = Path(png_path)
    fig, ax = plt.subplots(figsize=(16.5, 11.7), dpi=150)

    def draw():
        for n, vw in plan.views.items():
            for (x1, y1), (x2, y2) in vw["pairs"]:
                ax.plot([x1, x2], [y1, y2], color="#999999", lw=0.5, zorder=1)
            bb = vw["bbox"]
            ax.add_patch(Rectangle((bb.x0, bb.y0), bb.x1 - bb.x0, bb.y1 - bb.y0,
                                   fill=False, ls=":", ec="#444444", lw=0.6,
                                   zorder=1))
        style = {"ok": ("#bbbbbb", None), "unsolved": ("#8888ff", None),
                 "warn": ("#dd0022", "#ff000018"),
                 "accepted": ("#ee8800", "#ff990018")}
        dirs = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
        for i, e in enumerate(ev["elements"]):
            if e.get("anchor") is None:
                continue
            cx, cy, w, h, rot = *e["anchor"], e["w"], e["h"], e["rot"]
            ec, fc = style.get(e["status"], style["ok"])
            ax.add_patch(Polygon(SheetPlan._obb_corners(cx, cy, w, h, rot),
                                 closed=True, fill=fc is not None,
                                 facecolor=fc or "none", edgecolor=ec, lw=1.4,
                                 zorder=3))
            ax.text(cx, cy + h / 2 + 1.5, f"[{i}] {e['id']}", color=ec,
                    fontsize=6, ha="center", zorder=4)
            if e["status"] == "accepted" and e.get("reason"):
                ax.text(cx, cy - h / 2 - 1.5, "✓ " + e["reason"][:44],
                        color="#ee8800", fontsize=5.2, ha="center", va="top",
                        zorder=4)
            for v in e.get("violations", []):
                if "bbox" in v:
                    x0, y0, x1, y1 = v["bbox"]
                    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                                           fill=False, ls="--", ec="#0066ff",
                                           lw=1.0, zorder=2))
                elif "seg" in v:
                    (sx0, sy0), (sx1, sy1) = v["seg"]
                    ax.plot([sx0, sx1], [sy0, sy1], color="#0066ff", lw=1.6,
                            zorder=2)
            for lbl, d in (e.get("corridors") or {}).items():
                if d <= 0:
                    continue                                  # 无自由度不画
                dx, dy = dirs[lbl]
                ax.annotate("", xy=(cx + dx * d, cy + dy * d), xytext=(cx, cy),
                            arrowprops=dict(arrowstyle="->", color="#009944",
                                            lw=0.9), zorder=2)
                ax.text(cx + dx * d * 0.55, cy + dy * d * 0.55,
                        f"{lbl}{d:g}", color="#009944", fontsize=5.5,
                        ha="center", zorder=4)

    draw()
    ax.set_aspect("equal")
    ax.autoscale()
    ax.set_title(f"{plan.d.title} · 冲突标注: 红=warn 橙=accepted 蓝=障碍 "
                 f"黑点线=视图bbox")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(png_path)

    if crop_warn:
        dirs = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}
        for e in ev["elements"]:
            if e["status"] != "warn":
                continue
            cx, cy = e["anchor"]
            xs, ys = [cx], [cy]
            for v in e.get("violations", []):
                if "bbox" in v:
                    xs += [v["bbox"][0], v["bbox"][2]]
                    ys += [v["bbox"][1], v["bbox"][3]]
                elif "seg" in v:
                    xs += [p[0] for p in v["seg"]]
                    ys += [p[1] for p in v["seg"]]
            for lbl, d in (e.get("corridors") or {}).items():
                if d > 0:                                 # 走廊箭头纳入视野
                    dx, dy = dirs[lbl]
                    dd = min(d, 25.0)
                    xs.append(cx + dx * dd)
                    ys.append(cy + dy * dd)
            m = max(15.0, (max(xs) - min(xs)) * 0.35, (max(ys) - min(ys)) * 0.35)
            ax.set_xlim(min(xs) - m, max(xs) + m)
            ax.set_ylim(min(ys) - m, max(ys) + m)
            safe = e["id"].replace("/", "_").replace(":", "_")
            fig.savefig(png_path.with_name(f"{png_path.stem}__{safe}.png"))
    plt.close(fig)
    return ev


_OPS = {"rad": _apply_rad, "dia": _apply_dia, "lin": _apply_lin,
        "lead": _apply_lead, "accept": _apply_accept}


def apply_actions(plan, actions):
    results = []
    for act in actions:
        fn = _OPS.get(act.get("op"))
        if fn is None:
            results.append({"op": act.get("op"), "ok": False,
                            "error": f"未知 op {act.get('op')!r}"})
            continue
        try:
            results.append(fn(plan, act))
        except KeyError as e:
            results.append({"op": act.get("op"), "ok": False, "error": str(e)})
    out = {"results": results, "eval": evaluate_plan(plan)}
    # agent-in-the-loop: 每次 apply 自动刷新诊断图, 返回文本要求调用方先读图
    if getattr(plan.d, "diag_png", ""):
        try:
            annotate_plan(plan, plan.d.diag_png, out["eval"])
            out["diag"] = plan.d.diag_png
            out["instruction"] = ("诊断图已刷新, 提交下一组动作前必读: "
                                  "灰=ok 红=warn(先读红) 蓝=障碍 "
                                  "绿箭头=元素可滑移方向与距离")
        except Exception as e:                # 诊断失败不阻塞动作结果
            out["diag_error"] = str(e)
    return out
