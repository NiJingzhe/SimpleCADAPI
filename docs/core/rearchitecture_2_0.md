# SimpleCADAPI 2.0 重构设计文档

## 文档目的

本文档用于汇总并冻结 `SimpleCADAPI 2.0` 的重构方向。核心目标不是继续围绕 `OCP` 做包装，而是把系统重构为一个以 `OCP` 为底层内核、以参数/表达式/操作图/拓扑历史为事实来源的建模系统。

本文档覆盖：

- 2.0 的目标、边界和兼容性要求
- 现状评估与为何必须重构
- 目标架构与核心数据模型
- 参数表达式图方案
- 几何值模型、拓扑追踪、装配约束与序列化方案
- 分阶段迁移计划、测试计划与风险控制

本文档是架构设计稿，不是实现说明书。命名、模块拆分和阶段顺序可以在落地时微调，但本文档中的设计原则和兼容性约束应视为 2.0 的硬边界。

配套执行文档见：`docs/core/rearchitecture_2_0_requirements.md`。

## 当前实现审计（2026-04-14）

### 已完成

- 表达式基础层已落地：`Var/Const/Expr`、`ExpressionGraph`、参数 canonicalization 已可用。
- `GraphSession` 已升级为双图 session：同时维护 `OperationGraph` 和 `ExpressionGraph`。
- `Sketch` 已作为一等对象引入，但没有替代 `Vertex/Edge/Wire/Face/Solid` 主线。
- `Vertex/Edge/Wire/Face/Solid` 已能接受 raw OCC wrapped shape，`wrapped` 已开始成为核心存储。
- `extrude/revolve/fillet/chamfer/shell/cut/union/intersection` 等核心操作已经接入了不同程度的表达式或历史记录能力。
- assembly 约束参数已开始复用同一套表达式系统，`model.json` 也已有 graph + expression 的初步导出能力。

### 仍未完成

- `model.json` 仍不是完整 canonical IR：缺少稳定的 `geometry_registry`、`semantic_delta_log`、`topology_delta_log` 等核心结构。
- graph JSON roundtrip 还没有稳定保留 `SemanticDelta` / `TopoDelta`，会导致 replay 之外的历史信息丢失。
- 自动生成的 `SemanticDelta` 仍存在 `pending` 风格引用，占位语义没有被绑定成稳定的 graph/node 引用。
- Phase 1 曲线/轮廓入口尚未完全表达式化，仍有 primitive/profile API 只能接受纯数值。
- OCP-native evaluator 迁移仍未完成，很多实现仍在直接调用 `cadquery` 构造层。
- `shell` 等操作的可靠拓扑历史仍然不完整，当前更多是“记录结果”而不是“稳定双层 delta”。

### 本轮收敛 TODO

- [x] TODO-IR-001：为 `OperationGraph` 的 JSON roundtrip 补齐 `SemanticDelta` / `TopoDelta` 序列化。
- [x] TODO-IR-002：为 `model.json` 补齐 `geometry_registry`、`semantic_delta_log`、`topology_delta_log`。
- [x] TODO-HIST-001：把自动生成的 `SemanticDelta` 从 `pending` 占位绑定到真实 `graph_id/node_id`。
- [x] TODO-OPS-001：补齐 Phase 1 剩余 primitive/profile API 的表达式入口，至少覆盖 `point`、`line`、`rectangle`、`polyline`。

### 仍待后续轮次完成的大项

- [ ] TODO-KERNEL-001：继续把 evaluator 从 `cadquery` 构造路径迁移到 OCP-native builder 路径。
- [ ] TODO-HIST-002：为 `shell` 等尚未完整追踪的操作补齐稳定 `TopoDelta`。
- [ ] TODO-IR-003：继续扩展 canonical `model.json`，补齐更完整的 geometry/sketch/assembly/stable-ref registry。
- [ ] TODO-FRAME-001：补齐文档中要求的显式 frame / placement 基础设施，而不是只保留当前 workplane 上下文模型。

### 剩余 TODO 审计（本轮整理）

#### 本轮可完成

- [x] TODO-HIST-003：`revolve` 仍未走 tracked history，需补齐稳定 `TopoDelta` 与 graph roundtrip 保留。
- [x] TODO-IR-004：`model.json` 仍缺 `sketch/profile registry`。
- [x] TODO-IR-005：`model.json` 仍缺顶层 `assembly_registry` / `constraint_registry`，当前只有嵌套 assembly payload。
- [x] TODO-DOC-001：把“已完成 / 可完成 / 结构性大项”在审计段落中明确区分，避免 TODO 状态失真。

#### 结构性大项

- [x] TODO-KERNEL-002：`loft/sweep/helical_sweep` 仍主要依赖 CQ 构造层。
- [x] TODO-KERNEL-003：`line/arc/spline/helix` 等 curve evaluator 仍主要依赖 CQ 构造层。
- [x] TODO-SEM-001：`SemanticDelta` 仍以 `ShapeOutput` 为主，尚未升级为更清晰的 feature/body/sketch 语义实体。
- [x] TODO-FRAME-002：缺少独立的 `frame.py` / placement graph，当前空间语义仍主要依附 workplane 上下文。

注：`helical_sweep` 已按组合操作处理，不再作为基础核心 IR 节点记录；图中记录为 `make_helix_wire` + `sweep`。

### 新一轮剩余深化项

- [x] TODO-HIST-004：为 `loft/sweep/helical_sweep` 补更完整的 tracked `TopoDelta`，目前已完成 OCP-native evaluator 替换，但历史记录仍未达到 `extrude/revolve/shell` 同等细度。
- [x] TODO-FRAME-003：把 assembly / instance pose 进一步接入统一 frame graph，而不是仅导出建模 session frame snapshot。
- [x] TODO-SEM-002：继续把语义实体从 `Point/Profile/Body` 扩展到更明确的 `Sketch/Feature/AssemblyConstraint` 级别。

注：`helical_sweep` 作为组合宏，通过 `make_helix_wire + sweep` 继承同等级 history 记录，而不是单独维护基础特征节点。

### 本轮最终状态冻结（2026-04-15）

本轮将 2.0 的“继续推进”收束为一个必须由代码、导出 payload 和测试共同满足的最终状态，而不是停留在设计描述：

- `model.json` 是 canonical export，并可独立 replay。
- `graph` 是唯一真相源，并且必须直接是 canonical low-level graph。
- `leaf_ids` 是多输出场景的显式结果集，不允许默认依赖 `graph.leaf_nodes()` 猜测最终输出。
- canonical `graph` 必须收敛到冻结的基础 op set；任何 convenience op 或 macro-only op 若未 lower，不得进入 `graph`。
- `helical_sweep` 必须始终作为组合宏对待，而不是基础 canonical 节点。
- detail feature 的 canonical 事实来源必须是 explicit selected refs，而不是 `selection_query` 文本。
- `selection_query` 与 `selector_hint` 继续保留，但只作为回放与映射的 fallback 信息。
- `replay_model_json()` 必须直接依赖 `graph`，并对 detail feature 按以下顺序解析选择：
  - explicit topo refs
  - stable indices
  - selection query
  - selector hint

为避免该冻结状态重新退化，本轮同时引入：

- `model.json.canonical_contract` 机器可读合约
- canonical low-level op set 的导出期校验
- 围绕最终状态的专门测试

## 背景与问题定义

当前 `SimpleCADAPI` 已经具备以下基础能力：

- 纯函数风格的几何 API
- `Vertex -> Edge -> Wire -> Face -> Solid` 的几何对象主线
- 操作图记录、序列化与 replay 雏形
- 针对部分 OCP builder 的拓扑历史追踪
- 单独的装配姿态约束系统

但当前系统的事实来源仍然主要是即时构建出的 `OCP`/BRep 对象，而不是统一的参数化模型 IR。这样会导致几个根本问题：

1. 模型结果主要是最终几何，而不是参数化语义对象。
2. 大量核心类型直接持有 `cadquery` 对象，导致内核层与 `OCP` 强耦合。
3. 虽然已经有 graph/history，但还没有覆盖完整的参数、表达式、装配约束与对象空间描述。
4. 拓扑历史目前只覆盖部分操作，且很多 API 仍然是“算完即得 shape”。
5. 当前装配系统主要是姿态求解层，还没有和统一参数图/表达式图/重建图打通。

因此，2.0 的核心任务不是“继续增强现有 CQ 包装层”，而是把系统的中心从“几何结果”切换到“参数化模型”。

## 2.0 总目标

`SimpleCADAPI 2.0` 的目标是构建一个：

- 以 `OCP` 为主要几何内核
- 保留当前纯函数、shape-first 用户体验
- 具备统一参数表达式图
- 具备统一操作图与拓扑历史图
- 具备统一空间描述与装配约束图
- 可序列化、可重放、可增量更新
- 能输出最终 mesh/BRep，也能输出完整参数化中间表示

换句话说，2.0 中：

- `mesh / brep / step / stl` 只是导出结果
- `TopoDS_Shape` 是求值缓存和内核结果
- 真正的事实来源是模型 IR：表达式、变量、几何值、特征、装配、约束、拓扑变化

## 兼容性约束

以下要求已经明确，应作为 2.0 的硬约束：

1. 保留纯函数风格 API。
2. 保留 `Vertex -> Edge -> Wire -> Face -> Solid` 作为公开几何对象主线。
3. 保留现有命名风格，尤其是 `*_rvertex`、`*_redge`、`*_rwire`、`*_rface`、`*_rsolid`。
4. 尽量让现有脚本在小改动下迁移到 2.0。
5. 2.0 第一阶段全部按无单位标量处理，不引入单位系统。

这意味着：

- 2.0 不能把公开 API 改造成 scene graph 风格对象系统。
- 2.0 不能要求用户把所有常量都显式包成 wrapper。
- 2.0 不能把表达式系统设计成破坏现有调用习惯的 DSL。

## 现状评估

### 当前已有的可复用基础

以下模块和设计思路可以直接复用或吸收：

- `src/simplecadapi/graph.py`
  - 已有操作 DAG 记录机制
  - 已有 output lineage 附着机制
- `src/simplecadapi/topology.py`
  - 已有 `OperationGraph`、`OperationNode`、`TopoRef`、`TopoDelta`
- `src/simplecadapi/serializer.py`
  - 已有 graph JSON 导出/导入/replay 思路
- `src/simplecadapi/tracking.py`
  - 已有基于 OCP builder 的 `Modified / Generated / IsDeleted` 历史查询
- `src/simplecadapi/constraints.py`
  - 已有 assembly tree、anchor、constraint、solve 的雏形
- `src/simplecadapi/field.py`
  - 已有可序列化树状语义节点 `ScalarField(op, params, children)` 的前例

### 当前必须重构的核心问题

以下模块当前与 2.0 目标存在结构性冲突：

- `src/simplecadapi/core.py`
  - `Vertex/Edge/Wire/Face/Solid` 直接持有 `cq_*` 对象
  - 类型层与 `OCP` 强绑定
- `src/simplecadapi/operations.py`
  - 大量公开 API 直接调用 `cq.*`
  - 操作定义和求值逻辑、记录逻辑、标签逻辑混杂
- `src/simplecadapi/serializer.py`
  - replay 仍围绕现有 CQ 风格操作重建
- `src/simplecadapi/constraints.py`
  - 装配与主 graph/表达式系统分离

### 当前的关键判断

1. 现有 shape-first API 是资产，不是包袱。
2. 当前 graph/history 雏形是资产，但 schema 和覆盖范围不够。
3. `tracking.py` 说明直接面向 OCP builder 的方向是可行的。
4. 2.0 的问题不是“要不要表达式”，而是“如何在不破坏纯函数 API 的前提下记录表达式”。

## 2.0 设计原则

### 1. 保留 shape-first 与纯函数风格

2.0 对外仍然以几何值为中心：

- `make_line_redge(...) -> Edge`
- `make_circle_rface(...) -> Face`
- `extrude_rsolid(face, ...) -> Solid`
- `fillet_rsolid(solid, ...) -> Solid`

不引入公开的 scene node 概念来替代几何值对象。

### 2. 表达式与历史是横切能力，不替换几何返回类型

表达式图、历史图、拓扑图、装配约束图都应是内部模型层能力。它们增强几何对象，但不改变“函数输入几何，函数返回几何”的用户体验。

### 3. OCP 是 2.0 的主内核

`OCP` 不再是核心几何实现层。2.0 目标是：

- 几何构造、特征、布尔、变换、查询尽量直接通过 `OCP`
- `OCP` 不再是核心 runtime 依赖
- 如需保留 CQ，只能作为开发辅助或过渡期兼容工具，而不是内核前提

### 4. 模型 IR 是事实来源，BRep 是求值产物

2.0 中真正需要持久化和导出的核心数据是：

- variables
- expressions
- frames
- sketches
- feature chain
- assembly instances
- constraints
- semantic delta
- topology delta

### 5. 只把基础操作做成核心语义

2.0 第一阶段只把以下操作作为核心建模语义：

- `line`
- `arc`
- `bspline`
- `sketch`
- `extrude`
- `revolve`
- `fillet`
- `chamfer`
- `shell`
- `cut`
- `union`
- `intersection`
- assembly constraints

其他复杂宏、特例建模函数、evolve case、不稳定脚本能力不作为 2.0 核心 IR 的第一阶段内容。

## 2.0 目标架构

### 总体分层

建议的 2.0 架构分为 6 层：

1. Expression Layer
2. Geometry Value Layer
3. Feature and Operation Layer
4. OCP Evaluation Layer
5. History and Topology Layer
6. Assembly and Serialization Layer

### Layer 1: Expression Layer

负责变量、常量、表达式 DAG、参数求值与 dirty propagation。

输出：

- 标量表达式节点
- 向量/点参数的逐项表达式引用
- 装配约束参数表达式

### Layer 2: Geometry Value Layer

负责对外暴露的几何值对象：

- `Vertex`
- `Edge`
- `Wire`
- `Face`
- `Solid`
- `Sketch`（新增）

这些对象继续作为公开 API 的主线，不被 scene graph 替代。

### Layer 3: Feature and Operation Layer

负责把基础操作定义成稳定的语义节点：

- primitive/profile ops
- feature ops
- boolean ops
- transform/placement ops

### Layer 4: OCP Evaluation Layer

负责：

- 用 OCP 对语义节点求值
- 产出 `TopoDS_Shape` 结果
- 获取 builder 历史信息

### Layer 5: History and Topology Layer

负责：

- operation graph
- semantic delta
- topology delta
- stable refs
- replay

### Layer 6: Assembly and Serialization Layer

负责：

- assembly instances
- anchors
- constraints
- solve
- JSON IR 导入导出
- 下游导出适配器

## 几何值模型

### 公开几何对象不变

2.0 继续保留以下公开类型：

- `Vertex`
- `Edge`
- `Wire`
- `Face`
- `Solid`

新增但不替代主线的对象：

- `Sketch`

### 内部语义：Placement Ownership

2.0 需要一个内部概念来统一空间描述，但这个概念不应演化为公开类型分裂。

定义如下：

- 所有公开几何对象都是一等值对象
- 每个对象都可以回答自己的空间信息
- 但对象的空间信息来源有两种：
  - 自身直接拥有的 frame/placement
  - 从上游 owner、feature 或 assembly instance 推导出的 placement

这只是内部 runtime/IR 约束，不作为用户层公开分类。

### 为什么需要这个内部概念

原因只有两个：

1. 装配约束必须知道姿态是谁在负责。
2. 子拓扑对象的世界位置必须有稳定来源，而不是每个 face/edge 都假装是独立场景节点。

### 统一空间描述

2.0 应提供统一空间描述能力，至少支持：

- 本地 frame
- 世界 frame
- 几何中心/法向/包围盒
- owner/instance 来源

建议通过内部 frame graph 维护，而不是通过隐式全局 workplane 状态维护。

`SimpleWorkplane` 的公开用法可以继续保留，但其实现应逐步切换为显式 frame 组合，而不是只依赖 ambient context。

## 参数与表达式系统

### 目标

参数系统必须满足：

- 对用户尽量无感
- 保留现有纯函数 API
- 可序列化
- 可 replay
- 可做依赖分析和局部重建
- 同时可服务几何参数和装配约束参数

### 选型结论

2.0 采用以下方案：

- `Variable` 显式创建
- 普通常量自动提升为 `Const`
- 只要表达式中出现变量，后续算术运算自动形成 `Expr` DAG
- 所有公开 API 在入口统一进行参数 canonicalization

这是 2.0 第一阶段推荐的表达式图方案。

### 为什么不采用更“魔法”的方案

以下方案不作为 2.0 核心机制：

1. 源码 AST 捕获
   - `inspect.getsource()`、notebook、REPL、skill 环境都不稳定
2. `float` 子类伪装透明数值
   - 与 `numpy`、OCP、C 扩展交互容易静默退化
3. 强制所有参数都手写 wrapper
   - 会破坏当前 API 的简洁性
4. 直接以 SymPy 为核心
   - 过重，不适合作为第一阶段内核

### 推荐 API 形态

推荐新增：

```python
r = scad.var("r", 10.0)
h = scad.var("h", 20.0)

base = scad.make_circle_rface(center=(0, 0, 0), radius=r)
body = scad.extrude_rsolid(base, direction=(0, 0, 1), distance=h)
body2 = scad.fillet_rsolid(body, edges=..., radius=r * 0.1)
```

同时保留原有脚本：

```python
box = scad.make_box_rsolid(10, 20, 30)
```

这时旧脚本里的参数会被当作常量节点处理。

### 核心数据模型

建议定义：

- `Var(name: str, default: float)`
- `Const(value: float)`
- `Expr(op: str, args: tuple[ExprLike, ...])`

Phase 1 的 `Expr` 支持：

- `+`
- `-`
- `*`
- `/`
- `**`
- unary `-`
- `abs`
- `min`
- `max`
- `sin`
- `cos`
- `tan`
- `sqrt`

第一阶段全部按无单位标量处理。

### 参数 canonicalization

所有公开 API 在入口统一完成：

- `float/int -> Const`
- `Var -> Var`
- `Expr -> Expr`
- `tuple/list -> 逐项 lift`

canonicalization 结果至少需要包含：

- 表达式引用
- 当前数值快照

这样：

- OCP evaluator 使用数值快照执行建模
- graph/serializer 使用表达式引用保存依赖关系

### 表达式图与操作图的关系

建议维护两张图：

1. `ExpressionGraph`
2. `OperationGraph`

它们的关系：

- `OperationNode.params` 不直接重复内嵌完整表达式树
- 参数通过 `expr_id` 或 `expr_ref` 指向表达式图节点
- 序列化时，表达式图和操作图共同构成完整模型 IR

好处：

- 变量可在多个特征与约束中复用
- 修改单个变量时，可做精确 dirty rebuild
- graph 更清晰，不会在多个节点中重复复制整棵表达式树

## Sketch 模型

### 为什么必须新增 Sketch

当前系统虽然有 `line/arc/spline/wire/face`，但缺少一等 `Sketch` 对象。这会导致：

- profile 来源不明确
- 2D 语义缺失
- 参数化导出和 replay 时难以表达草图层级

因此 2.0 需要引入 `Sketch`，但 `Sketch` 是增强对象，不替代 `Vertex/Edge/Wire/Face/Solid` 主线。

### Phase 1 的 Sketch 范围

第一阶段 `Sketch` 只负责：

- 容纳 `line`
- 容纳 `arc`
- 容纳 `bspline`
- 生成闭合 loop/profile
- 参与 `extrude`/`revolve` 等特征输入
- 承载表达式参数与 curve identity

### Phase 1 明确不做

第一阶段不做完整 2D sketch constraint solver。

原因：

- 该问题规模远大于当前 2.0 的主目标
- 第一阶段优先保证表达式图、OCP 内核、特征链和装配约束图打通

## 基础操作模型

### 核心基础操作集

2.0 核心操作集如下：

- curve/profile:
  - `line`
  - `arc`
  - `bspline`
  - `sketch`
- solid feature:
  - `extrude`
  - `revolve`
  - `fillet`
  - `chamfer`
  - `shell`
- boolean:
  - `cut`
  - `union`
  - `intersection`
- assembly:
  - rigid constraints and instances

### 变换操作的定位

`translate`、`rotate`、`mirror` 等操作仍应保留为公开 API，但在 2.0 中建议区别对待：

- 对 body/instance，它们优先被建模为 placement/rigid transform 操作
- 对 topology history，它们通常不是创建新特征语义，而是改变对象姿态或结果映射

因此它们应作为支持性核心操作存在，但不抢占“实体特征链”的主轴。

## OCP 内核与求值模型

### 设计目标

2.0 的 evaluator 应做到：

- 输入稳定语义节点
- 输出 OCP shape 结果
- 保留 builder
- 获取拓扑历史
- 产出 semantic delta + topology delta

### OCP-native Wrapper

2.0 的 `Vertex/Edge/Wire/Face/Solid` 应从当前 `OCP` wrapper 切换为 OCP thin wrapper：

- 内部持有 `TopoDS_*`
- 自己实现必要的几何查询
- 尽量避免依赖 `cadquery.Shape` 提供的方法

### 当前可复用方向

`tracking.py` 已经说明以下路径可行：

- 直接保留 OCC builder
- 调用 `Modified / Generated / IsDeleted`
- 构建 `TopoDelta`

2.0 应把这条路径从“局部实验能力”提升为“核心 evaluator 规范”。

## 历史、语义变化与拓扑变化

### 为什么需要双层 delta

只记录最终 shape 不够，只记录 topology delta 也不够。2.0 需要两层变化信息：

1. 语义变化
2. 拓扑变化

### 语义变化

语义变化描述模型层对象发生了什么：

- 新建了哪些对象
- 删除了哪些对象
- 修改了哪些对象

例如：

- 创建一个新 `Sketch`
- 创建一个新 `FeatureNode`
- 替换一个 `Body` 的当前结果

### 拓扑变化

拓扑变化描述 OCP 几何层发生了什么：

- `created`
- `preserved`
- `modified`
- `deleted`

并记录：

- `parent_refs`
- `origin_role`
- 可选 `raw_event`

### 2.0 中每次操作的最小产物

每个基础操作应至少返回或附带以下信息：

- 语义输出对象
- 几何结果对象
- semantic delta
- topology delta
- 输入对象引用
- 参数表达式引用
- 当前参数值快照

### 需要强覆盖的操作

2.0 第一阶段目标是至少让以下操作具备可靠历史：

- `extrude`
- `revolve`
- `fillet`
- `chamfer`
- `shell`
- `cut`
- `union`
- `intersection`

如果某个 OCP builder 无法直接给出完整历史，则 evaluator 必须：

- 明确声明追踪能力等级
- 或通过辅助 diff 机制补全
- 不能悄悄退化成“只有结果 shape，没有变化记录”

## 对象引用与可追踪选择

### 目标

2.0 要求所有重要几何对象都有：

- 可追踪引用
- 可查询空间信息
- 可关联参数来源

### 建议引用体系

建议同时维护两类引用：

1. `SemanticRef`
   - 面向模型对象
   - 用于 feature、sketch、assembly、constraint 级别引用
2. `TopoRef`
   - 面向具体拓扑子形体
   - 用于面/边/顶点级追踪

### 选择策略

延续现有系统中较好的做法：

- shape ref
- selector hint
- selection query
- index fallback

但 2.0 应把它们正式化为稳定 schema，而不是零散 metadata。

## 装配与约束模型

### 当前判断

当前 `constraints.py` 的 assembly 系统有价值，但仍是独立子系统。2.0 需要把它纳入统一模型 IR。

### 2.0 装配目标

2.0 中装配层应负责：

- part definition
- part instance
- instance frame
- anchors
- constraints
- solve result
- 表达式依赖

### 约束参数也使用同一表达式系统

装配约束涉及：

- `distance`
- `offset`
- angle-like parameters
- frame origin/rotation inputs

这些都应复用同一套 `Var/Const/Expr` 系统，而不是单独发明一套 assembly 参数机制。

### 装配层边界

2.0 第一阶段装配约束仍聚焦：

- rigid body pose solving
- 不直接修改 part definition 内部拓扑

也就是说：

- part 的参数变化仍由 feature chain 驱动
- assembly solve 主要改变 instance pose

## 序列化与导出

### 新的 canonical export

2.0 的主导出格式不应是 STEP/STL，而应是模型 IR。

建议采用：

- `model.json`
- 可选 `brep_cache/`
- 可选 replay snapshot

### `model.json` 至少应包含

- schema version
- producer version
- expression graph
- operation graph
- geometry object registry
- sketch/profile registry
- assembly registry
- constraint registry
- semantic delta log
- topology delta log
- optional display/query hints

### STEP/STL/BRep 的定位

这些格式继续保留，但只作为：

- 最终几何导出
- 与外部 CAD/CAE/渲染工具交换最终形状

不作为 2.0 的参数化事实来源。

## 建议的模块重组

以下是建议的 2.0 模块拆分方向：

### 参数与表达式

- `src/simplecadapi/expr.py`
- `src/simplecadapi/eval.py`

### 几何值与 frame

- `src/simplecadapi/geometry.py`
- `src/simplecadapi/frame.py`
- `src/simplecadapi/sketch.py`

### OCP 内核适配

- `src/simplecadapi/kernel/ocp_shapes.py`
- `src/simplecadapi/kernel/ocp_query.py`
- `src/simplecadapi/kernel/ocp_builders.py`

### 基础操作

- `src/simplecadapi/ops/primitives.py`
- `src/simplecadapi/ops/curves.py`
- `src/simplecadapi/ops/features.py`
- `src/simplecadapi/ops/booleans.py`
- `src/simplecadapi/ops/transforms.py`

### 历史与拓扑

- `src/simplecadapi/history/op_graph.py`
- `src/simplecadapi/history/topology.py`
- `src/simplecadapi/history/tracking.py`

### 装配与约束

- `src/simplecadapi/assembly/model.py`
- `src/simplecadapi/assembly/anchors.py`
- `src/simplecadapi/assembly/constraints.py`
- `src/simplecadapi/assembly/solver.py`

### IO 与 replay

- `src/simplecadapi/io/model_json.py`
- `src/simplecadapi/io/replay.py`
- `src/simplecadapi/io/exporters.py`

### 兼容外壳

- `src/simplecadapi/__init__.py`
- `src/simplecadapi/compat/`

兼容外壳负责保留既有 API 名称、签名风格和 import 入口。

## 迁移策略

### 总原则

不建议直接在现有 CQ 内核上“原地爆破式重写”。更稳妥的策略是：

- 在仓库中并行引入 2.0 内核
- 先做新模块和新测试
- 等核心操作链跑通后，再把公开 API 切换到底层新引擎

### 推荐分期

#### Phase 0: 设计冻结

目标：

- 冻结 2.0 设计边界
- 冻结兼容性原则
- 冻结核心 IR schema 草案

交付：

- 本文档
- schema 草案
- 基础类型命名草案

#### Phase 1: 表达式与 frame 基础层

目标：

- 实现 `Var/Const/Expr`
- 实现参数 canonicalization
- 建立 `ExpressionGraph`
- 建立 `Frame` 基础设施
- 支持变量驱动的数值求值与 dirty propagation

交付：

- `var()` API
- 表达式序列化
- 参数快照求值器

#### Phase 2: OCP-native 几何值层

目标：

- 为 `Vertex/Edge/Wire/Face/Solid` 建立 OCP-native wrapper
- 替换当前 `core.py` 的 `cq_*` 主依赖
- 提供面积、体积、法向、bbox、中心等基础查询

交付：

- OCP thin wrapper
- 与现有 API 对应的 geometry query 基线测试

#### Phase 3: Sketch 与基础特征链

目标：

- 引入 `Sketch`
- 支持 `line/arc/bspline/sketch`
- 支持 `extrude/revolve`
- 支持基于表达式参数求值

交付：

- `Sketch` 数据模型
- `extrude/revolve` 的 OCP evaluator
- expression graph 与 operation graph 打通

#### Phase 4: Boolean 与细节特征的完整追踪

目标：

- 支持 `cut/union/intersection`
- 支持 `fillet/chamfer/shell`
- 为这些操作产出可靠 `TopoDelta`
- 引入 `SemanticDelta`

交付：

- 双层 delta 体系
- 稳定引用体系
- 选择与 selector schema

#### Phase 5: Assembly 与约束图整合

目标：

- 将 assembly 从独立模块整合为统一 IR 的一部分
- 约束参数表达式化
- solve 结果可重放、可序列化

交付：

- assembly graph
- constraint graph
- solve snapshot

#### Phase 6: 兼容层切换与导出适配器

目标：

- 用兼容外壳把公开 API 指向新引擎
- 保留旧命名和主要调用方式
- 提供新的 canonical JSON export
- 保留 STEP/STL/BRep 导出

交付：

- 公开 API 迁移
- replay 验证
- 文档与案例迁移

## 测试策略

2.0 必须从一开始就建立测试矩阵，而不是等功能完成后再补。

### 1. 兼容性测试

确保以下内容不被破坏：

- 现有 `make_*`、`*_rsolid` 等函数名
- 现有返回类型主线
- 常量参数脚本可以继续运行

### 2. 表达式测试

至少覆盖：

- `Var/Const/Expr` 构图
- 表达式序列化/反序列化
- 运算符重载正确性
- dirty propagation

### 3. 几何求值测试

至少覆盖：

- `line`
- `arc`
- `bspline`
- `extrude`
- `revolve`
- `cut/union/intersection`
- `fillet/chamfer/shell`

### 4. 拓扑历史测试

至少覆盖：

- `created/preserved/modified/deleted`
- `origin_role`
- `parent_refs`
- selector 回放稳定性

### 5. 装配测试

至少覆盖：

- rigid pose solve
- constraint expression propagation
- solve snapshot replay
- 局部参数变化后的局部重建

### 6. 全链路测试

至少覆盖：

- script -> model.json -> replay -> geometry equivalence
- script -> model.json -> assembly solve -> export

## 风险与控制策略

### 风险 1: 试图一步做太多

控制策略：

- 第一阶段只做基础操作集
- 完整 sketch solver 暂不进入 Phase 1
- 复杂宏与特殊 case 暂不进入核心 IR

### 风险 2: 兼容性被新架构吞掉

控制策略：

- 公开 API 与兼容层分离
- 新内核并行实现
- 迁移期间保留 shape-first 设计不动摇

### 风险 3: 拓扑命名与稳定引用不稳定

控制策略：

- 同时维护 `SemanticRef` 与 `TopoRef`
- 不只依赖索引
- 利用 selector hint、selection query、角色语义和参数来源共同定位

### 风险 4: 表达式系统过于“魔法”导致难维护

控制策略：

- 变量显式
- 常量自动提升
- 不做源码 AST 捕获
- 不做 `float` 伪装继承

## 非目标

以下内容不属于 2.0 第一阶段目标：

- 单位系统
- 通用 CAS 级符号推导
- 完整 2D sketch constraint solver
- 所有历史 CAD 格式的原生参数兼容导出
- 把所有宏函数都纳入核心 IR

## 结论

`SimpleCADAPI 2.0` 的本质不是简单地“把 `cadquery` 换成 `OCP`”，而是把系统从一个以最终几何为中心的 CQ 包装层，重构成一个以：

- 几何值对象
- 参数表达式图
- 基础特征链
- 拓扑变化记录
- 装配约束图

为中心的参数化建模平台。

同时，2.0 不能丢失 `SimpleCADAPI` 当前最重要的设计资产：

- 纯函数风格
- shape-first 用户心智
- `Vertex -> Edge -> Wire -> Face -> Solid` 主线
- 清晰直观的命名和调用方式

因此，2.0 的正确重构路线是：

- 在内部重建核心模型
- 在外部保持 API 风格延续
- 用显式变量、自动表达式提升和 API 边界记录来实现低侵入参数化
- 用 OCP-native evaluator 和双层 delta 来实现可靠历史追踪

这是一个 2.0 级重构，但它的目标不是抛弃已有设计，而是在保留其用户体验的前提下，把它变成一个真正完整的参数化 CAD 系统。
