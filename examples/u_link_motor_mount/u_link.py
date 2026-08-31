"""u_link_motor_mount: 参数化 U 形电机连杆（机械臂 link，通用电机安装）。

Coordinate convention (REQUIREMENTS.md):
  origin = 底部圆柱轴线中点; +X 沿连杆指向右臂; +Y 向上(U 开口); +Z 横向.
  受控基准面: 背面 y=back_y=rod_d/2*(2*back_cut_frac-1)（默认 75% 高度处 7.5）,
  安装面(槽底) y=D_motor/2, 臂端面 y=D; 臂轴线 x=±L/2.
"""
from __future__ import annotations

import math
from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql

# ---- Var-exposed tunable parameters (mm) ----
L = scad.var("L", 80.0, comment="臂轴跨距/底宽（两电机轴线间距）", unit="mm")
D = scad.var("D", 20.0, comment="臂端面高度（自 y=0）；2026-08-26 用户定向 40->20", unit="mm")
ROD_D = scad.var("rod_d", 30.0, comment="U 形圆杆直径", unit="mm")
THICKNESS = scad.var("thickness", 6.0, comment="电机槽壁余量（槽壁厚=thickness/2）", unit="mm")
D_MOTOR = scad.var("d_motor", 19.0, comment="电机深度（槽底 y=d_motor/2）；S11 用户定向加深 30->19，安装面到 back face = 标准壁厚 wall_t", unit="mm")
R_CORNER = scad.var("r_corner", 17.0, comment="拐角中心线圆弧半径（须∈(rod_d/2, D)）；随 D=20 联动 20->17", unit="mm")
FILLET_R = scad.var("fillet_r", 1.2, comment="全局倒角半径（<thickness/4）", unit="mm")
BACK_CUT_FRAC = scad.var("back_cut_frac", 0.75, comment="背切平面位置（底管高度百分比；0.5=中心线，0.75=中心线上移半径一半）；2026-08-26 用户定向 0.5->0.75")
# S10 剖分+轮廓腔参数（2026-08-26 用户定向：弃方形腔，75% 剖分两件+shell）
WALL_T = scad.var("wall_t", 2.0, comment="shell 壁厚=腔内偏移量（轮廓贴合由 r-wall_t 扫掠实现）", unit="mm")
BOSS_H = scad.var("boss_h", 5.0, comment="boss 柱高=剖分面下方悬臂长（腔带高）", unit="mm")
BOSS_D = scad.var("boss_d", 5.0, comment="boss 柱外径", unit="mm")
BOSS_X = scad.var("boss_x", 12.0, comment="boss 轴 x 位（±，剖分面中央区）", unit="mm")
BOSS_HOLE_D = scad.var("boss_hole_d", 2.7, comment="boss 中心自攻孔径（=shell 底孔内径，用户指定一致）", unit="mm")
BOSS_HOLE_DEPTH = scad.var("boss_hole_depth", 3.0, comment="boss 盲孔深（自柱底向上，留底 ≥0.5）", unit="mm")
RIB_T = scad.var("rib_t", 1.2, comment="三角筋厚", unit="mm")
RIB_LEN = scad.var("rib_len", 3.0, comment="三角筋水平边长（沿剖分面外伸）", unit="mm")
GUSSET_CHAMFER = scad.var("gusset_chamfer", 0.3, comment="三角筋斜边倒角（先于全局圆角执行）", unit="mm")
# S13 电机槽走线窗参数（2026-08-26 用户定向）
CABLE_W_OFF = scad.var("cable_w_off", 3.0, comment="走线窗底边高于安装面距离（用户规定 ∈[3,5]，推荐 3）", unit="mm")
CABLE_W_H = scad.var("cable_w_h", 5.0, comment="走线窗高（y 向）", unit="mm")
CABLE_W_W = scad.var("cable_w_w", 10.0, comment="走线窗宽（周向弦长）；S14 用户定向 5->10（周向 2 倍）", unit="mm")
CABLE_W_RR = scad.var("cable_w_rr", 1.2, comment="走线窗角圆角（rounded-rect 源型，防割手免 fillet）", unit="mm")
CABLE_W_PHASE = scad.var("cable_w_phase", 45.0, comment="走线窗相位（相对 +X；45°=对角布置，避让内向盲区——s13 探针: 0/180° 内向在窗低段撞拐角熔合区）", unit="deg")
SHELL_HOLE_D = scad.var("shell_hole_d", 2.7, comment="shell 底螺栓孔径（=boss_hole_d）", unit="mm")

# 命名特征面 tag（QL 索引入口）
TAG_MOUNT_LEFT = "feature.motor_mount_floor_left"
TAG_MOUNT_RIGHT = "feature.motor_mount_floor_right"
TAG_BACK = "feature.back_face"


def _value(value: object) -> float:
    evaluate = getattr(value, "evaluate", None)
    return float(evaluate()) if callable(evaluate) else float(value)


def params() -> dict:
    return {
        "L": _value(L), "D": _value(D), "rod_d": _value(ROD_D),
        "thickness": _value(THICKNESS), "d_motor": _value(D_MOTOR),
        "r_corner": _value(R_CORNER), "fillet_r": _value(FILLET_R),
        "back_cut_frac": _value(BACK_CUT_FRAC),
        "wall_t": _value(WALL_T), "boss_h": _value(BOSS_H),
        "boss_d": _value(BOSS_D), "boss_x": _value(BOSS_X),
        "boss_hole_d": _value(BOSS_HOLE_D), "boss_hole_depth": _value(BOSS_HOLE_DEPTH),
        "rib_t": _value(RIB_T), "rib_len": _value(RIB_LEN),
        "gusset_chamfer": _value(GUSSET_CHAMFER),
        "shell_hole_d": _value(SHELL_HOLE_D),
        "cable_w_off": _value(CABLE_W_OFF), "cable_w_h": _value(CABLE_W_H),
        "cable_w_w": _value(CABLE_W_W), "cable_w_rr": _value(CABLE_W_RR),
        "cable_w_phase": _value(CABLE_W_PHASE),
    }


def back_y(p: dict) -> float:
    """背切平面 y = r*(2f-1)：f=0.5 中心线，f=0.75 即底管高度 75% 处。"""
    return (p["rod_d"] / 2.0) * (2.0 * p["back_cut_frac"] - 1.0)


def assert_params() -> None:
    """参数约束链（REQUIREMENTS.md；S1-H5/S6/S7 探针证明退化参数须显式守卫）。"""
    p = params()
    r = p["rod_d"] / 2.0
    rp = (p["rod_d"] - p["thickness"]) / 2.0
    depth = p["D"] - p["d_motor"] / 2.0
    assert p["d_motor"] / 2.0 < p["D"], "d_motor/2 必须小于 D（槽底低于臂端）"
    assert p["r_corner"] > r, "r_corner 必须大于杆半径（拐角内退化会静默产出坏几何）"
    # 端面环宽 = r-rp = thickness/2，环内外两边同时倒角，2*fr 不得相遇吃穿环
    # （S6 变体 thickness=8/fr=3 证明 fr<thickness/2 不充分；S4-H5 R2.0 炸的真因亦在此）
    assert p["fillet_r"] < p["thickness"] / 4.0, \
        "fillet_r 必须小于 thickness/4（端面环宽 thickness/2 内双侧倒角不得相遇）"
    assert p["L"] > 2.0 * p["r_corner"], "L 必须大于 2*r_corner（底部直段存在）"
    assert p["D"] > p["r_corner"], "D 必须大于 r_corner（臂直段存在）"
    # S6 新增（探针 H2/H3：旧守卫放行、内核 fillet 崩溃）：
    assert p["fillet_r"] < rp, "fillet_r 必须小于槽半径 (rod_d-thickness)/2（槽底倒角吃穿槽壁）"
    assert p["fillet_r"] < depth, "fillet_r 必须小于槽深 D-d_motor/2（槽底倒角越过槽口）"
    # S7 新增（背切平面范围）：
    f = p["back_cut_frac"]
    assert 0.5 <= f < 1.0, "back_cut_frac 须∈[0.5,1)（0.5=中心线半切；>=1 切穿底管）"
    assert back_y(p) < p["d_motor"] / 2.0, \
        "背切平面必须低于槽底 d_motor/2（安装面到背面须留壁厚）"
    # S11 用户定向：安装面到 back face 厚度不小于标准壁厚 wall_t
    assert p["d_motor"] / 2.0 >= back_y(p) + p["wall_t"], \
        "d_motor/2 须 >= back_y+wall_t（电机安装面到 back face 至少标准壁厚）"
    # S10 新增（剖分+轮廓腔+boss 可行性）：
    by = back_y(p)
    wall_t = p["wall_t"]
    opening_half = ((r - wall_t) ** 2 - by ** 2) ** 0.5  # 腔带顶部开口 z 半宽
    assert 0.5 <= wall_t <= r / 3.0, "wall_t 须∈[0.5, rod_d/6]（壁过薄无法制造, 过厚腔不可用）"
    assert p["boss_h"] < by - 2.0, "boss_h 须 < back_y-2（腔带底部留结构余量）"
    assert p["boss_hole_depth"] <= p["boss_h"] - 0.5, "boss 盲孔须留底 ≥0.5"
    assert p["boss_hole_d"] / 2.0 + 0.5 + 0.3 <= p["boss_d"] / 2.0 - 0.3, \
        "boss 孔壁过薄（孔半径+0.5 ≤ 柱半径-0.3）"
    assert p["boss_d"] / 2.0 + p["rib_len"] <= opening_half - 0.5, \
        "±z 筋须在腔开口内（boss_r+rib_len ≤ sqrt((r-wall_t)²-back_y²)-0.5）"
    assert p["boss_x"] + p["boss_d"] / 2.0 + p["rib_len"] <= p["L"] / 2.0 - p["r_corner"] - 2.0, \
        "±x 筋须在底部直段腔内（远离拐角）"
    assert p["rib_t"] >= 2.0 * p["gusset_chamfer"] + 0.3, "筋厚须容双侧倒角"
    # S13 走线窗（用户规定: 底边距安装面 ∈[3,5]；推荐 3）
    assert 3.0 <= p["cable_w_off"] <= 5.0, "cable_w_off 须∈[3,5]（用户规定：≥3 且 ≤5）"
    cw_top = p["d_motor"] / 2.0 + p["cable_w_off"] + p["cable_w_h"]
    assert cw_top <= p["D"] - 2.0, "窗顶须低于臂端面圆角区（floor+off+h ≤ D-2）"
    assert p["cable_w_rr"] < p["cable_w_w"] / 2.0 and p["cable_w_rr"] < p["cable_w_h"] / 2.0, \
        "窗角圆角须小于半宽/半高"
    assert p["cable_w_w"] <= 1.6 * rp, "窗宽不得吃穿窗间壁（w ≤ 1.6×槽半径；w=10/rp=12 时窗间弧余 34mm）"


def _u_path_edges(p: dict):
    """U 路径 5 边：左臂下 → 左拐角弧 → 底部右 → 右拐角弧 → 右臂上（XY 平面, z=0）。"""
    l, d, r_c = p["L"], p["D"], p["r_corner"]
    xl, xr = -l / 2.0, l / 2.0
    s2 = math.sqrt(2.0) / 2.0
    cl, cr = (xl + r_c, r_c), (xr - r_c, r_c)
    return [
        scad.make_segment_redge(start=(xl, d, 0.0), end=(xl, r_c, 0.0)),
        scad.make_three_point_arc_redge(
            start=(xl, r_c, 0.0),
            middle=(cl[0] - r_c * s2, cl[1] - r_c * s2, 0.0),
            end=(cl[0], 0.0, 0.0),
        ),
        scad.make_segment_redge(start=(cl[0], 0.0, 0.0), end=(cr[0], 0.0, 0.0)),
        scad.make_three_point_arc_redge(
            start=(cr[0], 0.0, 0.0),
            middle=(cr[0] + r_c * s2, cr[1] - r_c * s2, 0.0),
            end=(xr, r_c, 0.0),
        ),
        scad.make_segment_redge(start=(xr, r_c, 0.0), end=(xr, d, 0.0)),
    ]


def build_u_rod() -> scad.Solid:
    """S1: 圆截面沿 U 路径扫掠（开口 +Y；端盖平面在 y=D）。"""
    assert_params()
    p = params()
    path = scad.make_wire_from_edges_rwire(edges=_u_path_edges(p))
    profile = scad.make_circle_rface(
        center=(-p["L"] / 2.0, p["D"], 0.0),
        radius=p["rod_d"] / 2.0,
        normal=(0.0, -1.0, 0.0),
    )
    rod = scad.sweep_rsolid(profile=profile, path=path)
    apply = scad.apply_tag
    apply(shape=rod, tag="role.u_rod")
    return rod


def _floor_selector(x_center: float, p: dict):
    """安装面(槽底)几何谓词：平面 +Y @ y=d_motor/2, x=x_center。"""
    y = p["d_motor"] / 2.0
    return ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", ">=", 0.999),
        ql.prop("geom.center.y", ">=", y - 0.1),
        ql.prop("geom.center.y", "<=", y + 0.1),
        ql.prop("geom.center.x", ">=", x_center - 0.1),
        ql.prop("geom.center.x", "<=", x_center + 0.1),
    )).exactly(1)


def _back_selector(p: dict):
    """背面几何谓词：平面 −Y @ y=back_y，大面积（区分 boss 顶环小面）。"""
    y = back_y(p)
    return ql.faces().where(ql.and_(
        ql.prop("geom.type", "==", "PLANE"),
        ql.prop("geom.normal.y", "<=", -0.999),
        ql.prop("geom.center.y", ">=", y - 0.1),
        ql.prop("geom.center.y", "<=", y + 0.1),
        ql.prop("geom.area", ">=", 100.0),
    )).exactly(1)


def _big_box(p: dict, y_top: float, y_bot: float) -> scad.Solid:
    """大包围盒。纪律（s10 探针教训）：cut 盒在非剖分侧必须越界出杆料——
    盒顶停在臂盖区内部会触发内核布尔垃圾结果。"""
    r = p["rod_d"] / 2.0
    ovs = 10.0
    return scad.make_box_rsolid(
        width=p["L"] + 4.0 * r + 2.0 * ovs, height=y_top - y_bot,
        depth=2.0 * (r + ovs),
        bottom_face_center=(0.0, (y_top + y_bot) / 2.0, -(r + ovs)))


def _eroded_sweep(p: dict) -> scad.Solid:
    """轮廓内偏移体：圆截面 半径 r-wall_t 沿同一 U 路径扫掠。
    （圆截面扫掠的内偏移=缩径扫掠，直段/圆弧段均精确——"贴合背板轮廓"的实现）"""
    q = dict(p)
    q["rod_d"] = p["rod_d"] - 2.0 * p["wall_t"]
    path = scad.make_wire_from_edges_rwire(edges=_u_path_edges(q))
    profile = scad.make_circle_rface(
        center=(-q["L"] / 2.0, q["D"], 0.0), radius=q["rod_d"] / 2.0,
        normal=(0.0, -1.0, 0.0))
    return scad.sweep_rsolid(profile=profile, path=path)


def _split_upper_base(p: dict, blank: bool) -> scad.Solid:
    """剖分上件基体。blank=True: 空白坯切 @ back_y-boss_h（75% 下移 boss 高，
    用户指定）；blank=False: 纯剖分 @ back_y（S2 阶段）。"""
    by = back_y(p)
    plane = by - p["boss_h"] if blank else by
    return scad.cut_rsolid(build_u_rod(), _big_box(p, plane, plane - 60.0))


def _boss_columns(p: dict) -> list:
    """boss 悬柱（union 语义：底=by-boss_h 精确，顶越界 2 入实体保熔合）。"""
    by = back_y(p)
    return [
        scad.make_cylinder_rsolid(
            radius=p["boss_d"] / 2.0, height=p["boss_h"] + 2.0,
            bottom_face_center=(sx * p["boss_x"], by - p["boss_h"], 0.0),
            axis=(0.0, 1.0, 0.0))
        for sx in (-1, 1)
    ]


def _boss_hole_tools(p: dict) -> list:
    """boss 中心盲孔（自柱底向上）。"""
    by = back_y(p)
    return [
        scad.make_cylinder_rsolid(
            radius=p["boss_hole_d"] / 2.0, height=p["boss_hole_depth"],
            bottom_face_center=(sx * p["boss_x"], by - p["boss_h"], 0.0),
            axis=(0.0, 1.0, 0.0))
        for sx in (-1, 1)
    ]


def _rounded_rect_prism(x_lo: float, x_hi: float, y_lo: float, y_hi: float,
                        z_lo: float, z_hi: float, rr: float) -> scad.Solid:
    """y-z 平面圆角矩形沿 +x 拉伸（共享工具：shell 走线口 / 电机槽走线窗）。

    注: wire 画在 x_lo 处、extrude distance=x_hi-x_lo——**不要**再平移（S12b 事故：
    extrude 后再 translate(+x_lo) 双重平移使工具落空且 cut 静默跳过）。
    """
    c45 = math.cos(math.pi / 4)

    def arc(x_lo_, cy, cz, sy, sz):
        return scad.make_three_point_arc_redge(
            start=(x_lo_, cy + sy * rr, cz),
            middle=(x_lo_, cy + sy * rr * c45, cz + sz * rr * c45),
            end=(x_lo_, cy, cz + sz * rr))

    y0r, y1r, z0r, z1r = y_lo + rr, y_hi - rr, z_lo + rr, z_hi - rr
    wire = scad.make_wire_from_edges_rwire(edges=[
        scad.make_segment_redge(start=(x_lo, y_lo, z0r), end=(x_lo, y_lo, z1r)),
        arc(x_lo, y0r, z1r, -1, 1),
        scad.make_segment_redge(start=(x_lo, y0r, z_hi), end=(x_lo, y1r, z_hi)),
        arc(x_lo, y1r, z1r, 1, 1),
        scad.make_segment_redge(start=(x_lo, y_hi, z1r), end=(x_lo, y_hi, z0r)),
        arc(x_lo, y1r, z0r, 1, -1),
        scad.make_segment_redge(start=(x_lo, y1r, z_lo), end=(x_lo, y0r, z_lo)),
        arc(x_lo, y0r, z0r, -1, -1),
    ])
    face = scad.make_face_from_wire_rface(wire=wire)
    return scad.extrude_rsolid(profile=face, direction=(1.0, 0.0, 0.0), distance=x_hi - x_lo)


def _cable_window_tools(p: dict) -> list:
    """S13 电机槽走线窗：每槽 4 窗（相位差 90°，对角布置避让内向盲区）。

    两条过轴 rounded-rect 棱柱（旋转 ±phase）各切对向 2 窗；窗底边
    y = 安装面 + cable_w_off（用户规定 ∈[3,5]）。
    """
    floor_y = p["d_motor"] / 2.0
    r = p["rod_d"] / 2.0
    span = r + 3.0
    y0 = floor_y + p["cable_w_off"]
    y1 = y0 + p["cable_w_h"]
    hw = p["cable_w_w"] / 2.0
    base = _rounded_rect_prism(-span, span, y0, y1, -hw, hw, p["cable_w_rr"])
    tools = []
    for rot in (p["cable_w_phase"], p["cable_w_phase"] + 90.0):
        t = scad.rotate_shape(shape=base, axis=(0.0, 1.0, 0.0), angle=rot)
        for xc in (-p["L"] / 2.0, p["L"] / 2.0):
            tools.append(scad.translate_shape(shape=t, vector=(xc, 0.0, 0.0)))
    return tools


def _gusset_tools(p: dict) -> list:
    """4 方向三角筋：垂直边贴柱（全高 boss_h），水平边沿剖分面 rib_len。"""
    by = back_y(p)
    br, rt, rl, bh = p["boss_d"] / 2.0, p["rib_t"], p["rib_len"], p["boss_h"]
    gussets = []
    for sx in (-1, 1):
        bx = sx * p["boss_x"]
        for dx in (-1, 1):  # ±x：三角形在 (x,y) 面，沿 +z 拉伸
            tri = scad.make_face_from_wire_rface(scad.make_wire_from_edges_rwire(edges=[
                scad.make_segment_redge(start=(bx + dx * br, by, -rt / 2),
                                        end=(bx + dx * (br + rl), by, -rt / 2)),
                scad.make_segment_redge(start=(bx + dx * (br + rl), by, -rt / 2),
                                        end=(bx + dx * br, by - bh, -rt / 2)),
                scad.make_segment_redge(start=(bx + dx * br, by - bh, -rt / 2),
                                        end=(bx + dx * br, by, -rt / 2)),
            ]))
            gussets.append(scad.extrude_rsolid(
                profile=tri, direction=(0.0, 0.0, 1.0), distance=rt))
        for dz in (-1, 1):  # ±z：三角形在 (z,y) 面，沿 +x 拉伸
            tri = scad.make_face_from_wire_rface(scad.make_wire_from_edges_rwire(edges=[
                scad.make_segment_redge(start=(bx - rt / 2, by, dz * br),
                                        end=(bx - rt / 2, by, dz * (br + rl))),
                scad.make_segment_redge(start=(bx - rt / 2, by, dz * (br + rl)),
                                        end=(bx - rt / 2, by - bh, dz * br)),
                scad.make_segment_redge(start=(bx - rt / 2, by - bh, dz * br),
                                        end=(bx - rt / 2, by, dz * br)),
            ]))
            gussets.append(scad.extrude_rsolid(
                profile=tri, direction=(1.0, 0.0, 0.0), distance=rt))
    return gussets


def _gusset_hyp_edges(body, p: dict) -> list:
    """筋斜边（长 sqrt(rib_len²+boss_h²)，每筋两侧共 16 条）。"""
    by = back_y(p)
    br = p["boss_d"] / 2.0
    hyp = (p["rib_len"] ** 2 + p["boss_h"] ** 2) ** 0.5
    edges = []
    for e in body.get_edges():
        if abs(e.get_length() - hyp) > 0.15:
            continue
        c = e.get_center()
        if any(abs(c.x - sx * p["boss_x"]) <= br + p["rib_len"] + 0.4 for sx in (-1, 1)) \
                and by - p["boss_h"] - 0.3 <= c.y <= by + 0.3:
            edges.append(e)
    return edges


def _fillet_included_edges(body, p: dict) -> list:
    """全局倒角边选择（s10 dbg26/27 分组取证 + s11 阈值精调）：

    只含 y > (back_y+d_motor/2)/2 的边（安装槽 rim/臂顶/高位外缝——可靠集；
    恰包含 d_motor/2 处的安装面 rim）。排除：剖分面(7.5)与地板顶(2.5)弦 rim
    （内核静默负体积！）、boss/筋邻域、低 y 杂边。工程上剖分接口锐边是正确
    配合设计。单次遍历（对象恒等不可靠）。"""
    y_min = (back_y(p) + p["d_motor"] / 2.0) / 2.0
    min_len = 2.0 * p["fillet_r"] + 0.3
    return [e for e in body.get_edges()
            if e.get_center().y > y_min and e.get_length() >= min_len]


def _build_chain_ops(stage: str):
    """纯操作链（不自建 GraphSession；在环境 session 中执行——
    独立验证走 build_stage 包装，@part 冷构建自带 session）。"""
    assert stage in ("s1", "s2", "s3", "s4")
    p = params()
    rp = (p["rod_d"] - p["thickness"]) / 2.0
    floor_y = p["d_motor"] / 2.0
    by = back_y(p)

    body = build_u_rod()
    if stage == "s1":
        return body
    # S2/S10: 剖分上件 @ back_y（75%），去下半（越界纪律）
    body = scad.cut_rsolid(body, _big_box(p, by, by - 60.0))
    if stage == "s2":
        scad.apply_tag(shape=body, tag="role.split_upper")
        return scad.apply_tag_rselection(scope=body, targets=_back_selector(p), tag=TAG_BACK)
    # S3: 电机安装槽 + 命名
    pocket_depth = p["D"] - floor_y
    pocket_tools = [
        scad.make_cylinder_rsolid(
            radius=rp, height=pocket_depth + 5.0,
            bottom_face_center=(x, floor_y, 0.0), axis=(0.0, 1.0, 0.0))
        for x in (-p["L"] / 2.0, p["L"] / 2.0)
    ]
    body = scad.cut_rsolid(body, pocket_tools)
    body = scad.apply_tag_rselection(
        scope=body, targets=_floor_selector(-p["L"] / 2.0, p), tag=TAG_MOUNT_LEFT)
    body = scad.apply_tag_rselection(
        scope=body, targets=_floor_selector(p["L"] / 2.0, p), tag=TAG_MOUNT_RIGHT)
    if stage == "s3":
        return body
    # S4/S10: 最终上件——剖分@back_y → boss 悬柱（integral 语义=用户两刀工艺的
    # 等价几何：上件 75% 以下仅存 boss+筋，壁让位给 shell 至 7.5，避免带区干涉）
    body = scad.cut_rsolid(body, _big_box(p, by, by - 60.0))
    body = scad.union_rsolid(body, *_boss_columns(p))
    pocket_depth = p["D"] - floor_y
    pocket_tools = [
        scad.make_cylinder_rsolid(
            radius=rp, height=pocket_depth + 5.0,
            bottom_face_center=(x, floor_y, 0.0), axis=(0.0, 1.0, 0.0))
        for x in (-p["L"] / 2.0, p["L"] / 2.0)
    ]
    body = scad.cut_rsolid(body, pocket_tools)
    body = scad.cut_rsolid(body, _boss_hole_tools(p))
    body = scad.union_rsolid(body, *_gusset_tools(p))
    hyp_edges = _gusset_hyp_edges(body, p)
    assert len(hyp_edges) == 16, f"筋斜边识别异常 n={len(hyp_edges)} (want 16)"
    body = scad.chamfer_rsolid(solid=body, edges=hyp_edges, distance=p["gusset_chamfer"])
    body = scad.fillet_rsolid(
        solid=body, edges=_fillet_included_edges(body, p),
        radius=p["fillet_r"], generated_faces_tag="fillet.global_patch")
    # S13 电机槽走线窗——最后一步（用户定向：切口在最后做；rounded-rect 源型
    # 自带角圆角，在成品拓扑上直接切出，无需再 fillet）
    body = scad.cut_rsolid(body, _cable_window_tools(p))
    # 拓扑稳定后统一重打确定性命名
    body = scad.apply_tag_rselection(
        scope=body, targets=_floor_selector(-p["L"] / 2.0, p), tag=TAG_MOUNT_LEFT)
    body = scad.apply_tag_rselection(
        scope=body, targets=_floor_selector(p["L"] / 2.0, p), tag=TAG_MOUNT_RIGHT)
    body = scad.apply_tag_rselection(scope=body, targets=_back_selector(p), tag=TAG_BACK)
    return body


def build_stage(stage: str = "s3") -> scad.Solid:
    """阶段化构建（独立进程验证入口：自建 GraphSession 并 capture）。"""
    assert_params()
    with scad.GraphSession(graph_id=f"u_link_{stage}") as session:
        result = _build_chain_ops(stage)
        session.capture_result(value=result)
        return result


@scad.part(id="u-link-motor-mount", revision="1.0.0",
           project_root=Path(__file__).resolve().parents[2])
def build_u_link_part() -> scad.Part:
    """交付产品：U 形电机连杆（含命名安装面+背腔+boss，倒角终态）。"""
    p = params()
    body = _build_chain_ops("s4")
    part = scad.make_part_rpart(
        part_id="u-link-motor-mount",
        body=body,
        name="Parametric U link with named motor mount faces",
    )
    connector = scad.make_placement_connector_rconnector(
        connector_id="back_datum",
        placement=scad.make_placement_rplacement(
            origin=(0.0, back_y(p), 0.0), x_axis=(1.0, 0.0, 0.0), y_axis=(0.0, 0.0, 1.0)),
        name="Back face datum (z out -Y)")
    return scad.add_connector_rpart(part=part, connector=connector)


def build_flat_bottom() -> scad.Solid:
    """S2: 剖分上件（=build_stage("s2")，保留旧入口名兼容验证器）。"""
    return build_stage("s2")


if __name__ == "__main__":
    result = build_u_link_part()
    body = result.value.body
    print(f"part volume={body.get_volume():.3f} faces={len(body.get_faces())}")
