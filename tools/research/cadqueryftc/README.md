# CadQuery → FTC 翻译工具集

把 CadQuery 程序（BenchCAD parquet 或单个源文件）翻译成本仓现行 FTC
（Feature Tree Convention）Python 源码。结构与 `tools/research/histjson`
对齐：**四件工具 + 责任墙**——翻译器只翻译，对不对、准不准的问题全部
外置给验证器。

源自 PR #30（`feat/cadquery_converter`，zhuxiahai）的运行时 tracer 思路；
其发射层（SFTC 模板、`@scad.model`/`scad.var`/`print('volume')` 自检、
list-comprehension 选边）按现行正典重写为 FTC 形状。

## 两段式设计

```
CadQuery 源码 ──(stage 1: 真实执行+插桩)──▶ trace.json ──(stage 2: 纯翻译)──▶ *.ftc.py
                .venv-cq (Python 3.11)      唯一握手物        仓库 .venv (3.10)
```

- **Stage 1（tracer）** monkey-patch `cq.Workplane` 的构造器与 ~37 个方法，
  记录每次调用的实参（Vector/Location 已序列化）、resolve 后的平面标架
  （origin/normal/xDir）、选择器字符串，以及**实际选中的面/边的几何指纹**
  （type/center/normal/direction/length/area）——不记 CQ 拓扑索引（不可
  移植），记几何特征，翻译期按几何重匹配。执行结束顺手记录 ground truth
  （体积+包围盒）进 trace 头部。
- **Stage 2（replayer）** 单遍状态机扫 trace：平面标架跟踪、pending 剖面
  累积（moveTo→lineTo→threePointArc→close）、rarray/polarArray/pushPoints
  网格、嵌套工具链（`cut(tool_workplane)`）整段切出递归重放，发射为 FTC 块。

## 四件工具

| 工具 | 环境 | 职责 |
| --- | --- | --- |
| `cadquery_trace.py` | `.venv-cq`（需要真 cadquery） | 捕获 trace：源码/parquet → `*.trace.json` |
| `cadquery_to_ftc.py` | 仓库 `.venv`（纯 Python） | 翻译：trace → `*.ftc.py` + `*.meta.json` |
| `cadquery_validate.py` | 仓库 `.venv` | 验收对账：执行 FTC 源码，体积/包围盒 vs trace 真值，分级 accepted / partial / rejected |
| `cadquery_profile.py` | 仓库 `.venv`（parquet 需 pyarrow） | 摸底：op 直方图、选择器分布、不支持 op 覆盖 |

### 环境（一次性）

```bash
# cadquery 2.8 需要 Python>=3.11；仓库官方 pin 仍是 3.10，不动。
uv venv .venv-cq --python 3.11
uv pip install --python .venv-cq/bin/python 'cadquery==2.8.0' pyarrow
```

### 复现口径（四个内置 fixture 的全绿基线）

```bash
OUT=tools/research/cadqueryftc/out
for f in washer hexnut rarray_plate revolve_ring; do
  .venv-cq/bin/python tools/research/cadqueryftc/cadquery_trace.py \
    --input test/cadquery_traces/$f.cq.py --stem $f --out $OUT/traces
done
.venv/bin/python tools/research/cadqueryftc/cadquery_to_ftc.py \
  --traces-dir $OUT/traces --out $OUT/ftc
.venv/bin/python tools/research/cadqueryftc/cadquery_validate.py \
  --ftc-dir $OUT/ftc --traces-dir $OUT/traces --report $OUT/validate.json
```

当前基线：4/4 accepted，体积误差 ≤ 2.2e-12（含 `edges(">Y").chamfer` 的
QL 选边对账）。`test/cadquery_traces/` 里烘焙了同一批 trace 与源程序，
`test/test_cadquery_translation_output.py` 在**不装 cadquery** 的普通 CI
环境里钉住格式契约 + 体积对账。

## 输出格式（FTC 契约要点）

- 块头 `# ---- feature: <slug> (<role>[, profile=geometry][, path=geometry]) ----`，
  角色闭集 `build|add|subtract|intersect|modify|pattern|annotate`；slug 用
  op 语义名（`pocket-cut`、`through-cut`、`countersink-hole`…），仅在撞名时
  加去重后缀——去重计数不是位置身份。
- CadQuery trace 不携带约束：所有剖面都是转录几何，平面剖面仍走 sketch API
  （`make_sketch_rsketch` + `add_*_rsketch` + `make_face_from_sketch_rface`，
  局部坐标、点池去重、三点弧过外心），诚实标注 `profile=geometry`（几何档
  第 2 条豁免）。插值样条/螺旋线 sketch API 表达不了：走
  `make_interpolated_spline_rwire` / `make_helix_rwire`，标 `path=geometry`。
- 布尔一律列表形 `cut_rsolid(_b, [tools])`；多体走 histjson 同款
  `bodies` 数据流（加=逐体 try-union 循环，减/交=列表推导，修改=守卫循环），
  末端 `_merge_bodies`。
- fillet/chamfer/shell 的选择集从**指纹合成 QL 谓词**（`geom.type` +
  `geom.center.*`/`geom.normal.*` 容差带 + 基数 `.take(n).exactly(n)`），
  生成源码里不存在免参拓扑枚举。
- 通孔/穿透刀具长度由 trace 包围盒推导，不用魔法数 1000。
- 生成源码零自检（无 print/assert/体积校验）；数字全字面量（trace 里没有
  命名参数，翻译器不发明参数名）。翻译完整性提示只出现在块尾注释与
  `*.meta.json`（`unsupported` 列表，永不静默丢弃——未知 op 也会记 note）。

## 已知边界（meta 里如实记 note）

- `extrude(taper=)` 仅支持圆剖面（锥台=两圆截面 loft，精确）；非圆 taper 记
  note 跳过。
- 开口线剖面无法 `sweep`（SDK 需闭合面）；记 note 跳过。
- pattern 内仅 rect/circle/闭合 wire 剖面；其余记 note。
- CQ 相切/离散复合体：逐体 union 失败的部件留在 `bodies` 外（单流形契约），
  体积对账会如实暴露差值——翻译器不做几何修补（不 nudge、不静默吞）。
- 静态 AST 翻译路径与打分/edit-bench（PR 中的 scoring/、Code-QA）未移植：
  PR 自标 exploratory，不在四阶段规范内；需要时从 PR 分支取。

## 历史注记

- tracer/（instrument、fingerprint、cq_runner、worker）与 replayer 状态机
  骨架移植自 PR #30 `tools/cadquery_converter`（运行时捕获思路保留）；
  发射层、角色/块头、QL 选边、验证器、CLI 按本仓 histjson 四阶段规范重写。
- 测试 fixture 的 trace 由 cadquery 2.8.0 真实执行捕获（2026-09，本机
  `.venv-cq`），非手工构造。
