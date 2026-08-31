"""u_link shell: 下半件外壳（两刀工艺，平底 @ 第一刀平面）。

用户定序（S11 修正版）：
  第一刀 @ back_y - boss_h - wall_t (=0.5)：切掉下半部 → shell 平底面；
  第二刀 @ back_y (=7.5)：分离壳体与上件。
shell = rod ∩ [0.5, 7.5] − 内偏移扫掠∩[boss_tip(2.5), 7.5]
→ 平底 0.5（整弦截面）+ 实体地板 [0.5, 2.5]（顶面贴 boss 尖端）
+ 轮廓壁 wall_t 的腔体 [2.5, 7.5]（容 boss+线束）。
两端腔高方口走线；地板沉头孔（Ø2.7 通 + 90° 锥口自平底向上）。薄壁不倒角。
"""
from __future__ import annotations

import math
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql

import u_link as U

NOTCH_W = scad.var("notch_w", 9.0, comment="走线口宽（z 向）；S11 用户定向加大", unit="mm")
NOTCH_SILL = scad.var("notch_sill", 0.5, comment="走线口上下台阶高（离地板顶/rim；S12 口角圆角承载体）", unit="mm")
NOTCH_RR = scad.var("notch_rr", 1.5, comment="走线口角圆角半径（rounded-rect 轮廓，防割手；S12 用户定向）", unit="mm")
CB_DIAMETER = scad.var("csink_d", 5.4, comment="沉头孔锥口大端直径（M3 沉头）", unit="mm")
CB_DEPTH = scad.var("csink_depth", 1.35, comment="沉头锥深（< wall_t-0.5，90°锥）", unit="mm")
SAFE_R = scad.var("safe_fillet_r", 0.6, comment="防割手圆角半径（平底外缘；走线口防割由 notch_rr 轮廓承担）", unit="mm")

TAG_SHELL_RIM = "feature.shell_rim_face"
TAG_SHELL_FLOOR = "feature.shell_hole_floor"  # 平底面（第一刀平面）


def _value(value: object) -> float:
    evaluate = getattr(value, "evaluate", None)
    return float(evaluate()) if callable(evaluate) else float(value)


def shell_params() -> dict:
    return {"notch_w": _value(NOTCH_W), "notch_sill": _value(NOTCH_SILL),
            "notch_rr": _value(NOTCH_RR),
            "csink_d": _value(CB_DIAMETER), "csink_depth": _value(CB_DEPTH),
            "safe_fillet_r": _value(SAFE_R)}


def floor_band(p: dict) -> tuple[float, float]:
    """shell 地板带 [底, 顶] = 第一刀平面, boss 尖端平面。"""
    by = U.back_y(p)
    return by - p["boss_h"] - p["wall_t"], by - p["boss_h"]


def build_shell_body() -> scad.Solid:
    p = dict(U.params(), **shell_params())
    by = U.back_y(p)
    fb, ft = floor_band(p)  # 0.5, 2.5
    r = p["rod_d"] / 2.0

    # 第一刀 @ fb：切掉下半部（平底面产生于此）
    piece = scad.cut_rsolid(U.build_u_rod(), U._big_box(p, fb, fb - 60.0))
    # 第二刀 @ by：分离——保留带 [fb, by]
    shell = scad.cut_rsolid(piece, U._big_box(p, by + 60.0, by))
    # 挖腔：内偏移扫掠 ∩ [ft, by]（地板保持实体）
    cavity = scad.intersect_rsolid(U._eroded_sweep(p), U._big_box(p, by, ft))
    shell = scad.cut_rsolid(shell, cavity)

    # 走线口（S12 防割手版）：rounded-rect 轮廓（角 R=notch_rr 圆角融入源型，
    # 免 fillet——矩形口边缘 fillet 在口角三面圆角相遇处内核稳定崩溃，s12 取证）；
    # 上下各留 sill 台阶（不与地板顶/rim 面共面）
    notch_xc = p["L"] / 2.0 - p["r_corner"] + 1.45 * r
    sill = p["notch_sill"]
    notch_h = by - ft - 2.0 * sill
    notch_tools = [
        U._rounded_rect_prism(
            sx * notch_xc - (r + 4.0) / 2.0, sx * notch_xc + (r + 4.0) / 2.0,
            ft + sill, ft + sill + notch_h,
            -p["notch_w"] / 2.0, p["notch_w"] / 2.0, p["notch_rr"])
        for sx in (-1, 1)
    ]
    shell = scad.cut_rsolid(shell, notch_tools)

    # 防割手圆角（S12 用户定向）：平底外缘 R=safe_fillet_r（孔前执行）
    bottom_face = ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", fb - 0.1),
        ql.prop("geom.center.y", "<=", fb + 0.1),
        ql.prop("geom.area", ">=", 500.0),
    )).resolve(shell)
    assert len(bottom_face) == 1, f"平底面识别异常 n={len(bottom_face)}"
    rim_edges = list(bottom_face[0].get_outer_wire().get_edges())
    assert len(rim_edges) >= 4, f"平底外缘边识别异常 n={len(rim_edges)}"
    shell = scad.fillet_rsolid(solid=shell, edges=rim_edges, radius=p["safe_fillet_r"])

    # 沉头螺栓孔：Ø2.7 通地板 + 自平底 90° 锥口（贴 boss 尖端拧入）
    hole_r = p["boss_hole_d"] / 2.0
    cb_r = p["csink_d"] / 2.0
    tools = []
    for sx in (-1, 1):
        bx = sx * p["boss_x"]
        tools.append(scad.make_cylinder_rsolid(
            radius=hole_r, height=p["wall_t"] + 2.0,
            bottom_face_center=(bx, fb - 1.0, 0.0), axis=(0.0, 1.0, 0.0)))
        tools.append(scad.make_cone_rsolid(
            bottom_radius=cb_r, top_radius=hole_r, height=p["csink_depth"],
            bottom_face_center=(bx, fb, 0.0), axis=(0.0, 1.0, 0.0)))
    shell = scad.cut_rsolid(shell, tools)
    scad.apply_tag(shape=shell, tag="role.shell")
    return shell


def _flat_bottom_selector(p: dict):
    """平底面（第一刀平面）：整弦截面大面积 −Y 面。"""
    fb = floor_band(p)[0]
    return ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", fb - 0.1),
        ql.prop("geom.center.y", "<=", fb + 0.1),
        ql.prop("geom.area", ">=", 500.0),
    ))


def _shell_rim_selector(p: dict):
    """rim（第二刀平面 7.5，可能被 seam 分面——全部命中）。"""
    y = U.back_y(p)
    return ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", ">=", 0.999),
        ql.prop("geom.center.y", ">=", y - 0.1),
        ql.prop("geom.center.y", "<=", y + 0.1),
        ql.prop("geom.area", ">=", 100.0),
    ))


@scad.part(id="u-link-shell", revision="1.0.0",
           project_root=Path(__file__).resolve().parents[2])
def build_shell_part() -> scad.Part:
    """交付零件：下半件外壳（建模于安装位，平底=第一刀平面）。"""
    p = dict(U.params(), **shell_params())
    body = build_shell_body()
    body = scad.apply_tag_rselection(
        scope=body, targets=_flat_bottom_selector(p), tag=TAG_SHELL_FLOOR)
    body = scad.apply_tag_rselection(
        scope=body, targets=_shell_rim_selector(p), tag=TAG_SHELL_RIM)
    part = scad.make_part_rpart(part_id="u-link-shell", body=body, name="U link shell")
    connector = scad.make_placement_connector_rconnector(
        connector_id="shell_rim",
        placement=scad.make_placement_rplacement(
            origin=(0.0, U.back_y(p), 0.0), x_axis=(1.0, 0.0, 0.0), y_axis=(0.0, 0.0, 1.0)),
        name="Shell rim datum (z out -Y)")
    return scad.add_connector_rpart(part=part, connector=connector)


if __name__ == "__main__":
    result = build_shell_part()
    body = result.value.body
    print(f"shell volume={body.get_volume():.3f} faces={len(body.get_faces())}")
