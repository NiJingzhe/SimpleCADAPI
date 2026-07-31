# STEP BREP 逆向工程方法

本文记录一种面向精确 BREP 的 STEP 逆向工作流。目标不是做出“看起来相似”的模型，而是恢复一个满足以下硬约束的可编辑参数模型：

1. 几何点集一致；
2. BREP 拓扑一致；
3. 解析曲面的参数一致；
4. 边界曲线和关键参数范围一致；
5. 模型能够稳定重建和回放。

当多种特征树都满足这些硬约束时，再用工程师的建模习惯筛选：优先对称、整数或标准尺寸、少量草图、稳定基准、清晰特征依赖和容易修改的参数。

## 1. 先区分五种“一致”

STEP 逆向中最容易犯的错误，是把不同层次的一致混为一谈。

### 1.1 外观一致

截图、网格或渲染结果相似。它只能用于快速发现大方向错误，不能用于验收。

截图看不出：

- 两个相邻面是否已合并；
- 一个圆柱面是整圆还是两个半圆；
- 隐藏孔、沉孔深度和内部台阶；
- 半径的微小差异；
- BREP 邻接关系；
- 曲面的参数原点和方向。

### 1.2 数值摘要一致

包围盒、体积、表面积、质心一致。这比外观更强，但仍不充分。不同实体可能碰巧拥有相同的体积和包围盒。

用途：

- 快速检查单位和坐标系；
- 定位哪个特征导致体积误差；
- 验证孔、槽、台阶的总体材料增减；
- 在迭代过程中排除明显错误。

### 1.3 几何点集一致

两个实体占据完全相同的空间。对实体可用双向布尔差集验证：

```text
A - B 的体积 = 0
B - A 的体积 = 0
```

这是几何一致的硬检查，但它不保证拓扑一致。例如一个完整圆柱面和两个半圆柱面可以表示相同点集。

### 1.4 BREP 拓扑一致

面、边、顶点数量相同，并且面—边—顶点邻接图同构。

仅比较数量还不够。两个模型都可能有 20 个面，但连接方式不同。可靠做法是给图节点添加几何标签，再检查图同构：

- 面标签：类型、面积、几何中心、半径、轴线、球心等；
- 边标签：类型、长度、几何中心、半径、轴线等；
- 顶点标签：三维坐标；
- 图边：Face—Edge 和 Edge—Vertex 关联。

### 1.5 参数化表示一致

同一个几何载体仍可能具有不同参数表示：

- 圆柱轴方向相反；
- 平面原点不同；
- 圆弧起始角不同；
- UV 范围平移或反向；
- 一条整圆边与两条半圆边；
- 相同孔通过不同特征顺序产生不同的曲面参数原点。

有些参数差异只是非唯一表示，不应误判为几何差异；有些则是建模历史的有效证据。必须结合设计语义判断。

## 2. 检查手段速查表

| 检查手段 | 最适合回答的问题 | 能提供的直觉 | 不能单独证明什么 |
|---|---|---|---|
| STEP 实体类型计数 | 文件主要由什么几何组成 | 是机械解析体、自由曲面还是混合模型 | 导入后的唯一拓扑数量 |
| BREP 有效性 | 文件能否作为可靠实体继续运算 | 是否存在开壳、坏边、容差问题 | 几何是否符合设计意图 |
| 唯一 Face/Edge/Vertex 数量 | 拓扑复杂度和分段程度 | 圆是否被拆弧、面是否被切分 | 邻接关系是否一致 |
| 拓扑出现次数 | 面如何重复引用边和顶点 | 是否像闭合流形、是否有非流形连接 | 两模型是否同构 |
| 包围盒 | 单位、整体尺寸和主方向 | 哪个方向可能是厚度或长度 | 内部孔槽和局部形状 |
| 体积/面积/质心 | 材料增减是否正确 | 漏掉的是大特征还是表面细节 | 几何点集和拓扑一致 |
| 解析面类型统计 | 特征家族是否正确 | 孔、倒角、圆角、自由曲面来源 | 每个面的具体位置和连接 |
| 面参数与包围盒 | 单个特征的尺寸和位置 | 半径、轴线、台阶、角度、深度 | 建模历史唯一解 |
| 边类型与端点 | 草图分段和切点 | 整圆/半圆、45 度线、圆角切线 | 隐藏面的完整形状 |
| 面-边-顶点邻接图 | BREP 连接结构是否一致 | 哪个局部特征造成分段差异 | 几何点集必然一致 |
| 双向布尔差集 | 两实体是否占据相同空间 | 几何已经完成，可转向拓扑检查 | 面分段和参数化一致 |
| 多视图截图 | 大方向和明显特征是否正确 | 最快发现轴向、孔位、台阶错误 | 精确尺寸、内部结构和拓扑 |
| 物理截面 | 隐藏结构和不同深度轮廓 | 沉孔、槽、壁厚、局部层级 | 未采样位置必然一致 |
| 截面 XOR | 候选差异出现在哪个区域 | 直接定位下一步应修改的特征 | 连续空间上的严格零差异 |
| UV/曲线参数范围 | 参数历史和特征顺序 | 工具从哪个基准面开始、何时被后续特征裁剪 | 非唯一坐标架必然相同 |
| 模型图回放 | 建模过程能否稳定复现 | 是否依赖交互状态或临时对象 | 回放结果与目标自动一致 |

推荐检查顺序是从便宜到昂贵：

```text
有效性和摘要
-> 解析几何清点
-> 多视图和少量关键截面
-> 面边参数与邻接
-> 候选构建
-> 双向差集
-> 图同构
-> 参数历史
-> 回放
```

不要一开始就对所有点做高密度分类，也不要一开始就逐个比较 STEP 文本实体。前者成本高且信息增量有限，后者会被导出器编号和非唯一参数化干扰。

## 3. 推荐的分阶段工作流

### 3.1 阶段 A：建立不可变基准

在写建模代码前，先从原始 STEP 导出一份机器可读报告。可以先用文本清点快速了解文件组成：

```bash
rg -o '^[[:space:]]*#[0-9]+[[:space:]]*=[[:space:]]*[A-Z0-9_]+' model.step \
  | sed -E 's/.*=[[:space:]]*//' \
  | sort \
  | uniq -c \
  | sort -nr
```

这能快速发现 `ADVANCED_FACE`、`PLANE`、`CYLINDRICAL_SURFACE`、`B_SPLINE_SURFACE_WITH_KNOTS` 等实体，但它只是 STEP 表示层清点。`EDGE_CURVE` 数量不一定等于内核导入后的唯一 Edge 数量；退化边、缝边和表示方式都会造成差异。最终基准必须来自导入后的 BREP。

机器可读报告至少包括：

- STEP 是否能读取；
- 转移根数量；
- BREP 是否有效；
- Solid、Shell、Face、Edge、Vertex 数量；
- 唯一拓扑数量和拓扑出现次数；
- 包围盒、体积、表面积、质心；
- 面类型统计；
- 边类型统计；
- 每个面的面积、UV 范围、解析曲面参数和邻接边；
- 每条边的类型、参数范围和邻接面。

唯一数量和出现次数必须分开：

```text
unique_edges       BREP 中不同的边对象数量
edge_occurrences   遍历所有面时边被引用的总次数
```

在闭合流形实体中，一条普通边通常被两个面引用，因此出现次数通常接近唯一边数的两倍。

正式实现位于：

```text
src/simplecadapi/inverse_engineer/brep/inspect.py
src/simplecadapi/inverse_engineer/brep/model.py
```

Python API：

```python
from simplecadapi.inverse_engineer import brep

report = brep.inspect_step(path="model.step")
report.write_json("model-report.json")

summary = brep.get_model_summary(path="model.step")
face = brep.inspect_entity(path="model.step", entity_id="face:0")
```

这些查询默认保持紧凑。需要精确自由曲线或曲面载体时，使用 targeted opt-in，而不是
整份读取大报告：

```python
edge = brep.inspect_entity(
    "model.step",
    "edge:4",
    include_curve_definition=True,
)
surface = brep.inspect_entity(
    "model.step",
    "face:12",
    include_surface_definition=True,
    max_surface_control_points=256,
)
boundary = brep.extract_face_boundaries(
    "model.step",
    "face:12",
    compact=True,
    include_curve_definitions=True,
    curve_definition_edge_ids=["edge:4", "edge:7"],
    max_total_control_points=256,
)
section = brep.make_section(
    "model.step",
    origin=(0, 0, 0),
    normal=(1, 0, 0),
    compact=True,
)
```

单条 B-spline/Bezier edge 定义没有控制点上限，应先读 `pole_count`；surface 和 boundary
batch 分别受 `max_surface_control_points` 和 `max_total_control_points` 约束。boundary
definitions 按规范 stable edge ID 去重、排序，不保留请求或 coedge 顺序；后者应从 loop
的 `edges` 数组读取。不支持完整参数化的 curve carrier 返回 `available=false`，不会把
摘要冒充精确定义。曲面定义是未裁剪 carrier；UV 范围和 trim loop 必须单独保留。超过
控制点上限时查询直接失败，不会返回不完整定义。
`get_model_summary(include_parameter_groups=True)` 同时提供有界 carrier、规范化轴线和邻接
签名分组；这些仍只是描述性多重度，不证明 pattern。

Agent tool 的 `compute_material_difference` 默认返回 `method="common_volume"` 的快速体积估计；
Python API 默认保留双向 cut components。严格材料验收应显式使用
`include_components=True, boolean_tolerance=None`。带 fuzzy tolerance 的结果只适合诊断，
不能证明相等，并会标记 `strict_equality_supported=false`。

需要连续调查多个实体时，应复用已索引模型：

```python
model = brep.load_step_model("model.step")
summary = model.summary()
face = model.describe_entity("face:0")
edge = model.describe_entity(face["adjacency"]["edges"][0])
```

稳定实体 ID 使用零基格式：

```text
body:0
face:12
edge:4
vertex:8
```

同一未修改 BREP 的重复加载会得到相同 ID。ID 表示确定的拓扑遍历位置，
不表示两个不同模型之间已经建立了语义对应；跨模型匹配必须另做实体对应分析。
退化边的 `geometry.type` 固定为 `DEGENERATE`，同时通过
`geometry.underlying_curve_type` 暴露其底层曲线载体，避免把零长度拓扑边误当普通曲线。

连续多轮调查和比较可直接使用框架无关的 Agent 工具注册表：

```python
schemas = brep.agent_tool_schemas()
summary = brep.call_agent_tool(
    "get_model_summary",
    {
        "model_path": "model.step",
        "include_parameter_groups": True,
    },
)
```

`parameter_groups` 只给出同类解析半径、B-spline 阶次等客观多重度和少量
示例 ID，固定标记 `pattern_inference=not_performed`。相同半径或相同数量不能
单独证明重复特征；只有空间中心/轴线、方向、间距与邻接签名同时规律时，才把
它作为阵列假设。无此证据时应继续考虑旋转、拉伸、扫掠、Loft、混合特征或
自由曲面。

调查长边界时优先使用 `extract_face_boundaries(compact=True)`；它保留有序
coedge 的类型、长度、端点、方向和关键参数，避免完整采样数组占满上下文。

工具分为两组：

- 局部调查：`get_model_summary`、`inspect_entity`、
  `get_topology_neighborhood`、`measure_relation`、`make_section`、
  `extract_face_boundaries`、`probe_point`、`render_region`。
- 比较验收：`compare_global_properties`、`compare_boundary_distance`、
  `compute_material_difference`、`compare_sections`、
  `build_difference_regions`、`find_nearby_entities`、`compare_entities`、
  `evaluate_result`、`compare_brep_strict`。中心切片保留为 Python/CLI
  可视化辅助能力，不作为默认 Agent 工具。

自由曲面模型不能只看稳定实体摘要。`inspect_step()` 的完整报告会保留
B-spline/NURBS 的 degree、knot values、multiplicities、control points 和
rational weights；`inspect_entity()` 默认只返回 degree、pole/knot 数量等局部摘要。
单条曲线可通过 `include_curve_definition=True` 返回完整定义；单个 B-spline/Bezier
carrier surface 可通过 `include_surface_definition=True` 按显式控制点预算返回。只有需要
跨大量实体的完整自由曲面证据时，才读取完整报告。

CLI：

```bash
uv run simplecad-brep inspect model.step -o model-report.json
uv run simplecad-brep tools
uv run simplecad-brep tool inspect_entity \
  --arguments '{"model_path":"model.step","entity_id":"face:0"}'
```

### 基础属性代码片段

```python
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps

assert BRepCheck_Analyzer(shape).IsValid()

bbox = Bnd_Box()
BRepBndLib.AddOptimal_s(shape, bbox)
print("bbox", bbox.Get())

volume_props = GProp_GProps()
BRepGProp.VolumeProperties_s(shape, volume_props)
print("volume", volume_props.Mass())
print("center", volume_props.CentreOfMass().Coord())

area_props = GProp_GProps()
BRepGProp.SurfaceProperties_s(shape, area_props)
print("area", area_props.Mass())
```

### 3.2 阶段 B：恢复坐标语义

不要根据 `X/Y/Z` 名称直接假设左右、前后和高度。

应综合使用：

- 包围盒三个跨度；
- 主成分分析；
- 平面和圆柱轴线分布；
- 对称平面拟合；
- 正交视图和典型截面；
- 机械功能，例如孔轴通常对应装配或加工方向。

坐标语义判断错误会导致整个特征解释反转。比如一个方向上的 U 形截面可能是左右对称结构，也可能被错误解释为前后凹槽。

### 3.3 阶段 C：做解析几何清点

解析面类型是最有价值的“建模指纹”之一。

| 几何类型 | 常见来源 | 可恢复的信息 |
|---|---|---|
| Plane | 拉伸端面、切割平面、倒角 | 基准方向、台阶位置、厚度、角度 |
| Cylinder | 孔、轴、拉伸圆弧、直边圆角 | 半径、轴线、深度、圆弧分段 |
| Sphere | 三条圆角边交汇、球切割 | 圆角半径、特征交汇方式 |
| Torus | 圆弧轮廓的边圆角、环形过渡 | 主半径、次半径、圆角中心 |
| Cone | 锥孔、沉头、拔模 | 锥角、轴线、顶点 |
| BSpline | 放样、填充、自由曲面 | 次数、节点、控制点、连续性 |

例如：

```text
4 个 R1 Sphere
4 个 (R2, R1) Torus
14 个 R1 Cylinder
```

通常不是手工拼出的 22 个面，而是一次连续局部 R1 圆角的结果。解析面组合比截图更能揭示特征操作。

### 读取解析曲面参数

```python
from OCP.BRepAdaptor import BRepAdaptor_Surface

surface = BRepAdaptor_Surface(face, True)
kind = surface.GetType()

cylinder = surface.Cylinder()
print("radius", cylinder.Radius())
print("axis", cylinder.Axis().Direction().Coord())
print("origin", cylinder.Location().Coord())

sphere = surface.Sphere()
print("radius", sphere.Radius())
print("center", sphere.Location().Coord())

torus = surface.Torus()
print("major", torus.MajorRadius())
print("minor", torus.MinorRadius())
```

### 3.4 阶段 D：从平面和边恢复尺寸关系

不要只读包围盒。每个解析面的平面方程、轴线和边界端点能够恢复：

- 台阶高度；
- 壁厚；
- 孔深；
- 孔距；
- 对称位置；
- 45 度倒角；
- 圆角切点；
- 草图中的直线方程。

例如一组斜面端点满足：

```text
x + |z| = 1.25
```

这比“看起来大约 45 度”更强，说明草图很可能使用了对称 45 度约束。

### 读取边端点和类型

```python
from OCP.BRepAdaptor import BRepAdaptor_Curve

curve = BRepAdaptor_Curve(edge)
first = curve.FirstParameter()
last = curve.LastParameter()
p0 = curve.Value(first)
p1 = curve.Value(last)

print("type", curve.GetType())
print("start", p0.Coord())
print("end", p1.Coord())

if "Circle" in str(curve.GetType()):
    circle = curve.Circle()
    print("radius", circle.Radius())
    print("center", circle.Location().Coord())
```

### 3.5 阶段 E：建立直观图像，但只让它承担合适的职责

推荐同时生成：

1. 等轴视图；
2. 三个正交视图；
3. 关键高度或轴向位置的占用截面；
4. 目标/候选叠加图；
5. XOR 差异图。

多视图适合发现：

- 坐标方向错误；
- 漏掉大特征；
- 孔位错误；
- 台阶方向错误；
- 圆角范围过大；
- 草图轮廓错误。

截面图适合发现：

- 内孔层级；
- 沉孔深度；
- 不同高度处的轮廓变化；
- 隐藏槽；
- 两实体的局部差异。

正式实现：

```text
src/simplecadapi/inverse_engineer/brep/render.py
src/simplecadapi/inverse_engineer/brep/slices.py
```

渲染图片需要可选依赖：

```bash
uv sync --extra inverse-engineer
```

Python API：

```python
from simplecadapi.inverse_engineer import brep

brep.render_step_views(step_path="candidate.step", output_path="candidate-views.png")
comparison = brep.compare_step_slices(
    target_path="target.step",
    candidate_path="candidate.step",
    output_path="slice-overlay.png",
)
```

CLI：

```bash
uv run simplecad-brep render candidate.step candidate-views.png
uv run simplecad-brep slices target.step candidate.step slice-overlay.png
# 默认自动检查联合包围盒的 X/Y/Z 中心截面；特征边界应显式追加：
uv run simplecad-brep slices target.step candidate.step feature-slices.png \
  --slice xz:-1.6 --slice xz:4.0 --slice xy:0
```

截面分类示例：

```python
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_ON
from OCP.gp import gp_Pnt

classifier = BRepClass3d_SolidClassifier()
classifier.Load(shape)
classifier.Perform(gp_Pnt(x, y, z), 1e-8)
inside = classifier.State() in (TopAbs_IN, TopAbs_ON)
```

默认截面只用于快速建立直觉。逆向时应进一步选择穿过特征边界、台阶高度、沉孔肩部、对称面和疑似差异区域的物理截面。

注意：逐点 BREP 分类较慢。截面图是诊断工具，应控制分辨率；几何硬验收应使用布尔差集，而不是靠提高图片分辨率。

### 3.6 阶段 F：提出最小特征假设

先写出一个人类可读的候选特征树，不要马上编码大量细节。

好的候选通常包含：

- 一个主草图和一次拉伸；
- 对称约束或镜像；
- 少量孔、槽、台阶；
- 局部圆角和倒角；
- 清晰的加工顺序。

每个参数都应能由原始 BREP 的证据解释。例如：

```text
R1      来自 14 个 R1 圆柱、4 个 R1 球和 4 个次半径 R1 的圆环
R3.25   来自沉孔圆柱
R1.7    来自贯穿孔圆柱
X=3.25  来自台阶平面
Z=±6    来自对称孔轴
```

避免在没有证据时使用：

- 随机小偏移；
- 大量补偿布尔体；
- 任意样条；
- 网格拟合；
- 按最终面逐面拼壳。

### 3.7 阶段 G：按特征逐步落地

每一步都打印少量有意义的基准：

```python
print(
    "ground opening fillet",
    body.get_volume(),
    len(body.get_faces()),
    len(body.get_edges()),
)
```

推荐顺序：

1. 主轮廓；
2. 主拉伸；
3. 大型切除或并集；
4. 台阶；
5. 孔；
6. 圆角和倒角，或根据几何指纹调整到正确历史位置；
7. 输出 STEP；
8. 生成报告和截图；
9. 对比；
10. 只修改造成当前差异的特征。

不要一次添加所有特征。否则拓扑不一致时无法知道是哪一步造成的。

## 4. 从差异反推建模历史

### 4.1 面数少但几何相同：检查草图分段

典型情况：

```text
目标：每个孔壁由两个半圆柱面组成
候选：每个孔壁是一个完整圆柱面
```

二者几何点集相同，但拓扑不同。原因通常不是布尔算法随机拆面，而是草图边界不同：

```text
完整圆边拉伸       -> 一个圆柱侧面
两条半圆弧闭合拉伸 -> 两个半圆柱侧面
```

因此，拓扑差异常常能反推草图实体数量。

### 4.2 面数多且出现额外平面：检查错误的布尔拆分

把一个圆柱工具拆成左右两个半圆实体分别切除，会得到两个半圆柱面，但也会引入径向分隔平面。

这是一条重要经验：

> 想得到分段侧面，应在草图边上分段，而不是把实体工具分成多个带内部平面的实体。

### 4.3 几何和拓扑相同但 UV 不同：检查特征顺序

典型沉孔：

```text
方案 A：先沉孔，再从肩部开始切小孔
方案 B：先切贯穿小孔，再切大沉孔
```

两者最终几何可能相同，但小孔圆柱支撑面的参数原点不同。

如果目标小孔的圆柱原点位于入口平面，UV 还保留了被沉孔切掉的参数区间，这通常说明：

```text
先贯穿孔
再沉孔
```

特征顺序不仅影响工程可读性，也会影响 STEP 中保留的曲面参数。

### 4.4 球面和圆环面组合：检查三维圆角交汇

二维草图圆角后拉伸，常产生圆柱面；对三维实体的多条相交边做圆角，会进一步产生球面和圆环面。

因此：

- 只有圆柱圆角面：可能是二维圆角轮廓拉伸；
- 同时出现球面和圆环面：更像三维成组选边圆角；
- 球面半径和圆环次半径相同：通常直接给出圆角半径。

## 5. 严格验收方法

### 5.1 双向布尔差集

```python
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps


def cut_volume(a, b):
    operation = BRepAlgoAPI_Cut(a, b)
    operation.SetFuzzyValue(1e-9)
    operation.Build()
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(operation.Shape(), props)
    return props.Mass()

assert cut_volume(target, candidate) < 1e-9
assert cut_volume(candidate, target) < 1e-9
```

这证明实体点集相同，但仍需拓扑检查。

### 5.2 几何标记的邻接图同构

正式实现位于：

```text
src/simplecadapi/inverse_engineer/brep/compare.py
```

Python API：

```python
from simplecadapi.inverse_engineer import brep

comparison = brep.compare_steps(target_path="target.step", candidate_path="candidate.step")
assert comparison.hard_gate_passed
```

CLI：

```bash
uv run simplecad-brep compare target.step candidate.step -o comparison.json
```

报告应同时满足：

```text
same_geometric_point_set = true
geometry_labelled_incidence_graph_isomorphic = true
```

### 规范化非唯一参数

比较几何载体时，不要直接比较平面原点或轴向符号。

平面可规范为：

```text
单位法向 n
有符号距离 d = n dot p
```

轴线可规范为：

```text
单位方向 d，统一符号
原点到世界原点的最近点 p - d(d dot p)
```

这样可以识别“同一个平面但原点不同”和“同一根轴但方向相反”。

### 5.3 参数化表示检查

完成几何和拓扑硬检查后，再检查：

- UV 范围；
- 圆柱、圆锥、圆环坐标架；
- 圆弧参数范围；
- B 样条次数、节点、重数、控制点和权重；
- 边方向和面方向；
- 曲面原点是否反映预期特征顺序。

不要把所有参数差异都当成错误。先问：

1. 这是非唯一坐标架选择吗？
2. 它是否改变几何点集？
3. 它是否改变 BREP 邻接？
4. 它是否揭示不同的草图分段或特征顺序？
5. 用户要求的是精确 BREP，还是 STEP 文本字节一致？

STEP 实体编号和文本顺序通常不属于 BREP 本体，不应作为几何逆向的默认验收项。

### 5.4 回放验收

逆向模型不能只在当前 Python 进程中成功。应记录模型图，重新播放，再对回放结果执行相同检查。

```python
import simplecadapi as scad

with scad.GraphSession(graph_id="reverse_part") as session:
    body = build_body()
    scad.capture_result(value=body)

payload = scad.export_model_json(session)
rebuilt = scad.replay_model_json(payload)[0]
scad.export_step(rebuilt, "replayed.step")
```

需要分别比较：

```text
原始 vs 直接构建
原始 vs 回放构建
直接构建 vs 回放构建
```

## 6. 高效迭代策略

### 6.1 用差异类型决定下一步

| 当前差异 | 优先检查 |
|---|---|
| 包围盒错误 | 坐标系、单位、基准位置 |
| 体积差很大 | 漏掉主切除/并集、特征方向错误 |
| 体积接近但面积差大 | 圆角、倒角、孔壁或隐藏台阶 |
| 几何相同但面数少 | 草图边分段不足、同域面被合并 |
| 几何相同但面数多 | 多余切割平面、重复布尔、错误拆工具 |
| Sphere/Torus 数量错误 | 圆角选边范围或圆角时序 |
| Cylinder 数量错误 | 圆/圆弧草图分段、孔特征顺序 |
| 拓扑计数相同但图不同 | 面邻接、边界方向、错误局部连接 |
| UV 原点或范围错误 | 特征创建顺序、工具起始平面 |

### 6.2 先匹配低维输入，再匹配高维结果

工程特征一般遵循：

```text
点/尺寸 -> 草图边 -> 闭合轮廓 -> 面 -> 拉伸/旋转 -> 布尔 -> 圆角
```

当最终圆柱面分段不对时，优先检查草图圆弧数量，而不是在最终实体上补切割面。低维输入通常才是拓扑来源。

### 6.3 用解析面统计做中间目标

完整拓扑还没对齐时，解析面统计是非常有效的阶段目标。例如：

```text
目标：Plane 16, Cylinder 22, Sphere 4, Torus 4
```

候选若为：

```text
Plane 16, Cylinder 18, Sphere 4, Torus 4
```

说明主体、台阶和圆角网络很可能已正确，剩余问题集中在圆柱类特征，不应重做整个主体。

### 6.4 保存候选，但不要让试验污染最终入口

建议保留：

- 每轮 STEP；
- 每轮报告；
- 每轮截图；
- 差异日志；
- 被否定的假设及原因。

最终应收敛为一个独立、可读、可回放的入口，不能依赖多个临时试验脚本互相导入。

## 7. 本次实践中走过的弯路

### 7.1 只根据截图猜主特征

问题：截图遮挡内部结构，容易把缺口、孔和圆角顺序解释错。

改进：截图只用于提出假设；立即用解析曲面、面边界和截面验证。

### 7.2 对所有边做圆角

问题：`fillet(all_edges)` 产生了过多球面，且破坏目标的平面和圆环统计。

改进：根据设计语义分组选边。先识别“左侧开口轮廓”这一语义组，再验证它生成的解析面组合。

### 7.3 用两个半圆实体切出分段孔

问题：虽然圆柱面数量增加到目标值，却额外产生了两个径向平面。

改进：用两条半圆弧组成一个闭合草图，再做一次拉伸切除。

### 7.4 把体积和面积一致当作完成

问题：完整圆柱孔和两个半圆柱孔具有相同几何、体积和面积，但拓扑不同。

改进：加入唯一拓扑数量、解析面统计和邻接图同构。

### 7.5 直接比较平面原点和轴向

问题：同一个平面可选择任意平面内原点，同一根轴可反向，导致大量假差异。

改进：比较规范化平面方程和规范化轴线，不比较任意坐标架选择。

### 7.6 截面采样过密

问题：逐点 BREP 分类成本高，六张高分辨率截面会超时。

改进：截面图保持适中分辨率用于直观诊断；精确几何一致由双向布尔差集负责。

### 7.7 先做沉孔再从肩部做小孔

问题：最终几何和拓扑正确，但小孔圆柱参数原点与目标不同。

改进：先从入口平面做贯穿孔，再做沉孔。这个顺序既符合常见加工意图，也复现目标 UV 历史。

## 8. 推荐的自动化产物

每个逆向任务建议固定生成：

```text
reference_report.json
candidate_report.json
candidate.step
candidate_replayed.step
candidate.model.json
candidate_views.png
candidate_slice_overlay.png
candidate_brep_compare.json
```

几何等价验收至少包括 BREP 有效、模型图可重放、回放结果有效，以及有效布尔结果
证明双向材料差在指定容差内。只有要求 Exact BREP 时，才额外检查：

```text
唯一 Face/Edge/Vertex 数量一致
解析面和边类型统计一致
几何标记邻接图同构
关键解析参数一致
```

对于闭合实体，默认验收不要先做高密度全局边界采样。先检查有效性和全局
属性，再计算双向材料差；材料点集一致即可判定几何等价。只有明确要求
exact BREP 时才继续检查严格拓扑。若材料不同，
再由 Agent 按需调用 `compare_boundary_distance`、`compare_sections`、
`build_difference_regions`、`find_nearby_entities`、`compare_entities` 和
`render_region` 定位下一处修改。边界距离、截面和渲染是诊断工具，不是每轮
候选的默认开销。

## 9. 核心方法总结

最有效的逆向顺序不是“看图后直接建模”，而是：

```text
建立精确基准
-> 恢复坐标语义
-> 清点解析几何
-> 从平面、轴线和边界恢复尺寸关系
-> 用多视图与截面建立直觉
-> 提出最小工程特征树
-> 逐特征构建和输出
-> 用差异类型指导下一轮
-> 双向差集验证几何
-> 几何标记图验证拓扑
-> UV/曲线参数验证特征历史
-> 模型图回放并重复全部验收
```

最重要的判断原则是：

> 几何和拓扑是硬约束；工程师先验只用于在满足硬约束的多种过程之间做选择。解析几何告诉我们“是什么”，拓扑分段告诉我们“草图如何画”，参数范围和坐标架经常告诉我们“特征按什么顺序做”。
