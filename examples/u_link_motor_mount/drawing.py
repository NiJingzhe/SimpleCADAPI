"""drawing: 声明式生成 u_link 上件与 shell 盖子两张 GB 工程零件图 (比例 2:1)。

标注语义模型 (simplecadapi.dxf_engine):
  DatumDecl  基准体系 —— 定位尺寸的出发点
  DimDecl    kind=size|position|overall, datum=基准引用, covers=参数追溯
引擎: 规划(报告) → 渲染 (DXF+PNG)

用法: uv run python examples/u_link_motor_mount/drawing.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import u_link   # noqa: E402
import shell    # noqa: E402
from simplecadapi.dxf_engine import (CenterDecl, DatumDecl, DimDecl,  # noqa: E402
                                     LeaderDecl, SheetDecl, SheetPlan,
                                     ViewDecl)

OUT_DIR = HERE / "out"
OUT_DIR.mkdir(exist_ok=True)


def u_link_sheet() -> SheetDecl:
    PU = u_link.params()
    by = u_link.back_y(PU)
    boss_bot = by - PU["boss_h"]
    reqs = [
        "1. 第一角画法 (GB/T 14692)，视图按规定位置配置；绘图比例 2:1，单位 mm。",
        "2. 基准体系: A=底部圆柱轴线(y=0，主基准) B=对称面(x=0)",
        f"    C=剖分面(y={by:g}，与盖子 ULM-TVS-002 装配)。",
        f"3. 全局倒角 R{PU['fillet_r']:g}；拐角中心线半径 R{PU['r_corner']:g}；薄壁不倒角。",
        f"4. 每槽走线窗 {PU['cable_w_w']:g}×{PU['cable_w_h']:g} (角 R{PU['cable_w_rr']:g})，",
        f"    底距安装面 {PU['cable_w_off']:g} (cable_w_off)，相位 "
        f"{PU['cable_w_phase']:g}° 对角布置，每槽 4 窗。",
        (f"5. boss 自攻孔 2-×⌀{PU['boss_hole_d']:g}×{PU['boss_hole_depth']:g} 深，"
         f"柱 ⌀{PU['boss_d']:g}×{PU['boss_h']:g}，位 x=±{PU['boss_x']:g}，"
         f"筋 t{PU['rib_t']:g} 边{PU['rib_len']:g}。"),
        (f"6. 安装面−剖分面壁厚 = {PU['wall_t']:g} (验证不变量 P5)；"
         "未注公差 GB/T 1804-m。"),
    ]
    up = u_link.build_u_link_part().value.body
    return SheetDecl(
        title="U 形电机连杆 · 剖分上件", dwg_no="ULM-TVS-001", scale=2.0,
        front="front", anchor=(209.5, 175.0),
        views=[
            ViewDecl("front", up.wrapped, (0, 0, 1), (1, 0, 0), anchor=(209.5, 175.0)),
            ViewDecl("left", up.wrapped, (-1, 0, 0), (0, 0, 1),
                     align={"to": "front", "side": "right", "gap": 55.0}),
            ViewDecl("top", up.wrapped, (0, 1, 0), (1, 0, 0),
                     align={"to": "front", "side": "below", "gap": 50.0}),
        ],
        datums=[
            DatumDecl("A", "axis", "front", at=(-59.0, 0),
                      box_off=(-11.0, -11.0), desc="底部圆柱轴线(y=0)"),
            DatumDecl("B", "plane", "front", at=(0, PU["D"] + 3),
                      box_off=(17.0, 9.0), desc="对称面(x=0)"),
            DatumDecl("C", "plane", "front", at=(8.0, by),
                      box_off=(26.0, -13.0), desc="剖分面(y=7.5)"),
        ],
        centers=[
            CenterDecl("front", p1=(0, boss_bot - 1.5), p2=(0, PU["D"] + 2)),
            CenterDecl("front", p1=(-59.0, 0), p2=(59.0, 0)),
            CenterDecl("front", p1=(-40, by - 1.5), p2=(-40, PU["D"] + 2)),
            CenterDecl("front", p1=(40, by - 1.5), p2=(40, PU["D"] + 2)),
            CenterDecl("front", arc=(-23.0, 17.0, 17.0, 180.0, 270.0)),
            CenterDecl("front", arc=(23.0, 17.0, 17.0, 270.0, 0.0)),
            CenterDecl("left", p1=(0, boss_bot - 1.5), p2=(0, PU["D"] + 2)),
            CenterDecl("left", p1=(-19.0, PU["D"]), p2=(19.0, PU["D"])),
            CenterDecl("top", p1=(0, -16.0), p2=(0, 16.0)),
            CenterDecl("top", p1=(-59.0, 0), p2=(59.0, 0)),
            CenterDecl("top", p1=(-40, -19.0), p2=(-40, 19.0)),
            CenterDecl("top", p1=(40, -19.0), p2=(40, 19.0)),
        ],
        dims=[
            DimDecl("position", "front", "linear", "L", value=PU["L"],
                    p1=(-40, 0), p2=(40, 0), datum="B",
                    side="top", row=0),
            DimDecl("size", "front", "linear", "D", value=PU["D"],
                    p1=(40, 0), p2=(40, PU["D"]), datum="A",
                    side="right", row=0),
            DimDecl("position", "front", "linear", "back_y", value=by,
                    p1=(-40, 0), p2=(-40, by), datum="A",
                    side="left", row=0, dec=1, covers=["back_cut_frac"]),
            DimDecl("position", "front", "linear", "d_motor/2",
                    value=PU["d_motor"] / 2, p1=(-40, 0), p2=(-40, PU["d_motor"] / 2),
                    datum="A", side="left", row=3, dec=1, covers=["d_motor"]),
            DimDecl("size", "front", "radius", "r_corner",
                    center=(-23.0, 17.0), radius=PU["r_corner"],
                    value=PU["r_corner"], at=250.0, covers=["r_corner"]),
            DimDecl("size", "top", "diameter", "rod_d", center=(PU["L"] / 2, 0),
                    radius=PU["rod_d"] / 2, value=PU["rod_d"], at=35.0,
                    out=14.0, covers=["rod_d"]),
            DimDecl("size", "top", "diameter", "rod_d−t",
                    center=(-PU["L"] / 2, 0),
                    radius=(PU["rod_d"] - PU["thickness"]) / 2,
                    value=PU["rod_d"] - PU["thickness"], at=145.0, out=16.0,
                    covers=["thickness"]),
            DimDecl("overall", "top", "linear", "rod_d", p1=(55, -15),
                    p2=(55, 15), value=PU["rod_d"], side="right", row=0),
        ],
        leaders=[
            LeaderDecl("front", anchor=(-45.0, 12.0),
                       lines=[f"走线窗 {PU['cable_w_w']:g}×{PU['cable_w_h']:g} "
                              f"(cable_w_w×cable_w_h)",
                              f"底距安装面 {PU['cable_w_off']:g} (cable_w_off)"],
                       off=(-73.5, 46.0), dx_dir=-1.0, name="走线窗"),
        ],
        notes=reqs, params=PU)


def shell_sheet() -> SheetDecl:
    PU, PS = u_link.params(), shell.shell_params()
    by = u_link.back_y(PU)
    fb0, ft = shell.floor_band(PU)
    notch_xc = PU["L"] / 2 - PU["r_corner"] + 1.45 * PU["rod_d"] / 2
    reqs = [
        "1. 第一角画法 (GB/T 14692)，视图按规定位置配置；绘图比例 2:1，单位 mm。",
        f"2. 基准体系: A=rim 装配面(y={by:g}，与上件 ULM-TVS-001 贴合)",
        "    B=对称面(x=0)。",
        (f"3. 两刀工艺: 平底 y={fb0:g} (第一刀面)，rim y={by:g} (第二刀面)；"
         f"腔体容 boss+线束。"),
        (f"4. 两端走线口 {PU['rod_d'] / 2 + 4:g}×"
         f"{by - fb0 - 2 * PS['notch_sill']:g} (角 R{PS['notch_rr']:g})，"
         f"中心 x=±{notch_xc:g}。"),
        (f"5. 沉头孔 2-×⌀{PU['boss_hole_d']:g} 通 (位 x=±{PU['boss_x']:g})，"
         f"沉头 ⌀{PS['csink_d']:g}×90° 自平底。"),
        f"6. 平底外缘防割圆角 R{PS['safe_fillet_r']:g}；薄壁不倒角；",
        "    未注公差 GB/T 1804-m。",
    ]
    sh = shell.build_shell_part().value.body
    return SheetDecl(
        title="U 形电机连杆 · 外壳盖", dwg_no="ULM-TVS-002", scale=2.0,
        front="front", anchor=(207.5, 200.0),
        views=[
            ViewDecl("front", sh.wrapped, (0, 0, 1), (1, 0, 0), anchor=(207.5, 200.0)),
            ViewDecl("top", sh.wrapped, (0, 1, 0), (1, 0, 0),
                     align={"to": "front", "side": "below", "gap": 54.0}),
        ],
        datums=[
            DatumDecl("A", "plane", "front", at=(-8.0, by),
                      box_off=(-26.0, -19.0), desc=f"rim 装配面(y={by:g})"),
            DatumDecl("B", "plane", "front", at=(0, by + 3),
                      box_off=(9.0, 6.0), desc="对称面(x=0)"),
        ],
        centers=[
            CenterDecl("front", p1=(0, fb0 - 1.5), p2=(0, by + 4)),
            CenterDecl("front", p1=(-59.0, 0), p2=(59.0, 0)),
            CenterDecl("front", p1=(-12, fb0 - 1.5), p2=(-12, by + 4)),
            CenterDecl("front", p1=(12, fb0 - 1.5), p2=(12, by + 4)),
            CenterDecl("top", p1=(0, -19.0), p2=(0, 19.0)),
            CenterDecl("top", p1=(-59.0, 0), p2=(59.0, 0)),
            CenterDecl("top", p1=(-12, -6.0), p2=(-12, 6.0)),
            CenterDecl("top", p1=(12, -6.0), p2=(12, 6.0)),
        ],
        dims=[
            DimDecl("overall", "front", "linear", "L+rod_d", p1=(-55, fb0),
                    p2=(55, fb0), value=PU["L"] + PU["rod_d"], side="bottom",
                    row=0),
            DimDecl("position", "front", "linear", "2×boss_x",
                    p1=(-PU["boss_x"], fb0), p2=(PU["boss_x"], fb0),
                    value=2 * PU["boss_x"], datum="B", side="bottom", row=1),
            DimDecl("overall", "front", "linear", "boss_h+wall_t",
                    p1=(-55, fb0), p2=(-55, by), value=by - fb0, side="left",
                    row=0, covers=["boss_h", "wall_t"]),
            DimDecl("size", "front", "linear", "wall_t", p1=(-55, fb0),
                    p2=(-55, ft), value=ft - fb0, side="left", row=1,
                    covers=["wall_t"]),
            DimDecl("size", "top", "diameter", "rod_d", center=(PU["L"] / 2, 0),
                    radius=PU["rod_d"] / 2, value=PU["rod_d"], at=35.0, out=19.0,
                    covers=["rod_d"]),
            DimDecl("overall", "top", "linear", "rod_d", p1=(55, -15),
                    p2=(55, 15), value=PU["rod_d"], side="right", row=0),
            DimDecl("size", "top", "linear", "notch_w",
                    p1=(-notch_xc, -PS["notch_w"] / 2),
                    p2=(-notch_xc, PS["notch_w"] / 2),
                    value=PS["notch_w"], side="left", row=0,
                    covers=["notch_w"]),
        ],
        notes=reqs, params=PS)


def main() -> None:
    t0 = time.time()
    for decl, tag in ((u_link_sheet(), "上件"), (shell_sheet(), "盖子")):
        print(f"[{tag}] {decl.title}")
        plan = SheetPlan(decl).solve()
        print(plan.report())
        plan.render(OUT_DIR / f"{'u_link' if tag == '上件' else 'shell'}_drawing.dxf",
                    OUT_DIR / f"{'u_link' if tag == '上件' else 'shell'}_drawing.png")
    print(f"两张图纸完成，用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
