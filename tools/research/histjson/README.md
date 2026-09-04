# HistCAD → SimpleCADAPI FTC 翻译工具

把 `examples/histcad/` 里的 HistCAD 序列 JSON（Fusion360 / DeepCAD 建模史）翻译成
SimpleCADAPI 的 FTC（Feature Tree Convention）Python 源码。翻译产物用于合成训练数据。

```
tools/research/histjson/
├── histcad_profile.py     数据集画像：操作/实体/约束形态分布
├── histcad_to_ftc.py      翻译器：JSON → FTC 源码（只做翻译）
├── histcad_validate.py    验收：执行翻译产物 + 与打包的 STEP 真值对体积
├── histcad_conflicts.py   审计：逐约束残差 + 求解结局分类（哪些不能翻、为什么）
└── out/                   报告输出（gitignored）
```

**职责墙（设计铁律）**：翻译器只做翻译——数据里有什么就译什么，不求解、不挑层级、
不回落、产物里没有任何检查代码。一切"译得对不对、解不解得出来"的问题都由外部的
validate / conflicts 工具回答。译出的源码 = 模型本身，仅此而已。

---

## 1. 如何翻译

### 单个 case

```bash
.venv/bin/python tools/research/histjson/histcad_to_ftc.py <seq.json> [--out PATH] [--constraints on|off]
```

- `--constraints on`（默认）：数据集里的约束全部照译（能映射的形式）。
- `--constraints off`：只转录几何，丢弃约束通道（体积对账、几何通道验收用）。
- 输出是一个可直接运行的 `.ftc.py`。

### 批量（翻译 + 构建 + STEP 对账一步完成）

```bash
.venv/bin/python tools/research/histjson/histcad_validate.py \
    --tar   examples/histcad/JSON/histcad_sequences_fusion360_0100.tar.gz \
    --step-tar examples/histcad/STEP/histcad_step_fusion360_0100.tar.gz \
    --count 100 --stride 83 --workers 6 --constraints off \
    --report out/histcad_validate.json
```

对每个采样 case：翻译 → 进程内执行 → 读打包 STEP → 比较总体积（容差 1e-3），
打印逐 case 结果与汇总，明细写 `out/histcad_validate.json`。`--uids 0100/01003954,...`
可以指定单点复查。

### 现成演示

`examples/histcad_demo/` 有三个完整示例（Fusion 弧链多特征、degree-5 NURBS、
DeepCAD 480 行多特征），带全量约束构建，体积与 STEP 对账 3.3e-16 / 8.2e-5 / 2.8e-13。

---

## 2. 翻译结果是什么

一个 case 一个 `.ftc.py`：一个 `@scad.part` 装饰的 `build()`，每个 HistCAD step 一个
FTC 特征块（草图 → 约束 → 提升 → 挤出 → 布尔），显式数据流改写 body：

```python
"""FTC source generated from HistCAD 0100/01003954."""

import simplecadapi as scad

BODIES = None  # all solid bodies before single-solid merge


def _merge_bodies(bodies):
    ...


@scad.part(id='histcad-0100-01003954', revision='1.0.0')
def build() -> scad.Part:
    # ---- feature: newbody-1 (build, profile=sketch) ----
    s = scad.make_sketch_rsketch(name='f0', plane={'origin': (0.0, 0.0, 0.0), ...})
    s = scad.add_point_rsketch(s, 'f0_p1', -5.0, -1.5)
    s = scad.add_line_rsketch(s, 'line_1', 'f0_p1', 'f0_p2')
    ...
    s = scad.constrain_horizontal_rsketch(s, 'line_1', constraint_id='h6_Horizontal')
    s = scad.constrain_distance_x_rsketch(s, 'line_3.start', 'line_3.end', -8.89,
                                          constraint_id='h5_Distance')
    f0_face0 = scad.make_face_from_sketch_rface(s, profile=0)
    f0_tool0 = scad.extrude_rsolid(profile=f0_face0, direction=(0.0, 0.0, -1.0), distance=1.905)

    # ---- feature: cut-2 (subtract, profile=geometry) ----
    ...
    bodies = [scad.cut_rsolid(_b, [f1_tool0]) for _b in bodies]
```

要点：

- **块头** `# ---- feature: <slug> (<role>, profile=<tier>) ----` 可解析；`role` =
  build/add/subtract/intersect 对应 NewBody/Join/Cut/Intersect。
- **tier 注记是静态事实**：该特征有约束行 = `profile=sketch`，只有转录几何 =
  `profile=geometry`（数据集本就没有可映射约束，或全部是池化恒真的重合约束）。
- **每条约束带原生编号** `constraint_id='h5_Distance'`（h<序号>_<数据集约束类型>，
  变长链加 `-2/-3` 后缀）——审计工具靠它点名到数据集里的原始条目。
- 头部注释会标注 `feature N: unmapped constraint kinds [...]`（该特征里没有映射形式
  的约束类型），这是唯一的翻译完整性提示，不是检查代码。
- 多体 case（数据集里不相交的多个 NewBody/Join）用 `bodies` 列表 +
  `_merge_bodies` 表达——这是组合策略不是检查（多 lump part 模型立项后会简化掉）。

---

## 3. 多大程度上能够翻译

### 结构覆盖（histcad_profile.py 实测，全量数据集）

| 通道 | 覆盖 |
| --- | --- |
| 操作 | 数据集 245,197 步全部是 Extrude（NewBody/Join/Cut/Intersect）——**100% 支持** |
| 实体 | line / circle / arc / ellipse / nurbs 支持；elliptical_arc 不支持（该步跳过并注记） |
| 约束 | 19 种类型的主要形式全部有映射；少数形式无映射（见下节 A1） |

### 几何通道正确率（`--constraints off`，体积对 STEP，容差 1e-3）

| 数据集 | 样本 | 通过 | 失配 | 构建错误 |
| --- | --- | --- | --- | --- |
| DeepCAD | 300 | **85.0%**（中位误差 1.6e-16 = 机器精度，p95 5e-6） | 3.0% | 12.0% |
| Fusion360 | 150 | **76.7%**（中位 2.8e-16） | 6.7% | 16.7% |

### 约束通道可解率（histcad_conflicts.py 审计，各 100 case 标准样本）

| 数据集 | 特征总数 | 解出且复现坐标 | drifted | conflicting | 无约束通道 |
| --- | --- | --- | --- | --- | --- |
| Fusion360 | 240 | **186（90.3% / 有约束特征）** | 19 | 1 | 34 |
| DeepCAD | 140 | **119（93.0%）** | 9 | 0 | 12 |

"解出"的特征里，求解器对坐标的重排极小（中位 0，p90 ≈ 3e-5 mm）——约束系统与转录
坐标在求解意义下自洽。约束通道 + 几何通道可以同时成立：演示三例就是带全量约束
构建、体积机器精度对账的。

---

## 4. 为什么不能翻译 / 译了也解不出

按"谁的问题"分四类：

### A. 翻译器不支持（产物里有注记，几何不受影响）

1. **无映射的约束形式**：Distance 的 点-线 / 圆-圆 / 弧-弧 / 圆-线 组合（目前只映射
   点-点 H/V/MINIMUM 与 线-线）、Tangent 的 弧-圆、Equal 含椭圆。这些条目被丢弃，
   头部注记 `unmapped constraint kinds`。几何转录不受影响，丢的是这几条设计意图。
2. **elliptical_arc 实体**：整步跳过，头部注记 `unsupported`。
3. FCStd 侧小缺口：ellipse 的 Concentric 在 FreeCAD 翻译里记为未翻译
   （需要 InternalAlignment 约束，几何不受影响）。

### B. 数据集约束自身的问题（审计工具的残差分析定位）

1. **声明值与坐标矛盾（舍入级，1e-5~1e-3 mm）**：数据集坐标只存 4 位小数，尺寸值
   另有舍入；系统自由度耗尽（dof=0）时无处吸收，求解器判 inconsistent。
2. **声明值与坐标粗大矛盾**：残差 >1e-3，个别是真实数据集错误（实测案例：一个
   Angle 声明值与坐标差 64.6°）。dof>0 时求解器会"满足约束但把几何拉走"——
   drifted 类（实测位移中位 1.4~9 mm）。**这类照译不误：翻译器忠实翻译数据集，
   错在数据集**，用审计工具挑出来即可。
3. DeepCAD halfSpace0/1（两线互侧标志）：信息已在坐标里；仅个别条目与坐标侧翻位。

### C. 构建层（几何通道的 build_error，与约束无关）

约七成 = `union_rsolid` 单流形契约 vs 切向/棱接触的 Join（多 lump compound part
策略已备、待立项，落地后解锁这 10~15% 大头）；其余 = JSON 整数溢出的数据伪影、
少量 bspline/面提升内核边角。

### D. 已知数据集伪影

如 0001/00010008：最后一步 Cut 按规格执行会多切体积，而打包 STEP ≈ 没切。
以 STEP 为准对账即暴露。

> 注意：求解器点名的"失败约束"不等于根因（实测定位率 7/20）——它只是求解器做秩
> 分析时顺手摘掉的条目。定位根因要靠残差分析（conflicts 工具），不要只看点名。

---

## 5. 如何知道哪些不能翻译

### 逐约束审计（主力工具）

```bash
.venv/bin/python tools/research/histjson/histcad_conflicts.py \
    --tar examples/histcad/JSON/histcad_sequences_fusion360_0100.tar.gz \
    --count 100 --stride 83 [--uids a,b] [--dump-uid 0100/01000000] \
    --report out/histcad_conflicts.json
```

它对每个特征：用与翻译器相同的渲染器生成约束前缀 → 实际求解 → 分类
`solved / drifted(>1e-3 mm) / conflicting / exec_error / no-constraints`，并对数据集
**每一条**约束计算"声明值 vs 坐标隐含值"残差。输出交叉表：

```
== outcome x max-residual bucket (per feature) ==
  conflicting    n=1    coarse(>1e-3)=1
  drifted        n=19   round4(1e-5..1e-3)=7  coarse(>1e-3)=4  ...
  solved         n=186  exact(<1e-9)=151  round4=25  ...

== outcome x dof ==            ← 冲突是否集中在 dof=0（过定）
== solved/drifted point displacement ==   ← 求解把几何拉了多远
== per-kind residual medians (all vs failed) ==   ← 哪类约束的值最脏
```

- `--dump-uid <uid>`：打印该 case 每条约束的残差表（`h5_Distance point-point:H
  residual=3.1e-05`），逐条定位到数据集原始条目。
- 残差分档含义：`exact` 与坐标精确一致；`round4`（1e-5~1e-3）= 数据集 4 位舍入级；
  `coarse`（>1e-3）= 粗大矛盾，多半是数据集错误或方言。

### 体积对账

`histcad_validate.py`（上文命令）：`pass / volume_mismatch / build_error` 逐 case
判定，`build_error` 带错误串，报告在 `out/`。想看"带约束构建能过多少"就用
`--constraints on` 跑一遍——失败 case 即约束通道不可用者，再去 conflicts 工具查原因。

### 翻译产物内注记

生成源码头部的 `# feature N: unmapped constraint kinds [...]` 与
`# step N: unsupported (...)` 直接告诉你 A 类缺口在哪。

### 数据集摸底

`histcad_profile.py <json.tar.gz> [...] [--limit N] [--out PATH]` 输出操作/实体/约束
形态分布（out/histcad_profile.json），选型或评估覆盖时先跑它。

---

## 复现口径

本文数字的产生命令（样本与步长固定，可复跑）：

```bash
# 几何通道（另有 deepcad 300 / fusion 150 大样本历史报告）
histcad_validate.py --tar <fusion json> --step-tar <fusion step> --count 100 --stride 83 --constraints off
histcad_validate.py --tar <deep  json> --step-tar <deep  step> --count 100 --stride 577 --constraints off

# 约束通道审计（与上同样本同步长）
histcad_conflicts.py --tar <fusion json> --count 100 --stride 83
histcad_conflicts.py --tar <deep  json> --count 100 --stride 577
```
