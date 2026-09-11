# WHUCAD → SimpleCADAPI FTC 翻译工具

把 WHUCAD 数据集的向量化 CAD 序列（h5 `vec` 命令矩阵，DeepCAD/CATIA 风格的
256 级量化表示）翻译成 SimpleCADAPI 的 FTC（Feature Tree Convention）Python
源码。翻译产物用于合成训练数据。架构与 `tools/research/histjson/`（HistCAD
翻译）完全同构：翻译器只做翻译，验收与审计在外部工具。

```
tools/research/whucad/
├── whucad_vec.py        # 解码器：vec → 特征对象（自包含 port，仅 numpy/h5py）
├── whucad_select.py     # Topo/Select 拓扑引用 → ql 几何谓词选择器
├── whucad_to_ftc.py     # 翻译器：特征对象 → FTC 源码（只做翻译）
├── whucad_profile.py    # 数据画像：特征/曲线/extent/选择形态分布 + 覆盖率
├── whucad_validate.py   # 验收：执行产物 + 与官方 BRep 真值对体积（抽样）
├── check_port.py        # 开发工具：解码器与原版 cadlib 的差分校验
└── out/                 # 报告与真值缓存（gitignored）
test/test_whucad_translation_output.py   # 输出契约测试（内嵌向量，无需数据集）
```

**职责墙（设计铁律，同 histjson）**：翻译器只做翻译——数据里有什么就译什么，
不求解、不挑层级、不回落、产物里没有任何检查代码。译不出的形式跳过并在头部
注记（`# step N: unsupported ...`），一切"译得对不对"的问题由 validate /
profile 回答。调用发射与 histjson 采纳同一约定：simplecadapi 调用一律用
关键字参数形式（`scad.add_line_rsketch(sketch=s, entity_id=..., start=...,
end=...)`），布尔行除外（`cut/union/intersect` 保持位置形式，同上游）。

---

## 1. 与 HistCAD 管线的差异

| | HistCAD（histjson） | WHUCAD（本目录） |
| --- | --- | --- |
| 输入 | 带约束通道的序列 JSON | h5 `vec` 整数命令矩阵（无约束） |
| 草图 | line/circle/arc/ellipse/nurbs + 19 类约束 | line/circle/arc/spline（无约束） |
| 特征 | 只有拉伸 | Pad/旋转/旋转切/抽壳/倒角/圆角/孔/镜像/拔模 |
| 拓扑引用 | 无 | Topo/Select："第 n 个特征的第 m 个面" |
| 坐标 | 毫米浮点 | 256 级量化 + 单位立方归一化（**绝对尺度不在数据里**） |

量化带来的两个直接推论：

- FTC 产物是**归一化尺度**的模型（包围盒 ~1.5），不是原始毫米尺度。
- 体积对账必须做尺度校正（bbox 对角线比值）后比较，容差比 histcad 的 1e-3
  放宽（数据量化噪声 ~0.4%/维度）。

## 2. 如何使用

```bash
# 单个 case：h5 → FTC 源码
.venv/bin/python tools/research/whucad/whucad_to_ftc.py <model.h5> [--out PATH]

# 数据画像：特征/曲线/选择形态分布 + 翻译覆盖率（抽样一个子目录即可）
.venv/bin/python tools/research/whucad/whucad_profile.py <vec_dir> [--limit N]

# 抽样验收：翻译 → 进程内执行 → 下载对应 BRep 真值 → 尺度校正后对体积
.venv/bin/python tools/research/whucad/whucad_validate.py \
    --vec-dir <WHUCAD>/data/vec/0000 --count 40 --stride 23 \
    [--uids a,b,c] [--report out/whucad_validate.json]
```

`whucad_vec.py` 是原版 `fazhihe/WHUCAD` cadlib 解码路径的忠实 port（不依赖
torch/matplotlib）。`check_port.py` 在全部样例上与原版 cadlib 差分对比
（曲线、平面、参数、Select 树逐值相等）：

```bash
.venv/bin/python tools/research/whucad/check_port.py   # 1419/1419 一致（0000 目录实测）
```

## 3. 翻译覆盖（data/vec/0000 全量 1419 模型实测，profile 报告）

| 特征 | 映射 | 状态 |
| --- | --- | --- |
| Ext / Pocket | 面提升 + `extrude_rsolid` + 布尔（add/cut/intersect，双侧 union 技巧，负向 extent 翻越草图面） | ✅ |
| Rev / Groove | `revolve_rsolid`，轴 = 草图第 no 条线（数据集 Wire/Sketch 引用，1-based） | ✅（双侧旋转除外） |
| Hole | 圆草图 + 拉伸 cut | ✅（`OffsetLimit` 底） |
| Chamfer / Fillet（棱边引用） | 两面交边解析（圆 = 面×柱，直线 = 面×面共享端点）→ `ql.edges()` 谓词 | ✅ |
| Chamfer / Fillet（整面引用） | 帽面圆边 / 侧壁全边界边 → 逐边谓词 | ✅ |
| Shell（外部厚度 = 0） | `shell_rsolid` + `ql.faces()` 谓词 | ✅ |
| Mirror / Draft | 无 FTC 映射 | 注记跳过 |
| Shell（外部厚度 > 0） | FTC 无外部厚度参数 | 注记跳过 |
| 旋转体（Shaft）的面/侧壁引用、弧线侧壁、UpTo 系拉伸终点 | 待第二期 | 注记跳过 |

特征级覆盖率 **79.1%**（4095 特征中 857 个注记跳过）；模型级 **49.0%** 全量
翻译、其余部分翻译（跳过的特征主要是 Mirror / 外部厚度抽壳 / 旋转体引用）。

## 4. 抽样验收结果（40 例，stride 23，对官方 BRep 真值）

- **全量翻译的 16 例：构建成功的 10 例体积全部对上（10 pass / 0 mismatch）**，
  其中含倒角/圆角的盒体达到机器精度（rel 8.4e-14 / 1.1e-8），曲面模型在量化
  噪声水平（1e-3 ~ 1.4e-2）。
- 6 例 build_error 全部是 OCC 内核限制（与 histcad 已知 C 类同源）：并集切向
  接触违反单流形契约、圆角半径 ≈ 轮廓圆角弧半径一半时相切退化
  （r=0.035 能过、r=0.039 失败的实测阈值）、抽壳边界厚度。
- 22 例带跳过注记的模型体积必然偏差（缺的就是被跳过特征的贡献）——偏差即
  跳过清单，逐 case 在报告 `skipped_features` 字段可查。

## 5. 移植与校准笔记（为什么这样译）

- **2D → 实坐标**：`p_real = (p − 128) × sketch_size/95`，95 = 256/2×0.75−1，
  与数据集自己的 CATIA 重建（`profile.denormalize(sketch_size)`）一致；
  3D = 草图面原点 + x_axis·px + y_axis·py（CoordSystem 原点即 sketch_pos）。
- **帽面编号**（对官方 BRep 实测校准）：`no=0` 侧壁（携 Wire 引用）、`no=1`
  近帽（草图面侧）、`no=2` 远帽；帽/壁棱边倒角的两条腿按"帽面锚定 l1"约定，
  00000004 实测机器精度验证。
- **旋转轴**：`Wire/Sketch#body_no` 的第 no 条曲线（1-based 全局曲线序号），
  CATIA FirstAngle/SecondAngle 换算后单侧扫掠直接映射 FTC `angle`。
- **Validate 的 bbox**：必须用 `BRepBndLib.AddOptimal_s(shape, box, False,
  False)` + `SetGap(0)`——默认包围盒对曲面外扩 ~7%，会把尺度校正整个带偏。

## 6. 已知边界

- FTC `@scad.part` 装饰器可能在独立命名空间重建函数，`module.BODIES` 不一定
  回写——validate 已按 Part 返回值兜底（histcad 同款）。
- 多体（不相交）模型经 `_merge_bodies` 合并，体积对账按单实体真值口径。
- WHUCAD-2026 新版若改格式，只需替换 `whucad_vec.py` 一个模块。
