"""flange_plate: 参数化法兰盘（几何体素路线，无草图层）。

Coordinate convention (REQUIREMENTS.md):
  origin = 法兰轴线 ∩ 盘底平面; +Z 凸台方向.
  受控基准面: 盘底 z=0, 盘顶 z=flange_t, 凸台顶 z=boss_top_z; 回转轴 = Z 轴.

体素路线依据 (FTC geometry tier case 3): 盘/凸台/孔刀全部是完全含于圆柱基本体
的纯工具体 —— 基元即完整设计形状, 无需 profile. 一个 feature 一个块, 圆角最后.
"""
from __future__ import annotations

import math

import simplecadapi as scad
from simplecadapi import ql

# ---- Var-exposed tunable parameters (mm) ----
FLANGE_OD = scad.var("flange_od", 100.0, comment="法兰盘外径", unit="mm")
FLANGE_T = scad.var("flange_t", 10.0, comment="法兰盘厚度", unit="mm")
BOSS_OD = scad.var("boss_od", 55.0, comment="中心凸台外径", unit="mm")
BOSS_TOP_Z = scad.var("boss_top_z", 30.0, comment="凸台顶面到盘底距离", unit="mm")
BORE_D = scad.var("bore_d", 30.0, comment="中心通孔直径", unit="mm")
BOLT_D = scad.var("bolt_d", 11.0, comment="螺栓通孔直径", unit="mm")
BOLT_PCD = scad.var("bolt_pcd", 84.5,
                    comment="螺栓孔分布圆直径 PCD；USER 第 2 轮 78→88 被 G2a 拒（web 0.5<2）；"
                            "85 时 web==R_edge 精确相切（G2b 禁止，实证孔壁被圆角吞并），"
                            "按 0.5mm 网格取严格可行最大值 84.5", unit="mm")
BOLT_COUNT = scad.var("bolt_count", 8, comment="螺栓孔数（均布，首孔 +X/0°）；USER 第 2 轮 6→8")
BOSS_FILLET_R = scad.var("boss_fillet_r", 3.0, comment="凸台根部圆角", unit="mm")
EDGE_FILLET_R = scad.var("edge_fillet_r", 2.0, comment="法兰外缘上下圆角", unit="mm")
MIN_EDGE_WEB = scad.var("min_edge_web", 2.0,
                        comment="轮辐宽下限：孔边到外缘最小筋宽（ASSUMED=取 edge_fillet_r）", unit="mm")

# 刀具过切量（feature-ordering: 孔刀须越过进出面）
OVERSHOOT = 5.0


def _value(v: object) -> float:
    evaluate = getattr(v, "evaluate", None)
    return float(evaluate()) if callable(evaluate) else float(v)


def params() -> dict:
    return {
        "flange_od": _value(FLANGE_OD), "flange_t": _value(FLANGE_T),
        "boss_od": _value(BOSS_OD), "boss_top_z": _value(BOSS_TOP_Z),
        "bore_d": _value(BORE_D), "bolt_d": _value(BOLT_D),
        "bolt_pcd": _value(BOLT_PCD), "bolt_count": int(_value(BOLT_COUNT)),
        "boss_fillet_r": _value(BOSS_FILLET_R), "edge_fillet_r": _value(EDGE_FILLET_R),
        "min_edge_web": _value(MIN_EDGE_WEB),
    }


def assert_params(p: dict | None = None) -> None:
    """参数可行性守卫（REQUIREMENTS.md V3；不可行参数显式失败，绝不静默）。"""
    p = p if p is not None else params()
    # G1 中心孔 < 凸台（壁厚须同时扛住根部圆角）
    wall = (p["boss_od"] - p["bore_d"]) / 2.0
    assert p["bore_d"] < p["boss_od"], \
        f"G1 中心孔 {p['bore_d']} 不小于凸台外径 {p['boss_od']}"
    assert wall > p["boss_fillet_r"], \
        f"G1 凸台环形壁厚 {wall:.3f} 必须大于根部圆角 {p['boss_fillet_r']}"
    # G2 螺栓孔到外缘轮辐宽（两句：宽度下限 + 拓扑非相切）
    web = p["flange_od"] / 2.0 - p["bolt_pcd"] / 2.0 - p["bolt_d"] / 2.0
    assert web >= p["min_edge_web"], \
        (f"G2a 轮辐宽不足: web = {p['flange_od']}/2 - {p['bolt_pcd']}/2 - {p['bolt_d']}/2 "
         f"= {web:.3f} < min_edge_web = {p['min_edge_web']}")
    assert web > p["edge_fillet_r"], \
        (f"G2b 孔缘与外缘圆角相切: web = {web:.3f} 不大于 edge_fillet_r = {p['edge_fillet_r']}；"
         "web==R_edge 时孔口圆与圆角切圆内切，边圆角会吞并相切孔壁（2026-09-05 实证: "
         "8 孔 PCD 85 → 0° 孔壁消失、体积反常 +950），须严格大于")
    # G3 螺栓孔与凸台根部圆角不干涉
    gap = p["bolt_pcd"] / 2.0 - p["bolt_d"] / 2.0 - p["boss_od"] / 2.0 - p["boss_fillet_r"]
    assert gap > 0.0, \
        (f"G3 螺栓孔内缘侵入根部圆角区: PCD/2 - d/2 - boss_od/2 - R = {gap:.3f} <= 0")
    # G4 根部圆角不超凸台高出盘面的高度
    boss_h = p["boss_top_z"] - p["flange_t"]
    assert p["boss_fillet_r"] <= boss_h, \
        f"G4 根部圆角 {p['boss_fillet_r']} 超过凸台高出盘面高度 {boss_h:.3f}"


def _fact_card(slug: str, body: scad.Solid) -> None:
    """小事实卡（incremental grounding）：体积 + 面数，不打印整个实体。"""
    faces = ql.faces().resolve(body)
    print(f"[{slug}] volume={body.get_volume():.3f} faces={len(faces)}")


def _edge_card(slug: str, sel, body: scad.Solid) -> None:
    """选边卡（geometric-validation 选边证据门）：QL resolve 数量 + 逐边长度与中心。"""
    card = sel.resolve(body)
    print(f"[{slug}] selection card: n={len(card)}")
    for e in card:
        c = e.get_center()
        print(f"  len={e.get_length():.3f} center=({c.x:.2f},{c.y:.2f},{c.z:.2f})")


def _bolt_hole_tools(p: dict) -> list:
    """bolt-holes 块局部工具体：原型孔刀 + radial_pattern（首孔 +X，均布 360°）。"""
    proto = scad.make_cylinder_rsolid(
        radius=p["bolt_d"] / 2.0, height=p["flange_t"] + 2.0 * OVERSHOOT,
        bottom_face_center=(p["bolt_pcd"] / 2.0, 0.0, -OVERSHOOT), axis=(0.0, 0.0, 1.0))
    return scad.radial_pattern_rsolidlist(
        shape=proto, center=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0),
        count=p["bolt_count"], total_rotation_angle=360.0)


def build_solid() -> scad.Solid:
    """特征链（FTC: 一个 feature 一个块，块头注释即特征树）。"""
    p = params()
    assert_params(p)

    # ---- feature: flange-disc (build) ----
    body = scad.make_cylinder_rsolid(
        radius=p["flange_od"] / 2.0, height=p["flange_t"],
        bottom_face_center=(0.0, 0.0, 0.0), axis=(0.0, 0.0, 1.0))
    _fact_card("flange-disc", body)

    # ---- feature: center-boss (add) ----
    boss = scad.make_cylinder_rsolid(
        radius=p["boss_od"] / 2.0, height=p["boss_top_z"] - p["flange_t"],
        bottom_face_center=(0.0, 0.0, p["flange_t"]), axis=(0.0, 0.0, 1.0))
    body = scad.union_rsolid(body, boss)
    _fact_card("center-boss", body)

    # ---- feature: center-bore (subtract) ----
    bore_tool = scad.make_cylinder_rsolid(
        radius=p["bore_d"] / 2.0, height=p["boss_top_z"] + 2.0 * OVERSHOOT,
        bottom_face_center=(0.0, 0.0, -OVERSHOOT), axis=(0.0, 0.0, 1.0))
    body = scad.cut_rsolid(body, bore_tool)
    _fact_card("center-bore", body)

    # ---- feature: bolt-holes (subtract) ----
    bolt_tools = _bolt_hole_tools(p)
    body = scad.cut_rsolid(body, bolt_tools)
    _fact_card("bolt-holes", body)

    # ---- feature: boss-root-fillet (modify) ----
    # 选边卡先行（REQUIREMENTS 要求 2）：数量 + 边长，exactly(1) 承重，选边失败显式抛错
    root_sel = ql.edges().where(ql.and_(
        ql.prop("geom.type", "==", "CIRCLE"),
        ql.prop("geom.center.z", ">=", p["flange_t"] - 0.1),
        ql.prop("geom.center.z", "<=", p["flange_t"] + 0.1),
        ql.prop("geom.length", ">=", math.pi * p["boss_od"] - 0.5),
        ql.prop("geom.length", "<=", math.pi * p["boss_od"] + 0.5),
    )).exactly(1)
    _edge_card("boss-root-fillet", root_sel, body)
    body = scad.fillet_rsolid(solid=body, edges=root_sel,
                              radius=p["boss_fillet_r"],
                              generated_faces_tag="fillet.boss_root")
    _fact_card("boss-root-fillet", body)

    # ---- feature: flange-edge-fillets (modify) ----
    edge_sel = ql.edges().where(ql.and_(
        ql.prop("geom.type", "==", "CIRCLE"),
        ql.prop("geom.length", ">=", math.pi * p["flange_od"] - 0.5),
        ql.prop("geom.length", "<=", math.pi * p["flange_od"] + 0.5),
        ql.or_(
            ql.and_(ql.prop("geom.center.z", ">=", -0.1),
                    ql.prop("geom.center.z", "<=", 0.1)),
            ql.and_(ql.prop("geom.center.z", ">=", p["flange_t"] - 0.1),
                    ql.prop("geom.center.z", "<=", p["flange_t"] + 0.1)),
        ),
    )).exactly(2)
    _edge_card("flange-edge-fillets", edge_sel, body)
    body = scad.fillet_rsolid(solid=body, edges=edge_sel,
                              radius=p["edge_fillet_r"],
                              generated_faces_tag="fillet.flange_edge")
    _fact_card("flange-edge-fillets", body)

    return body


@scad.part(id="flange-plate", revision="1.0.0")
def build_flange_plate() -> scad.Solid:
    """产品零件入口（durable 导出用；验证脚本直接用 build_solid）。"""
    return build_solid()


if __name__ == "__main__":
    result = build_flange_plate()
    print(f"part built: {type(result).__name__}")
