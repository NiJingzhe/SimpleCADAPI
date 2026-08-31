"""dxf_engine.render — 手工基元渲染: 图线/箭头/旋转文字 → DXF + PNG。

GB/T 4458.4 基元:
  尺寸线/尺寸界线  细实线
  轮廓线           粗实线 (b=0.5)
  虚线/中心线      细虚线 / 细点画线
  箭头             实心三角 (长约 6b)
  文字             平行于尺寸线, 字头朝上/朝左 (旋转归一)
"""
from __future__ import annotations

import math
import time

import ezdxf
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from pathlib import Path

from .planner import TEXT_H

_LAYERS = [
    ("01粗实线", 7, "Continuous", 50),
    ("08虚线", 3, "DASHED_GB", 25),
    ("05中心线", 1, "CENTER_GB", 25),
    ("01细实线", 7, "Continuous", 25),
    ("尺寸标注", 7, "Continuous", 25),
    ("文字", 7, "Continuous", 25),
]


def _cjk_font_name() -> str:
    import glob
    import os

    pats = ["/System/Library/Fonts/*PingFang*", "/System/Library/Fonts/Supplemental/*",
            "/System/Library/Fonts/*", "/Library/Fonts/*.ttf",
            "C:/Windows/Fonts/sim*.tt?", "C:/Windows/Fonts/msyh*"]
    want = ("pingfang", "songti", "stheiti", "hiragino", "simsun", "simhei",
            "msyh", "arial unicode")
    seen = []
    for pat in pats:
        for f in glob.glob(pat):
            low = os.path.basename(f).lower()
            seen.append(low)
            if any(w in low for w in want) and low.endswith((".ttf", ".ttc", ".otf")):
                return low
    return next(iter(seen), "txt")


def _arrow(msp, tip, direction_deg, layer="尺寸标注", length=3.0, width=1.15):
    a = math.radians(direction_deg)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    b1 = (tip[0] - ux * length + px * width / 2,
          tip[1] - uy * length + py * width / 2)
    b2 = (tip[0] - ux * length - px * width / 2,
          tip[1] - uy * length - py * width / 2)
    msp.add_solid([tip, b1, b2], dxfattribs={"layer": layer})


def _seg(msp, p, q, layer):
    msp.add_line(p, q, dxfattribs={"layer": layer})


def _poly(msp, pts, layer, closed=False):
    msp.add_lwpolyline(list(pts), format="xy",
                       dxfattribs={"layer": layer, "closed": closed})


def _draw_view_edges(msp, plan, view):
    from .hlr import arc_angles
    ox, oy, s = view["ox"], view["oy"], plan.s
    for ad, pts, visible in view["edges"]:
        if len(pts) < 2:
            continue
        layer = "01粗实线" if visible else "08虚线"
        g = ad.GetType()
        if g == GeomAbs_Line:
            (x0, y0), (x1, y1) = pts[0], pts[-1]
            msp.add_line((x0 * s + ox, y0 * s + oy), (x1 * s + ox, y1 * s + oy),
                         dxfattribs={"layer": layer})
        elif g == GeomAbs_Circle:
            circ = ad.Circle()
            c = circ.Location()
            cx, cy, rr = c.X(), c.Y(), circ.Radius()
            if abs(circ.Axis().Direction().Z()) < 0.999:
                _poly(msp, [(p[0] * s + ox, p[1] * s + oy) for p in pts], layer)
            else:
                q0 = ad.Value(ad.FirstParameter())
                q1 = ad.Value(ad.LastParameter())
                closed = math.hypot(q0.X() - q1.X(), q0.Y() - q1.Y()) < 1e-6
                if closed:
                    msp.add_circle((cx * s + ox, cy * s + oy), rr * s,
                                   dxfattribs={"layer": layer})
                else:
                    a0, a1 = arc_angles(ad, (cx, cy),
                                        ad.FirstParameter(), ad.LastParameter())
                    msp.add_arc((cx * s + ox, cy * s + oy), rr * s, a0, a1,
                                dxfattribs={"layer": layer})
        else:
            _poly(msp, [(p[0] * s + ox, p[1] * s + oy) for p in pts], layer)


def _rot_text(msp, text, insert, rot, layer="文字", h=TEXT_H, style="CJK"):
    msp.add_text(text, dxfattribs={"layer": layer, "style": style,
                                   "height": h, "rotation": rot}
                 ).set_placement(insert)


def _render_dim(msp, r):
    dr = r.draw
    if not dr.get("text"):
        return
    if dr["kind"] == "lin":
        for sp, sq in dr["exts"]:
            _seg(msp, sp, sq, "尺寸标注")
        _seg(msp, dr["line"][0], dr["line"][1], "尺寸标注")
        for tip, ddeg in ((dr["arrows"][0], dr["rot"] + 180.0),
                          (dr["arrows"][1], dr["rot"])):
            _arrow(msp, tip, ddeg)
        _rot_text(msp, dr["text"], dr["insert"], dr["rot"], layer="文字")
    elif dr["kind"] == "dia-man":
        m1, m2 = dr["m1"], dr["m2"]
        _seg(msp, m1, m2, "尺寸标注")
        for tip, ref in ((m1, m2), (m2, m1)):
            dv = (ref[0] - tip[0], ref[1] - tip[1])
            ln = math.hypot(*dv)
            _arrow(msp, tip, math.degrees(math.atan2(dv[1], dv[0])))
        _rot_text(msp, dr["text"], dr["anchor"], dr["rot"], layer="文字")
    elif dr["kind"] == "rad-man":
        _seg(msp, dr["mpt"], dr["tail"], "尺寸标注")
        _arrow(msp, dr["mpt"], dr["arrow_deg"])
        _rot_text(msp, dr["text"], (dr["text_x"], dr["text_y"]), dr["rot"],
                  layer="文字")


def _render_leader(msp, r):
    dr = r.draw
    a, path, lines = dr["anchor"], dr["path"], dr["lines"]
    for i in range(len(path) - 1):
        _seg(msp, path[i], path[i + 1], "尺寸标注")
    arrow_at = path[0] if r.adjust else path[0]
    dv = (path[1][0] - path[0][0], path[1][1] - path[0][1])
    ln = math.hypot(*dv) or 1.0
    tip = (path[0][0] + dv[0] / ln * 2.2, path[0][1] + dv[1] / ln * 2.2)
    _arrow(msp, tip, math.degrees(math.atan2(-dv[1], -dv[0])))
    ty = dr["text_y_top"] - 2.4
    for line in lines:
        msp.add_text(line, dxfattribs={"layer": "文字", "style": "CJK",
                                       "height": 2.2}).set_placement(
                                           (dr["text_x"], ty))
        ty -= 4.2


def _render_datum(msp, r):
    dr = r.draw
    at, bc, letter = dr["at"], dr["bc"], r.name
    dx, dy = bc[0] - at[0], bc[1] - at[1]
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    base = (at[0] + ux * 2.6, at[1] + uy * 2.6)
    p1 = (base[0] + px * 1.5, base[1] + py * 1.5)
    p2 = (base[0] - px * 1.5, base[1] - py * 1.5)
    msp.add_lwpolyline([at, p1, p2], close=True, dxfattribs={"layer": "尺寸标注"})
    msp.add_lwpolyline([(bc[0] - 3, bc[1] - 2.2), (bc[0] + 3, bc[1] - 2.2),
                        (bc[0] + 3, bc[1] + 2.2), (bc[0] - 3, bc[1] + 2.2)],
                       close=True, dxfattribs={"layer": "尺寸标注"})
    join = ((bc[0], bc[1] - 2.2) if abs(uy) > abs(ux)
            else ((bc[0] - 3) if ux < 0 else (bc[0] + 3), bc[1]))
    _seg(msp, base, join, "尺寸标注")
    msp.add_text(letter, dxfattribs={"layer": "文字", "height": 3.0}
                 ).set_placement((bc[0] - 1.1, bc[1] - 1.4))


def _frame(msp, plan):
    msp.add_lwpolyline([(25, 5), (415, 5), (415, 292), (25, 292)], close=True,
                       dxfattribs={"layer": "01粗实线"})
    tb = (235.0, 5.0, 415.0, 61.0)
    msp.add_lwpolyline([(tb[0], tb[1]), (tb[2], tb[1]), (tb[2], tb[3]),
                        (tb[0], tb[3])], close=True,
                       dxfattribs={"layer": "01粗实线"})
    for y in (47.0, 33.0, 19.0):
        msp.add_line((tb[0], y), (tb[2], y), dxfattribs={"layer": "01细实线"})
    msp.add_line((330.0, tb[1]), (330.0, tb[3]), dxfattribs={"layer": "01细实线"})

    def t(label, value, x, y, h=3.2):
        msp.add_text(label, dxfattribs={"layer": "文字", "style": "CJK",
                                        "height": 2.4}).set_placement((x + 1.5, y + 9.5))
        msp.add_text(value, dxfattribs={"layer": "文字", "style": "CJK",
                                        "height": h}).set_placement((x + 1.5, y + 4.0))

    msp.add_text(plan.d.title, dxfattribs={"layer": "文字", "style": "CJK",
                                           "height": 4.5}).set_placement(
                                               ((tb[0] + tb[2]) / 2 - 33, 51.0))
    t("设计 DESIGN", "GLM-Agent", tb[0], 33.0)
    t("图号 DWG NO.", plan.d.dwg_no, 330.0, 33.0)
    t("比例 SCALE", f"{plan.d.scale:g} : 1", tb[0], 19.0)
    t("单位 UNIT", "mm · GB 第一角", 280.0, 19.0)
    t("材料 MATERIAL", plan.d.material, 330.0, 19.0)
    import time as _t
    t("日期 DATE", _t.strftime("%Y-%m-%d"), tb[0], 5.0)
    t("版本 REV", "1.0", 280.0, 5.0)
    t("张次 SHEET", "1 / 1", 330.0, 5.0)


def _notes(msp, plan):
    ny = plan.d.notes_zone[3]
    msp.add_text("技术要求 NOTES:", dxfattribs={"layer": "文字", "style": "CJK",
                                               "height": 3.0}).set_placement((28.0, ny))
    ny -= 4.6
    for rr in plan.d.notes:
        msp.add_text(rr, dxfattribs={"layer": "文字", "style": "CJK",
                                     "height": 2.2}).set_placement((28.0, ny))
        ny -= 4.2
    py = ny - 6.0
    msp.add_text("参数 PARAMETERS:", dxfattribs={"layer": "文字", "style": "CJK",
                                                "height": 3.0}).set_placement((28.0, py))
    py -= 4.6
    keys = list(plan.d.params.keys())
    rows = (len(keys) + 2) // 3
    for i, k in enumerate(keys):
        col, row = i // rows, i % rows
        v = plan.d.params[k]
        vs = f"{v:g}" if isinstance(v, float) else str(v)
        msp.add_text(f"{k}={vs}", dxfattribs={"layer": "文字", "style": "CJK",
                                              "height": 2.0}).set_placement(
                                                  (28.0 + col * 66.0, py - row * 3.4))


def render_plan(plan, dxf_path, png_path):
    """把求解后的 SheetPlan 渲染为 GB 图层 DXF + PNG 双产物。

    DXF 走 ezdxf（手工基元：细实线尺寸线/界线、实心箭头、旋转归一文字、
    GB 图层 01粗实线/08虚线/05中心线/尺寸标注/文字），PNG 经 PyMuPdf 由
    DXF 转出用于多模态互校验。同时写出便于版本 diff 的文本化动作日志。
    """
    t0 = time.time()
    import matplotlib
    matplotlib.use("Agg")

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4
    doc.header["$LWDISPLAY"] = 1
    doc.styles.add("CJK", font=_cjk_font_name())
    doc.linetypes.add("DASHED_GB", [3.0, 2.0, -1.0], description="细虚线 GB 2/1")
    doc.linetypes.add("CENTER_GB", [18.0, 12.0, -1.5, 0.0, -1.5],
                      description="细点画线 GB 12/1.5")
    for lname, color, lt, lw in _LAYERS:
        doc.layers.add(lname, color=color, linetype=lt, lineweight=lw)
    msp = doc.modelspace()

    for name, vw in plan.views.items():
        _draw_view_edges(msp, plan, vw)

    # 中心线
    for cd in plan.d.centers:
        if cd.arc:
            cx, cy, r, a0, a1 = cd.arc
            c0 = plan.tx(cd.view, (cx, cy))
            sweep = (a1 - a0) % 360.0          # DXF 语义: a0→a1 逆时针
            steps = max(8, int(sweep / 10))
            pts = []
            for i in range(steps + 1):
                a = math.radians(a0 + sweep * i / steps)
                pts.append((c0[0] + r * plan.s * math.cos(a),
                            c0[1] + r * plan.s * math.sin(a)))
            for i in range(len(pts) - 1):
                _seg(msp, pts[i], pts[i + 1], "05中心线")
        else:
            _seg(msp, plan.tx(cd.view, cd.p1), plan.tx(cd.view, cd.p2), "05中心线")

    # 尺寸
    for r in plan.resolved:
        if r.kind == "dim":
            _render_dim(msp, r)
    for r in plan.resolved:
        if r.kind == "leader":
            _render_leader(msp, r)
    for r in plan.resolved:
        if r.kind == "datum":
            _render_datum(msp, r)

    _frame(msp, plan)
    _notes(msp, plan)

    doc.saveas(dxf_path)
    chk = ezdxf.readfile(dxf_path)
    cnt = len(list(chk.modelspace()))
    from ezdxf.addons.drawing import Frontend, RenderContext, config, layout, pymupdf
    context = RenderContext(chk)
    backend = pymupdf.PyMuPdfBackend()
    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        color_policy=config.ColorPolicy.BLACK)
    Frontend(context, backend, config=cfg).draw_layout(chk.modelspace())
    page = layout.Page(420, 297, layout.Units.mm, margins=layout.Margins.all(2))
    png_path.write_bytes(backend.get_pixmap_bytes(page, fmt="png", dpi=220))
    print(f"    渲染 {Path(dxf_path).name} ({cnt} 实体) + "
          f"{Path(png_path).name} ({time.time() - t0:.1f}s)")


