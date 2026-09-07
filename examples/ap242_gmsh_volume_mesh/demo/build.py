#!/usr/bin/env python3
"""Rebuild the ap242_gmsh_volume_mesh (L-bracket) replay demo with demo_kit.

Run from the repository root:

    python3 examples/ap242_gmsh_volume_mesh/demo/build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # demo/
ROOT = HERE.parent                              # 12_ap242_gmsh_volume_mesh/
KIT = ROOT.parent / "demo_kit"
sys.path.insert(0, str(KIT))

from build_demo import build_case  # noqa: E402

build_case({
    "root": ROOT,
    "stl": {
        "path": ROOT / "out" / "ap242_gmsh_bracket.stl",
        "name": "ap242_gmsh_bracket.stl",
        "note": "948 三角面 · 单实体 L 形支架",
        "gl_cap": "ap242_gmsh_bracket · FEM 接口标签保留 · 会话自动导出（scadpkg / STEP / FCStd / STL）",
    },
    "imgs": [
        {"key": "iso", "path": ROOT / "out" / "render_iso.png", "cap": "等轴测视图 · L 形主体 + 双筋"},
        {"key": "top", "path": ROOT / "out" / "render_top.png", "cap": "俯视图 · 筋板对称布局"},
        {"key": "detail", "path": ROOT / "out" / "render_detail.png", "cap": "筋板 + 安装孔区特写"},
    ],
    "params": [
        ["bracket_width / height / depth", "40 / 36 / 28 mm", "外形包络（宽 / 高 / 深）"],
        ["plate_thickness", "4 mm", "竖壁与横板壁厚"],
        ["mount_hole_radius", "2.5 mm", "安装孔半径（⌀5，tol 0.1）"],
        ["mount_hole_spacing", "22 mm", "安装孔孔距（跨筋对称）"],
        ["mount_hole_height_ratio", "0.62", "安装孔高度 = 0.62 × bracket_height"],
        ["load_hole_radius / load_hole_x", "3.0 mm / 12 mm", "横板承载孔（⌀6）半径与 x 位置"],
        ["rib_thickness / height / depth", "3 / 18 / 18 mm", "双三角筋板（geometry tier 轮廓）"],
        ["rib_offset_y", "11 mm", "筋板对称偏置（legacy 字面量，已核对）"],
        ["cut_overshoot", "1 mm", "孔刀超出量（切穿保证）"],
        ["revision", "2.0.0 → 2.1.0", "工作流正式化重建，几何逐位等价"],
    ],
    "tags": [
        "interface.fixed_support",
        "interface.load_surface",
        "interface.mount_hole_1",
        "interface.mount_hole_2",
        "interface.load_hole",
        "role.structural_l_bracket",
    ],
    "tags_note": "FEM 接口标签集合与 legacy 版逐位一致（面积 rel ≤ 5.3e-7）——下游 Gmsh 网格 / CalculiX 边界条件按标签选面，重建不破坏仿真链。",
    "artifacts": {
        "files": [
            ["ap242_gmsh_bracket.scadpkg", "1.07 MB", "SimpleCAD 原生产品包 @2.1.0"],
            ["ap242_gmsh_bracket.step", "66 KB", "STEP AP242 · 1382 实体"],
            ["ap242_gmsh_bracket.FCStd", "53 KB", "FreeCAD 可编辑特征树 · 26 对象 / 15 特征"],
            ["ap242_gmsh_bracket.obj / .stl", "32 / 47 KB", "网格导出（948 三角面）"],
            ["render_*.png", "×4", "等轴 / 正视 / 俯视 / 筋板特写"],
        ],
        "scripts": [
            "s1_verify", "s2_verify", "s3_equivalence", "s3_render", "s4_fcstd_check",
            "s1/s2/s3_hypothesis", "s0_legacy_probe",
        ],
        "notes": [
            "新旧几何等价：体积 rel = 0.00e+00，包围盒逐位相同",
            "四个下游导出脚本（step/obj/stl/fcstd）对 2.1.0 包零改动重跑通过",
        ],
    },
    "about": [
        "<b>这是什么。</b>把一个已有的 legacy 建模脚本按 single-part-modeling 工作流完整正式化的会话回放：需求确认 → 总体规划 → 分阶段验证先行重建 → 新旧几何等价对账 → FCStd 可编辑性核验。Agent 在 {tools} 次工具调用中完成。",
        "<b>左侧对话</b>逐条回放全部 {N} 条消息，与 session_transcript.md 一一对应，未做删改。",
        "<b>等价是怎么证的</b>：体积相对偏差 0.00e+00、包围盒逐位相同、17 面/51 边拓扑、5 个 interface.* 标签面积 rel ≤ 5.3e-7、双包新进程重开——重建没有偷偷改变任何一个 FEM 边界面。",
        "<b>右侧 3D</b> 是会话最终导出的 {stlName}（{stlTris} 三角面），three.js 实时渲染，可拖拽旋转 / 缩放 / 平移。",
    ],
    "highlights": "① 验证先行（{allPass} 次 ALL PASS）；② FEM 接口标签跨版本保真，仿真链零破坏；③ FCStd 特征树 15 个可编辑特征经 CLI 重开+体积对账验证；④ 4 次检查器自身缺陷被如实记录并修复（含 1 次评审契约修正链）。",
    "subtitle": "· legacy 脚本的工作流化 + 几何等价对账",
    "extra_stat": ["0.00e+00", "新旧体积相对偏差"],
})
