"""六孔法兰盘 —— 最简 FTC 单零件示例。

几何体素合法用例（feature-tree-convention.md geometry tier 第 3 类）：
盘、凸台、孔刀全部完全含于圆柱基本体，无需草图；设计意图全部在命名参数里。
"""

from __future__ import annotations

import math
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql

OUT_DIR = Path(__file__).resolve().parent / "out"

FLANGE_OD = scad.var("flange_od", 100.0, comment="法兰盘外径", unit="mm")
FLANGE_T = scad.var("flange_t", 10.0, comment="法兰盘厚度", unit="mm")
HUB_OD = scad.var("hub_od", 55.0, comment="中心凸台外径", unit="mm")
HUB_TOP_Z = scad.var("hub_top_z", 30.0, comment="凸台顶面高度（自盘底 z=0）", unit="mm")
BORE_D = scad.var("bore_d", 30.0, comment="中心通孔直径", unit="mm")
PCD = scad.var("pcd", 78.0, comment="螺栓孔分布圆直径", unit="mm")
BOLT_D = scad.var("bolt_d", 11.0, comment="螺栓孔直径", unit="mm")
ROOT_R = scad.var("root_r", 3.0, comment="凸台根部圆角半径", unit="mm")
RIM_R = scad.var("rim_r", 2.0, comment="盘外缘上下圆角半径", unit="mm")

BOLT_N = 6  # 周向均布螺栓孔数
CUT_OVERSHOOT = 1.0  # 刀具超出量，保证切穿


def _value(value: scad.Var | float) -> float:
    if isinstance(value, scad.Var):
        return float(value.evaluate())
    return float(value)


def _p() -> dict:
    return {
        "od": _value(FLANGE_OD), "t": _value(FLANGE_T),
        "hub_od": _value(HUB_OD), "hub_top": _value(HUB_TOP_Z),
        "bore_d": _value(BORE_D), "pcd": _value(PCD),
        "bolt_d": _value(BOLT_D), "root_r": _value(ROOT_R),
        "rim_r": _value(RIM_R),
    }


def _cyl(radius: float, height: float, bottom_z: float, x: float = 0.0, y: float = 0.0) -> scad.Solid:
    return scad.make_cylinder_rsolid(
        radius=radius, height=height,
        bottom_face_center=(x, y, bottom_z), axis=(0.0, 0.0, 1.0))


def build_body() -> scad.Solid:
    p = _p()

    # 参数可行性守卫（设计参数，几何验证在外置 verify.py）
    assert p["bore_d"] < p["hub_od"], "中心孔须小于凸台外径"
    assert p["pcd"] / 2.0 + p["bolt_d"] / 2.0 + p["rim_r"] <= p["od"] / 2.0, \
        "螺栓孔到盘外缘的轮辐宽不足"
    assert p["pcd"] / 2.0 - p["bolt_d"] / 2.0 >= p["hub_od"] / 2.0 + p["root_r"], \
        "螺栓孔与凸台根部圆角干涉"
    assert p["hub_top"] - p["t"] >= p["root_r"], "根部圆角超出凸台高度"

    # ---- feature: flange-disc (build) ----
    body = _cyl(p["od"] / 2.0, p["t"], 0.0)

    # ---- feature: hub-boss (add) ----
    body = scad.union_rsolid(body, _cyl(p["hub_od"] / 2.0, p["hub_top"], 0.0))

    # ---- feature: center-bore (subtract) ----
    body = scad.cut_rsolid(body, _cyl(p["bore_d"] / 2.0, p["hub_top"] + 2.0 * CUT_OVERSHOOT, -CUT_OVERSHOOT))

    # ---- feature: bolt-holes (subtract) ----
    def _bolt_tools():
        return [
            _cyl(p["bolt_d"] / 2.0, p["t"] + 2.0 * CUT_OVERSHOOT, -CUT_OVERSHOOT,
                 x=p["pcd"] / 2.0 * math.cos(math.tau * i / BOLT_N),
                 y=p["pcd"] / 2.0 * math.sin(math.tau * i / BOLT_N))
            for i in range(BOLT_N)
        ]

    body = scad.cut_rsolid(body, _bolt_tools())

    # ---- feature: hub-root-fillet (modify) ----
    root_circle = 2.0 * math.pi * p["hub_od"] / 2.0
    root_selector = (
        ql.edges()
        .where(ql.prop("geom.type", "==", "CIRCLE"))
        .where(ql.prop("geom.center.z", ">=", p["t"] - 0.5))
        .where(ql.prop("geom.center.z", "<=", p["t"] + 0.5))
        .where(ql.prop("geom.length", ">=", root_circle * 0.9))
        .where(ql.prop("geom.length", "<=", root_circle * 1.1))
    )
    card = root_selector.resolve(body)
    print(f"hub-root card: n={len(card)} " + " ".join(f"len={e.get_length():.2f}" for e in card))
    body = scad.fillet_rsolid(
        solid=body, edges=root_selector.exactly(1),
        radius=p["root_r"], generated_faces_tag="fillet.hub_root")

    # ---- feature: rim-fillet (modify) ----
    rim_circle = 2.0 * math.pi * p["od"] / 2.0
    rim_selector = (
        ql.edges()
        .where(ql.prop("geom.type", "==", "CIRCLE"))
        .where(ql.prop("geom.length", ">=", rim_circle * 0.9))
    )
    card = rim_selector.resolve(body)
    print(f"rim card: n={len(card)} " + " ".join(f"len={e.get_length():.2f}" for e in card))
    body = scad.fillet_rsolid(
        solid=body, edges=rim_selector.exactly(2),
        radius=p["rim_r"], generated_faces_tag="fillet.rim")

    return body


@scad.part(id="flange-plate-6b", revision="1.0.0",
           project_root=Path(__file__).resolve().parents[2])
def build_flange_plate() -> scad.Part:
    """交付产品：六孔法兰盘（凸台根部 R3 + 盘外缘 R2 圆角终态）。"""
    return scad.make_part_rpart(
        part_id="flange-plate-6b",
        body=build_body(),
        name="Six-bolt flange plate",
    )


if __name__ == "__main__":
    result = build_flange_plate()
    body = result.value.body
    print(f"volume={body.get_volume():.1f}")
    print(f"faces={len(ql.faces().resolve(body))}")

    package_path = OUT_DIR / "flange_plate_6b.scadpkg"
    scad.capture(result, package_path)
    step_path = OUT_DIR / "flange_plate_6b.step"
    step_report = scad.exporter.export_product_package_to_step(package_path, step_path)
    png_path = OUT_DIR / "flange_plate_6b.png"
    scad.render_screenshot_rpath(shapes=body, output_path=str(png_path))

    print("product package", package_path)
    print("step", step_report.output_path)
    print("render", png_path)
