#!/usr/bin/env python3
"""Rebuild the u_link_motor_mount replay demo with demo_kit.

Run from the repository root:

    python3 examples/u_link_motor_mount/demo/build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # demo/
ROOT = HERE.parent                              # u_link_motor_mount/
KIT = ROOT.parent / "demo_kit"
sys.path.insert(0, str(KIT))

from build_demo import build_case  # noqa: E402

build_case({
    "root": ROOT,
    "stl": {
        "path": ROOT / "out" / "u_link_assembly.stl",
        "name": "u_link_assembly.stl",
        "note": "44,976 三角面 · OCC BREP 曲面细分",
        "gl_cap": "u_link_assembly · body + shell · 会话自动导出（STEP AP242 / STL / FCStd）",
    },
    "imgs": [
        {"key": "assembly", "path": ROOT / "out" / "render_assembly.png", "cap": "最终装配 · body + shell"},
        {"key": "iso", "path": ROOT / "out" / "render_iso.png", "cap": "等轴测视图"},
        {"key": "front", "path": ROOT / "out" / "render_front.png", "cap": "正视图"},
        {"key": "shell", "path": ROOT / "out" / "render_shell.png", "cap": "外壳 shell（剖视）"},
    ],
    "params": [
        ["L", "80 mm", "臂轴跨距 / 底宽（两电机轴线间距）"],
        ["D", "20 mm", "臂端面高度（用户定向 40 → 20 取半）"],
        ["rod_d", "30 mm", "U 形圆杆直径"],
        ["thickness", "6 mm", "电机槽壁余量（槽壁厚 = 3）"],
        ["d_motor", "19 mm", "电机深度（S11 用户定向 30 → 19 加深槽）"],
        ["r_corner", "17 mm", "拐角中心线圆弧半径，须 ∈ (rod_d/2, D)"],
        ["fillet_r", "1.2 mm", "全局倒角半径（< thickness/4）"],
        ["back_cut_frac", "0.75", "背切平面位置（0.5=中心线 → 0.75 用户定向上移）"],
        ["wall_t", "2.0 mm", "shell 壁厚 = 腔内偏移量"],
        ["boss_d / boss_h", "5 / 5 mm", "boss 柱外径 / 高度"],
        ["boss_x", "12 mm", "boss 轴位置（剖分面中央区 ±）"],
        ["boss_hole_d", "2.7 mm", "boss 自攻孔径 = shell 底孔内径（用户指定一致）"],
        ["cable_w_off", "3 mm", "走线窗底边高于安装面（用户规定 ∈ [3,5]）"],
        ["cable_w_h × w", "5 × 10 mm", "走线窗尺寸（S14 周向 5 → 10 加宽 2 倍）"],
        ["safe_fillet_r", "0.6 mm", "shell 平底外缘防割手圆角"],
        ["notch_w × h", "9 × 5 mm", "两端走线方口（S11 加大）"],
        ["csink", "Ø5.4 × 1.35", "shell 底板沉头孔（90° 锥口）"],
    ],
    "tags": [
        "feature.motor_mount_floor_left",
        "feature.motor_mount_floor_right",
        "feature.back_face",
    ],
    "tags_note": "命名面在倒角、剖分、重打标后仍可被查询语言索引 —— 这是本轮会话的核心能力演示之一。",
    "artifacts": {
        "files": [
            ["u_link_assembly.step", "1.30 MB", "STEP AP242DIS · 3 定义 · 2 实例"],
            ["u_link_assembly.stl", "2.14 MB", "44,976 三角面 · OCC BREP 曲面细分"],
            ["u_link_assembly.FCStd", "1.91 MB", "FreeCAD 可编辑特征树 · 167 对象"],
            ["u_link_assembly.scadpkg", "18.9 MB", "SimpleCAD 原生装配包"],
            ["render_*.png", "×4", "装配 / 等轴 / 正视 / 外壳渲染"],
        ],
        "scripts": [
            "s1–s5_verify", "s6_param_sweep", "s8_preprobe/diag×3", "s9_diag/verify",
            "s10_verify", "s11_probe", "s12_verify", "s13_probe", "s14 回归",
        ],
        "notes": ["参数扫描 13 变体 + 17 边界 全过"],
    },
    "about": [
        "<b>这是什么。</b>一个真实工程会话的忠实回放：2026-08-26 15:56 → 00:17，人类工程师用自然语言描述需求、逐步定向修改，Agent（SimpleCAD SDK）在 <b>{tools}</b> 次工具调用中完成「需求确认 → 总体规划 → 分阶段建模 → 每阶段独立验证 → 导出装配」的完整闭环。",
        "<b>左侧对话</b>逐条回放全部 {N} 条消息（用户输入 / Agent 思考与回复 / 工具调用输入与输出 / 补丁 / 角色切换），内容与 session_transcript.md 一一对应，未做删改。",
        "<b>右侧 3D</b> 是会话最终导出的 {stlName}（{stlTris} 三角面），由 three.js 实时渲染，可拖拽旋转 / 缩放 / 平移。",
    ],
    "highlights": "① 每阶段先写验证契约再建模（{allPass} 次 ALL PASS）；② 安装面/背面具备确定性命名、可被查询语言索引；③ 用户 7 次「不对/改一下」的真实返工（S8 卡扣→S9 boss→S10 剖分→S11 两刀工艺）；④ 参数守卫链与变体扫描保证参数化正确性。",
    "subtitle": "· 从一句话需求到可制造装配",
    "extra_stat": ["2", "交付零件 body+shell"],
})
