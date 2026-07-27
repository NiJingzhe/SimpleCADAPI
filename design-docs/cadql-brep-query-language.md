# CADQL: 基于 BRep Graph 的结构化查询语言设计

## 文档状态

- 状态：Proposed; transitional scoped semantics implemented
- 目标版本：CADQL Query IR 1.0
- 目标项目：SimpleCADAPI 2.x
- 主要影响模块：`ql.py`、`core.py`、`topology.py`、`graph.py`、`serializer.py`、各 translator backend
- 非目标：在第一阶段引入 GraphQL Server、HTTP API 或第三方 GraphQL runtime

### 当前实现边界

当前代码尚未实现本文定义的完整 CADQL Query IR。已落地的过渡 subset 仅包括现有 `ShapeSelector` 上的 scoped tag predicate、typed tracking predicates、source-preserving `TagBinding` assignment，以及 graph/model schema `2.0` 中的 semantic replay。该 subset 不等于 typed graph-pattern evaluator、完整 Topology Evolution Graph、named-port schema `3.0` 或跨 backend provider parity。

因此，下文 Phase 1-7 仍是 proposed roadmap；已实现的 tagging/tracking subset 应按 `design-docs/cadql-tagging-and-auto-semantics.md` 的 bounded transition 状态理解。

## 1. 摘要

SimpleCADAPI 需要一套以 BRep topology graph 为基础、同时支持几何属性和 semantic tags 的结构化查询语言。该查询语言必须满足：

1. 查询意图能够进入 canonical operation graph，并可序列化、重放和翻译。
2. 查询结果不依赖未定义的 BRep 枚举顺序。
3. 几何条件具有明确的单位、容差和方向语义。
4. semantic tag 查询能够区分 local、inherited、effective 和 lineage scope。
5. 查询的 cardinality 和歧义策略是正式 contract，而不是调用端的临时检查。
6. Python replay、FreeCAD translator 和未来 translator 使用相同查询语义。
7. 查询意图与一次执行产生的几何 fingerprint/evidence 分离。

本方案借鉴 GraphQL 的 schema、类型验证、variables、fragments、selection set 和结构化错误，但不直接使用 GraphQL 作为核心执行模型。Canonical contract 是一个强类型、JSON 可序列化的 CAD Query IR。GraphQL-like 文本、Python builder、GUI 和 LLM 都只是 Query IR 的前端。

## 2. 背景与问题

当前 selection 体系由多套机制叠加形成：

- `get_edges(index)`、`get_faces(index)` 等 indexed getter。
- `ShapeSelector` 和 QL predicate/order/cardinality。
- `select_edges_by_tag`、`select_faces_by_tag`。
- `make_select_rvertex/redge/rwire/rface/rsolid` graph node。
- `geo_selector` 几何 fingerprint。
- `TopoRef`、legacy enumeration index 和 selector hint fallback。
- feature params 中的 `selected_edge_node_ids`、`selected_face_node_ids`、indices 和 refs。

这些机制目前没有统一的一等数据模型，造成以下问题：

- QL query 经常在 record time 被 resolve，然后降级为 geometry-only selection node，原始 semantic intent 丢失。
- `TopoRef.topo_id` 是 implementation-defined，不适合作为 durable topology naming。
- Python replay 和 FreeCAD translator 使用不同的 geo scoring、阈值和 normal 方向规则。
- 对称或重复几何中的同分候选不会可靠地报告歧义。
- selection node、query、projection、cardinality 和 fallback strategy 混在同一组 params 中。
- backend 很难声明自己支持哪些 query predicate 和 traversal relation。

因此，下一代查询系统不能继续在当前 `ql.py` 上零散增加 helper。需要先定义稳定的 Query IR、类型系统和执行语义。

## 3. 设计决策

### 3.1 决策一：Canonical contract 是 Query IR，不是文本语法

Canonical operation graph 中保存 JSON Query IR，不保存 Python callable，也不把 GraphQL 字符串作为唯一事实来源。

原因：

- JSON IR 更容易做 schema migration 和 strict validation。
- translator 不需要嵌入 GraphQL parser。
- Python builder、GraphQL-like text、GUI 和 LLM 可共享同一个执行器。
- Query IR 可以精确表示 typed graph pattern、单位、容差和 cardinality。

### 3.2 决策二：GraphQL-like syntax 是推荐文本前端

借鉴 GraphQL：

- 类型化 schema。
- 字段和 input object。
- variables。
- fragments。
- validation before execution。
- result projection。
- structured diagnostics。

不照搬 GraphQL：

- 不使用 GraphQL resolver 自由定义字段语义。
- 不使用 GraphQL null propagation 表示选择失败。
- 不依赖 GraphQL list 顺序。
- 不把 selection set 与 CAD entity match 混为一谈。
- 不把 mutation/subscription 引入 CADQL 1.0。

### 3.3 决策三：查询对象是 BRep Topology Graph

必须区分三种图：

| 图 | 职责 |
| --- | --- |
| Operation Graph | 描述模型如何构建，并提供 query scope 和 provenance。 |
| BRep Topology Graph | 描述当前 output 中 topology entities 及其 contains/boundary/incident/adjacent 关系。 |
| Topology Evolution Graph | 通过 EntityVersion/TopoUseVersion/Change 描述 preserved/modified/generated/deleted、split、merge 和 generation。 |

CADQL 在 Current BRep Graph 与 Topology Evolution Graph 的联合视图上执行，可以通过 provenance relation 连接 Operation Graph。

### 3.4 决策四：Query intent 是主身份，Evidence 是辅助信息

Query intent 描述用户为什么选择实体，例如：

```text
选择带 role.mounting_surface tag、surface type 为 plane、法向朝 +Z 的唯一 face
```

Evidence 描述某次执行如何得到结果，例如：

```text
匹配了 face_7；area=245；normal=[0,0,1]；唯一候选；resolver=ocp
```

Replay 必须先重新执行 Query intent。Evidence 用于 drift diagnosis 和显式 fallback，不是 primary selector。

### 3.5 决策五：违反唯一性默认失败

当 feature query 的 cardinality 要求唯一实体，而匹配结果不唯一时必须失败，不允许静默选择 BRep 列表中的第一个实体。多实体选择通过 `EXACTLY`、`AT_LEAST` 等 cardinality 正式声明。

### 3.6 决策六：查询定义与 graph binding 分离

Query IR 描述 traversal、predicate、ordering、cardinality 和 projection，不保存具体 operation node ID。查询作用域通过执行时 binding 提供：

- Python 中由 `cadql.select(cadql.Face, in_=body)` 的 `in_` 参数建立 runtime binding。
- Operation Graph 中由 query node 的 `scope` typed input port 建立 binding。
- 文本查询中由 variable 建立 binding。

因此，相同 Query IR 可以绑定到参数变化后重建的 operation output，`query_hash` 也不会因为 node ID 改变。持久化对象由 `query` 和 `bindings` 两部分组成。

### 3.7 决策七：Canonical query 是 typed graph pattern

很多实际选择不是“某条 edge 的长度或中心是多少”，而是“当前拓扑实体在空间结构和建模历史中扮演什么角色”。Boolean、fillet、chamfer、shell、cut 和 pattern 都会产生 split、merge、generated、modified 和 preserved entities，不能为每种 operation 发明一个 selection helper。

Canonical CADQL 因此采用统一的 typed graph pattern：

- typed variable 表示当前或历史 topology entity、oriented topology use、change 或 operation。
- topology relation 表示 contains、boundary、incident、adjacent 等当前空间结构。
- lineage relation 表示一个实体经过任意 operation 后如何 split、merge、modify、generate 或 preserve。
- provenance relation 表示 operation、input role 和 source binding。
- semantic predicate 表示用户或系统提供的稳定意图锚点。
- geometry predicate 只作为可选约束，不是统一 identity 模型的基础。

查询最终返回某个 typed variable 的去重集合。现有 `faces().where(...).order_by(...)` 属于 legacy `ql.py`，不是 CADQL 1.0 public syntax，也不是 canonical IR。

这一形式统一表达：

- box/cylinder union 后，位于两个来源 surface 交界上的 current edges。
- fillet/chamfer 后，由原 edge 分裂或生成、并与特定来源 faces 相邻的 current edges。
- 多次 feature 后，仍是某个 semantic source query 的 descendants 的 current faces。
- 不知道具体 curve/surface class 时，仅依赖 topology role 和 lineage 的选择。

CADQL 不能在完全没有 semantic tag、source query、spatial relation、lineage 或 geometry distinction 时区分数学上对称且可交换的实体。此时正确结果是集合或 `AmbiguousSelectionError`，而不是伪造稳定身份。

### 3.8 决策八：Public API 只有一种 query 形态

CADQL 不提供 `from_shape`、`anchor`、`on`、`SurfaceContext` 等相互重叠的 query 入口。所有选择都从同一个构造器开始：

```python
cadql.select(ResultType, in_=scope)
```

其中 public `scope` 可以是 Shape、operation output 或另一个 `SelectionQuery[T]`。已经 resolved 的 `SelectionSet[T]` 不作为 public `in_` 参数；Operation Graph 内部会把 referenced query 的 output 作为 typed binding 连接到下游 query node。所有 query 使用相同的操作并返回相同的结果形态：

```text
select -> where -> order_by/take -> expect -> SelectionQuery[T]
SelectionQuery[T].resolve() -> SelectionSet[T]
```

已有 query 不会被“提升”为另一种 Anchor 对象。它本身就是可持久化、可作为后续 relation source binding 的选择意图：

```python
mounting_face = (
    cadql.select(cadql.Face, in_=before_boolean)
    .where(cadql.tag("role.mounting_surface", scope="effective"))
    .expect_one()
)

current_faces = (
    cadql.select(cadql.Face, in_=after_boolean)
    .where(
        cadql.related(
            cadql.descends_from,
            from_=cadql.this,
            to=mounting_face,
            derivations=("continuation", "fragment"),
            depth=(1, 64),
        )
    )
    .expect_at_least(1)
)
```

局部 surface/UV 选择也不是另一套 context API。先选 current faces，再把该 query 作为普通 relation binding：

```python
outer_coedges = (
    cadql.select(cadql.Coedge, in_=after_boolean)
    .where(
        cadql.related(cadql.boundary_uses, from_=current_faces, to=cadql.this)
        & cadql.topology.loop_role.eq("outer")
    )
    .expect_at_least(1)
)
```

`FaceFamily` 只是 `SelectionSet[Face]`，`WorkPlaneContext` 只是绑定到单一 planar chart 的 query validation 状态，二者都不是 public object kind。一个历史 face resolve 为多个 current fragments 时，结果自然是多个 Face；初始 `.expect_one()` 与后续 `.expect_at_least(1)` 是两个独立 query 的 cardinality contract。

### 3.9 决策九：先定义不可约的选择 case

表面上不同的 CAD 选择应先归约到最少的正交能力。CADQL 只有六种不可互相替代的 match case：

| Case | 唯一新增能力 | 代表问题 |
| --- | --- | --- |
| 类型全集 | 只给出 result type 和 scope | 选择 body 中所有 Face。 |
| 属性约束 | 对 candidate property 求 predicate | 选择带 tag、面积大于阈值或法向朝上的 Face。 |
| Current topology relation/path | 匹配 snapshot 中的 typed relation 或其有界/传递闭包 | 选择 face boundary Edge、两个 faces 的共享 Edge 或相切 edge chain。 |
| Oriented occurrence | 返回 TopoUse，而不是 underlying entity | 选择 face outer loop 的正向 Coedge 或 seam 的某次 use。 |
| Evolution relation | 沿 Change graph 匹配历史关系 | 选择原 edge split 后的 current fragments。 |
| Multi-source Change pattern | 同时约束一个 Change 的多个 input/output | 选择 box/cylinder 两个 source surfaces 共同生成的交界 edges。 |

以下不是新的 match case：

- Semantic、geometry、local UV 和相对空间条件都是属性约束，只是 property namespace 不同。
- Face、Edge、Vertex 只是 result type 不同。
- Boolean、fillet、chamfer 只是 Change producer 不同。
- Union、intersection、difference 是集合代数。
- Ordering、take、group 和 cardinality 是结果代数。
- 保存、命名和 graph binding 是 query 生命周期，不改变 match 语义。

任何新增 public helper 都必须证明自己能表达一个现有六类无法表达的 case；否则只能是 lowering 到这些原语的非 canonical convenience syntax，并且不进入 1.0 public contract。

### 3.10 典型选择 case corpus

下面每行具有不同的最小表达式或数据需求；同一行中的 operation 名称和 topology type 变化不产生新 case。

| # | 典型需求 | 唯一归约 | 需要的数据 |
| --- | --- | --- | --- |
| 1 | 选择 scope 中全部 Face | 类型全集 | Current BRep containment。 |
| 2 | 选择带 mounting tag 的 Face | 属性约束：semantic | Semantic binding。 |
| 3 | 选择半径约等于 5 mm 的圆 Edge | 属性约束：intrinsic geometry | Geometry properties、unit、tolerance。 |
| 4 | 选择平行于 datum plane 的 Face | 属性约束：relative geometry | Reference binding、frame。 |
| 5 | 选择已选 Face 包含的 Edge | Query scope containment | Current BRep containment。 |
| 6 | 选择两个 Face 的共享 Edge | Current relation | `incident_faces`。 |
| 7 | 选择与 seed Face 相邻的 Face | Current relation | `adjacent_faces`。 |
| 8 | 选择与 seed 连通且保持相切的 Edge chain | Current relation path | `adjacent_edges`、step predicate、depth bound。 |
| 9 | 选择 Face outer loop 中的 Edge occurrences | Oriented occurrence + property | `boundary_uses`、`loop_role`。 |
| 10 | 区分 periodic Face 上同一 seam Edge 的两次使用 | Oriented occurrence | TopoUse occurrence identity。 |
| 11 | 选择 planar Face 局部坐标最右侧的 Coedge | Oriented occurrence + local property | SurfaceChart、stable frame。 |
| 12 | 选择 source Edge split 后的 current fragments | Evolution relation | `descends_from`、`FRAGMENT` evidence。 |
| 13 | 选择由 source Face 生成的新 boundary Edge | Evolution relation | `generated_from`、`BOUNDARY` evidence。 |
| 14 | 选择与某 transition Face 同一 Change 的 Edge | Evolution relation | `co_result_of` witness。 |
| 15 | 选择同时由 box/cylinder sources 生成的 interface Edge | Explicit Change pattern | 多 input role、`INTERSECTION` output。 |
| 16 | Source Face 已消失时选择消费它的 Change outputs | Explicit Change pattern | Historical input 和 generated outputs。 |
| 17 | 选择满足 A 或 B、同时排除 C 的 Edge | Set algebra | Union/difference 和 entity identity。 |
| 18 | 从多个候选中选择最高且唯一的 Face | Result ordering | Business order、tie error、take、cardinality。 |
| 19 | 每个 hole loop 选择最长且唯一的 Edge | Correlated partition | Loop identity、per-partition order/cardinality。 |
| 20 | 数学上完全对称且无区分依据的实体 | Cardinality/ambiguity | 返回集合，或唯一性要求下失败。 |

覆盖规则：

- Case 2、3、4 的求值数据不同，但语法和结果行为完全相同，都是 `.where(property_predicate)`。
- Case 6、7、8 的 relation 不同，但语法和结果行为完全相同，都是 `.where(related(...))`。
- Case 12、13、14 的 evolution relation 不同，但仍使用同一个 `related(...)` constructor。
- Case 15、16 都需要显式匹配一个 n-ary Change；input 数量不是新的语言机制。
- Case 17、18、19、20 不增加 candidate identity 机制，只处理已匹配集合。
- Face/Edge/Vertex/Wire/Solid 的替换不产生新 case；它只触发 relation/property type validation。

## 4. 术语

| 术语 | 定义 |
| --- | --- |
| Scope | 查询开始的 operation output 或已有 topology entity set；scope binding 不属于 Query IR identity。 |
| Match | 根据 predicate 选择 topology entities。 |
| Traversal | 沿强类型 topology/lineage relation 移动。 |
| Predicate | 对 geometry、topology、semantic 或 provenance property 的条件。 |
| Projection | 查询结果需要返回的字段，不决定选中哪些实体。 |
| Cardinality | 对匹配结果数量的正式约束。 |
| Ambiguity | 多个候选都满足 identity 或 fingerprint，无法唯一判定。 |
| Evidence | 某次执行的匹配属性、候选数、path witness 和 selected refs。 |
| SelectionQuery | 未执行的 typed Query IR 及其 runtime bindings；可以作为另一个 query 的 source。 |
| SelectionSet | 某个 Query IR 的强类型结果集合。 |

## 5. 类型系统

### 5.1 Topology 类型

目标类型层次：

```text
TopoEntity
├── Compound
├── CompSolid
├── Solid
├── Shell
├── Face
├── Wire
├── Edge
└── Vertex

QueryContext
├── SurfaceChart
└── FrameRef

TopoUse[T]
├── FaceUse
├── WireUse
├── Coedge        oriented use of Edge in a face boundary
└── VertexUse
```

CADQL 1.0 的内部 BRep graph 必须完整表示：

```text
Compound
CompSolid
Solid
Shell
Face
Wire
Edge
Vertex
TopoUse
SurfaceChart
```

Public query return type 1.0 至少支持 Solid/Face/Wire/Edge/Vertex 和 Coedge。Coedge 是 `TopoUse[Edge]` 的公开类型名，不是新的 BRep entity。Shell/Compound/CompSolid 及其他 TopoUse 可以参与 pattern，并在 provider capability 声明后作为返回类型。SDK 当前 `TopoKind` 已有 Compound，但缺少 Shell/CompSolid；canonical selection operations 也缺少 Compound/Shell/CompSolid。Phase 1 必须补齐 IR type enum，Phase 4 再补齐 public graph outputs。

### 5.2 Property namespace

属性必须按 namespace 分类，禁止把所有属性放入未定义语义的 dict。

#### Topology properties

```text
topology.kind
topology.closed
topology.edge_count
topology.wire_count
topology.inner_wire_count
topology.incident_face_count
topology.adjacent_face_count
topology.loop_role
topology.loop_identity
```

#### Geometry properties

```text
geometry.length
geometry.area
geometry.volume
geometry.center
geometry.center.x
geometry.center.y
geometry.center.z
geometry.bbox
geometry.normal
geometry.tangent
geometry.curvature
geometry.radius
geometry.curve_type
geometry.surface_type
```

#### Semantic properties

```text
semantic.tags
semantic.metadata.<namespace>.<key>
semantic.role
semantic.group
semantic.material
```

#### Provenance properties

```text
provenance.produced_by
provenance.operation_type
provenance.origin_role
provenance.source_node
```

#### Spatial/reference properties

```text
geometry.axis.origin
geometry.axis.direction
geometry.location
geometry.support_curve_type
geometry.support_surface_type
geometry.parameter_span
geometry.sweep_angle
```

这些 property 仅对适用的 entity kind 可用。例如 `geometry.axis` 可用于 cylinder/cone surface 和 circle/ellipse curve；`geometry.sweep_angle` 只适用于具有规范角参数的 trimmed conic。Property registry 必须声明适用类型，不能在不适用时返回任意默认值。

#### Local/chart properties

```text
local.u
local.v
local.u_range.min
local.u_range.max
local.v_range.min
local.v_range.max
local.winding
local.orientation
```

`local.u/v` 具有 length 或 dimensionless 参数单位，由 SurfaceChart schema 声明；不能在 query 中混合比较不同单位。`local.winding/orientation` 只适用于 Coedge/WireUse，其他 local property 的适用类型由 registry 静态验证。任何 predicate、ordering、partition 或 projection 对 `local.*` property 的引用都必须携带明确的 chart binding。Chart identity 通过 `surface_chart/use_chart` relation 表达，不再提供会自引用 chart binding 的 `local.chart_id` property。Loop role 和 identity 是纯拓扑事实，使用不依赖 chart 的 `topology.loop_role/loop_identity`。

### 5.3 Property capability

每个 backend/evaluator 必须声明 property capability：

```json
{
  "geometry.area": "supported",
  "geometry.curvature": "unsupported",
  "topology.loop_role": "supported"
}
```

Query validation 在执行前检查所有 property 和 relation。Unsupported property 必须产生 `UnsupportedQueryCapabilityError`，不能被当作 false predicate。

## 6. Typed Traversal Relations

CADQL relation 是有限枚举，并具有 source/target 类型约束。

### 6.1 Topology relations

| Relation | Source | Target | 语义 |
| --- | --- | --- | --- |
| `contains_direct` | Compound/CompSolid/Solid/Shell/Face/Wire | next lower entity | 只表示直接 BRep containment。 |
| `contains` | TopoEntity | lower-dimensional entity | `contains_direct` 的有界传递 path，必须指定 target type。 |
| `incident_faces` | Edge | Face | 共享该 edge 的 faces。 |
| `adjacent_faces` | Face | Face | 通过 edge adjacency 相邻。 |
| `adjacent_edges` | Edge | Edge | 共享 vertex 的 edges；可用 step predicate 进一步要求 tangent continuity。 |
| `boundary_uses` | Face/Wire | Coedge | Face 或 wire boundary 中有方向的 Edge occurrences。 |
| `use_entity` | TopoUse[T] | T | Occurrence 引用的同类型 underlying entity，例如 Coedge -> Edge。 |
| `use_parent` | TopoUse | TopoEntity | Occurrence 所属 parent entity。 |
| `use_chart` | TopoUse | SurfaceChart | Occurrence 所属 face chart。 |
| `surface_chart` | Face | SurfaceChart | Face query 绑定的 surface chart。 |
| `next_coedge` | Coedge | Coedge | 同一 WireUse 中按 orientation 的下一个 occurrence。 |
| `previous_coedge` | Coedge | Coedge | 同一 WireUse 中按 orientation 的上一个 occurrence。 |
| `mate_coedge` | Coedge | Coedge | 邻接 FaceUse 上引用同一 underlying Edge 的 occurrence。 |
| `starts_at` | Coedge | VertexUse | Coedge 在 parent orientation 下的起始 VertexUse。 |
| `ends_at` | Coedge | VertexUse | Coedge 在 parent orientation 下的结束 VertexUse。 |
| `belongs_to_loop` | Coedge | WireUse | Coedge 所属的 boundary loop occurrence。 |

`boundary_uses(Face/Wire, Coedge)` 是 `FaceUse -> WireUse -> Coedge` occurrence chain 的规范投影。它保留每个 parent occurrence，不按 underlying Edge 去重；因此 seam Edge 在同一 Face 中仍返回两个 Coedges。需要显式遍历中间 occurrence 时使用 `use_parent`/`belongs_to_loop`，不增加另一套 `coedges` relation。

### 6.2 Lineage relations

Lineage 不能只是一组从 child 指向 parent 的模糊 ref。Canonical Topology Evolution Graph 使用四类 node：

```text
EntityVersion   某个 operation output snapshot 中的 topology entity
TopoUseVersion  某个 snapshot 中带 parent/orientation/occurrence 的 topology use
Change          一次 operation 内的一项 topology evolution event
Operation       Operation Graph 中的建模 operation
```

基本关系：

```text
EntityVersion -[INPUT_TO {input_port, role}]-> Change
Change -[OUTPUT {event, derivation}]-> EntityVersion
TopoUseVersion -[USE_INPUT_TO {input_port, role}]-> Change
Change -[USE_OUTPUT {event, derivation, order_interval}]-> TopoUseVersion
TopoUseVersion -[USE_ENTITY]-> EntityVersion
TopoUseVersion -[USE_PARENT]-> EntityVersion
Change -[PERFORMED_BY]-> Operation
EntityVersion -[MEMBER_OF]-> Snapshot
```

`event` 沿用宏观结果分类：

```text
PRESERVED
MODIFIED
GENERATED
DELETED
```

`derivation` 使用与具体 feature 名称无关的演化分类：

| Derivation | 含义 |
| --- | --- |
| `CONTINUATION` | 同一拓扑角色继续存在，可能参数或位置改变。 |
| `FRAGMENT` | 一个 parent 被 split/trim 后产生同维度片段。 |
| `MERGE` | 多个同维度 parents 合并为一个 output。 |
| `INTERSECTION` | 由两个或多个 support entities 的相交生成。 |
| `BOUNDARY` | 由高一维结果或修改区域产生的新 boundary。 |
| `REPLACEMENT` | 旧实体被新的同角色实体替换，但不是可证明的 fragment。 |
| `UNKNOWN` | Backend 只知道 parent/child，无法给出更强分类。 |

例如原 edge 经 chamfer/fillet 后被分裂，新的同维 edge 使用 `FRAGMENT`；feature 新建的过渡面 boundary edge 使用 `BOUNDARY`；boolean 两个 surface 的交线使用 `INTERSECTION`。这些分类描述 BRep 演化事实，不编码 `fillet`、`chamfer` 或 `union` 名称。

一个 Change 可以有多个 input 和 output，因此能自然表示 split 和 merge，不需要伪造一对一 durable topology ID。`order_interval` 是可选的 source-use 参数区间；只有 backend 能证明 occurrence ancestry 和 orientation 时才记录。Lineage relation 只能在 model graph 提供相应 change evidence 时使用；缺少 evidence 不能退化成几何猜测。

### 6.3 Relation quantifiers

Predicate 可以对子关系做 `exists`、`all` 和 `count`：

```json
{
  "relation": "incident_faces",
  "from": "edge",
  "to": "source_face",
  "relation_quantifier": {"kind": "at_least", "value": 1}
}
```

`source_face` 必须是已声明 variable；其 `descends_from` source binding 由同一个 `and` pattern 中的独立 path constraint 表达。

Count 形式：

```json
{
  "relation": "incident_faces",
  "relation_quantifier": "count",
  "where": {"property": "geometry.surface_type", "eq": "plane"},
  "cardinality": {"kind": "exactly", "value": 1}
}
```

Quantifier 的 `where` 在 relation target type 上静态验证。`all` 对空 relation 返回 false，避免 vacuous truth 导致意外匹配。

Python `related(...)` 的 `from_`/`to` endpoint 可以绑定单个 variable 或 `SelectionQuery[T]`。Python 可以省略默认 endpoint quantifier；normalized IR 必须显式携带它：

```text
ANY_MEMBER    至少与 binding 中一个 member 满足 relation；默认值。
ALL_MEMBERS   与 binding 中每个 member 满足 relation；空 binding 返回 false。
EXACTLY(n)    恰好与 n 个 members 满足 relation。
AT_LEAST(n)   至少与 n 个 members 满足 relation。
AT_MOST(n)    至多与 n 个 members 满足 relation。
```

默认值永远是 `ANY_MEMBER`，不随 relation 名称、方向或 endpoint cardinality 改变。Python 省略默认值与显式写 `from_quantifier="any_member"`/`to_quantifier="any_member"` 完全等价；Canonical IR 总是显式保存 normalized quantifier。

### 6.4 Relation validation

以下是合法 traversal：

```text
Solid -> contains_direct -> Shell
Face -> contains_direct -> Wire
Wire -> contains_direct -> Edge
Edge -> contains_direct -> Vertex
Face -> adjacent_faces -> Face
```

以下必须在 validation 阶段失败：

```text
Vertex -> contains_direct -> Face
Edge -> boundary_uses
Solid -> incident_faces
```

### 6.5 BRep graph snapshot construction

Provider 对每个 scope output 构建一个只读 BRep graph snapshot：

1. Scope root 本身是 graph node，不只索引它的 children。
2. 每个拓扑实体以 `(kind, entity_token)` 在该 snapshot 内去重。
3. `contains_direct` 保存 direct containment edge；`contains` 是它的 typed path projection，不重复存边。
4. `boundary_uses` 连接 parent 和有方向 occurrence，`use_entity` 再连接 underlying entity；`incident` 和 `adjacent` 从共享 underlying boundary entity 推导。
5. Face adjacency 默认是共享 Edge；仅共享 Vertex 不算 face adjacency。
6. Seam edge 在同一 face 中可能出现两次，但 entity graph node 只有一个；需要 occurrence 信息的查询使用 `TopoUse/Coedge`，不假装 Edge entity 能表达方向不同的两次使用。
7. Snapshot identity 只在一次 scope evaluation 内有效。跨 replay identity 由 Query intent 和 Evidence 处理，不持久化 `entity_token`。

`related(...)` traversal 对 entity set 逐个展开、合并并按 entity identity 去重。需要保留多条 path multiplicity 的 path query 不属于 CADQL 1.0。

### 6.6 Generic feature-evolution semantics

CADQL 不定义 boolean、fillet 或 chamfer 专用 relation。Provider 将每次 operation 的 topology history 规范化为 Change graph：

```text
input EntityVersion(s) -> Change -> output EntityVersion(s)
```

Input edge 必须带 role：

```text
subject    被延续、切分或替换的实体
target     用户明确选中并驱动 feature 的实体
support    决定新实体位置或边界的支撑实体
tool       boolean/tool operand 中的实体
context    参与 change，但没有更强可证明角色的实体
```

Output edge 必须带 `event` 和 `derivation`。由此可统一表达：

- Boolean 交界 edge：同一个 Change 有来自两个 operands 的 support/tool inputs，output derivation 为 `INTERSECTION`。
- 原 edge 被 split：原 edge 是 subject/target input，多个 current edges 是 `FRAGMENT` outputs。
- Fillet/chamfer 新 boundary edges：原 target edge 和 adjacent support faces 是 inputs，新 edges 是 `BOUNDARY` outputs。
- 原 face 被 trim：原 face 是 subject input，current face 是 `FRAGMENT` 或 `CONTINUATION` output。
- 多次 feature 后追踪：沿 Change graph 对 `descends_from` 或更宽的 `depends_on` 做传递 path match。

规范 evolution relation 只有以下五个；没有 `fragments_of`、`generated_by`、`intersects_sources` 等 aliases：

| Relation | Source | Target | Depth | 含义 |
| --- | --- | --- | --- | --- |
| `descends_from` | current Entity/TopoUse | bound historical same-kind Entity/TopoUse | 1..n | Source 是 target 的 continuation/fragment/merge/replacement descendant。 |
| `generated_from` | current Entity/TopoUse | bound historical Entity/TopoUse | 1..n | Source 由 target 参与 intersection/boundary generation。 |
| `depends_on` | current Entity/TopoUse | bound historical Entity/TopoUse | 1..n | Source 的 causal Change path 中包含 target，不保证同维度或材料连续性。 |
| `co_result_of` | current Entity/TopoUse | current Entity/TopoUse | 1 | 两者是同一个 Change 的 outputs。 |
| `changed_with` | current Entity/TopoUse | bound historical Entity/TopoUse | 1 | Source 的 Change 同时消费 target。 |

CADQL 1.0 不提供 `interface_between(a, b)`、`descendants_of(a)` 等同义 helper。它们分别使用 `change(...)` 和 `related(...)` 表达，避免同一 graph constraint 出现第二种 public 写法。

如果 backend 没有完整 Change input/output evidence，相关 pattern 产生 `UnsupportedQueryCapabilityError`，不能退化为“找最接近的 curve”。

对 box/cylinder union 场景，不应先假定交界 edge 是 circle。Cylinder 与 oblique box plane 的支撑交线通常为 ellipse/conic，trim 后只是其中一段。CADQL 应先按两个来源 bindings 共同参与的 `INTERSECTION` Change 选择 current edges；curve type、sweep angle 或 length 只是可选的二次约束。

### 6.7 Entity 和 oriented use

BRep 中同一个底层 entity 可以在不同 parent 中以不同 orientation 出现。Canonical graph 区分：

```text
TopoEntityVersion   snapshot 内未定向的拓扑实体
TopoUse             entity 在某个 parent boundary 中的一次有方向 occurrence
```

`contains`、`incident_faces` 等 entity-level relation 用于大多数 selection；`boundary_uses`、`next_coedge`、`starts_at` 和 `ends_at` 用于依赖方向或 seam occurrence 的 query。`TopoEntityVersion` 可按 kernel `IsSame` 语义去重，`TopoUse` identity 则包含 parent、orientation 和 occurrence ordinal。

Normal、tangent、edge endpoint order 等 oriented property 必须在 `TopoUse` 上求值，或显式指定相对哪个 parent 求 oriented view。不能在去除 orientation 的 entity 上声称存在唯一方向。

### 6.8 Query composition 和 relation direction

`select(T, in_=scope)` 始终只做两件事：建立 candidate universe，并声明 result type。它不隐式进入 history、不自动加入邻面，也不根据调用链切换语义。

`in_` 只绑定 candidate domain，不 lower 为 graph relation：

- Shape 或 operation output：candidate domain 是该 current snapshot。
- `SelectionQuery[P]`：candidate domain 是其 resolved `SelectionSet[P]` 覆盖的 current subgraphs。
- 请求 `TopoEntity` 类型时，subgraph 包含 scope root 本身和沿 `contains_direct` 可达的 descendants。
- 请求 `Coedge` 时，subgraph 包含 scope 中 Face/Wire 的 `boundary_uses` targets。
- 所有 candidate 合并后按 entity/use identity 去重。
- 若目标不是 candidate-domain membership，而是 incident、adjacent、use/entity 或 history 关系，必须写入 `.where(...)`。

Candidate-domain membership 是 evaluator seed 规则，不属于 `related(...)` registry，也不进入 query identity。Query identity 保存 result type；binding identity 保存具体 scope。这样 `select(Solid, in_=solid)` 可以选择 root，`select(Coedge, in_=body)` 也不需要伪造 `contains(body, coedge)`。

所有 graph relation 使用同一个 predicate constructor：

```python
cadql.related(relation, from_=source, to=cadql.this)
cadql.related(relation, from_=cadql.this, to=target)
```

`cadql.this` 表示当前被测试的 candidate。Relation schema 静态检查 source/target type，因此 relation direction 不靠方法名猜测。一个 `related(...)` predicate 最多允许一个 endpoint 是 `SelectionQuery[T]`，另一个必须是 `cadql.this` 或局部 scalar variable。Set endpoint 默认量词始终是 `ANY_MEMBER`；需要其他行为时按 endpoint 方向使用 `from_quantifier=` 或 `to_quantifier=`。Relation target 自身的 exists/count 语义使用独立的 `relation_quantifier` IR field，不复用 endpoint quantifier 名称。

示例：

```python
# Face -> boundary_uses -> Coedge
coedges = (
    cadql.select(cadql.Coedge, in_=body)
    .where(cadql.related(cadql.boundary_uses, from_=faces, to=cadql.this))
)

# Coedge -> use_entity -> Edge
edges = (
    cadql.select(cadql.Edge, in_=body)
    .where(cadql.related(cadql.use_entity, from_=coedges, to=cadql.this))
)

# Edge -> incident_faces -> Face
shared_edges = (
    cadql.select(cadql.Edge, in_=body)
    .where(
        cadql.related(cadql.incident_faces, from_=cadql.this, to=face_a)
        & cadql.related(cadql.incident_faces, from_=cadql.this, to=face_b)
    )
)
```

Python `cadql.related(...)` 可以省略 `depth`，唯一默认值是 `depth=1`；normalized IR 必须显式保存该值。有界或传递 traversal 使用同一个 constructor，并提供 `depth=(min, max)`。Normalize 阶段把默认/显式 `depth=1` lower 为相同 canonical `relation` constraint，把范围 lower 为 canonical `path` constraint。

Path 的 `step_where` 是可选的 pairwise predicate，显式绑定 `cadql.step.from_`、`cadql.step.to` 和 relation witness。例如 `adjacent_edges` witness 是共享 Vertex：

```python
cadql.related(
    cadql.adjacent_edges,
    from_=seed_edges,
    to=cadql.this,
    depth=(0, 64),
    step_where=cadql.step.tangent_continuous(
        angle_tolerance=cadql.deg(0.1),
    ),
)
```

普通 `where=` 只允许 target-local predicate，不能表达 pairwise tangency。Provider 不支持 relation witness 或 oriented tangent 时必须报告 capability error。

Canonical path IR 保存同一信息：

```json
{
  "path": {
    "from": "seed_edge",
    "relation": "adjacent_edges",
    "to": "result",
    "min_depth": 0,
    "max_depth": 64,
    "from_quantifier": "any_member",
    "step_where": {
      "predicate": "tangent_continuous",
      "relative_to": "relation_witness",
      "angle_tolerance": {"value": 0.1, "unit": "deg"}
    }
  }
}
```

`tangent_continuous` 只适用于 `adjacent_edges` path。`relative_to: relation_witness` 表示在共享 Vertex occurrence 处比较进入/离开 tangent，因此满足 oriented-property 的显式 context 要求。

### 6.9 Local 2D topology naming

局部 surface 选择的稳定性主要来自 query-selected Face 与其局部拓扑结构，而不是 UV 数值。每个 face chart 暴露：

```text
FaceUse
  -> outer/inner WireUse
  -> ordered cyclic Coedge sequence
  -> start/end VertexUse
  -> mate Coedge on neighboring FaceUse
```

Outer/inner 是 `topology.loop_role` property，不是第二套 relation。局部 traversal 只使用 6.1 已注册的 `next_coedge`、`previous_coedge`、`mate_coedge`、`starts_at`、`ends_at` 和 `belongs_to_loop`。

当原 boundary edge 被 split 时，Topology Evolution Graph 必须把 current coedge fragments 映射到 source coedge query，并保留在 source orientation 下的有序覆盖：

```text
source CoedgeUse
  -> fragment 0
  -> fragment 1
  -> fragment 2
```

该顺序来自 `TopoUseVersion USE_OUTPUT.order_interval`，不是 current backend edge enumeration。若 provider 只能证明 underlying edge fragments 属于同一 source query、无法证明 use ancestry/orientation/order，则仍可返回无序 fragment set，但任何 `next_coedge` 或 ordered-range query 必须产生 `UnsupportedQueryCapabilityError`。

常见无具体几何 query：

```text
selected face 的 outer loop edges
selected face 某个有稳定区分依据的 inner loop current descendants
selected coedge 被 split 后的全部 current fragments
与 selected face 相邻、且由同一个 Change 新生成的 faces
selected face boundary 上由 tool source 参与生成的 edges
```

“第 2 个 inner loop”只有在 loop 本身有 semantic tag 或稳定 ordering key 时才可持久化。Raw current loop enumeration 仍不是 durable identity。

### 6.10 Surface chart 只是显式 predicate binding

CADQL 不创建 SurfaceContext/WorkPlaneContext 对象。Local property 必须通过 `in_chart=` 显式绑定到一个 Face query：

```python
right_side = (
    cadql.select(cadql.Coedge, in_=body)
    .where(
        cadql.related(cadql.boundary_uses, from_=mounting_face, to=cadql.this)
        & cadql.local.u.approximately(
            cadql.local.u_range.max,
            in_chart=mounting_face,
        )
    )
    .expect_one()
)
```

规则：

- `mounting_face` 必须静态为 `SelectionQuery[Face]`。
- 若 local predicate 需要单一 chart，binding query 必须具有 `ONE` cardinality。
- 多个 faces 可按 chart 分组后分别执行 local predicate，但不同 chart 的 UV 不得直接比较或全局排序。
- Planar frame 来自 source Face query 的 operation/frame binding，不从 current trimmed bbox 重新猜测。
- Chart 只沿可证明的 `CONTINUATION`/`FRAGMENT` use history 继承。`MERGE`/`REPLACEMENT` 默认不继承，必须用新的 Face query 和显式 frame 重新定义 local predicate。

邻接和 Change neighborhood 不再是 context expansion mode。它们分别写成 `related(incident_faces, ...)`、`related(evolution_relation, ...)` 或 multi-source `change(...)` constraints。因此候选范围不会因一个隐式 expansion 改变。

## 7. Predicate Algebra

### 7.1 Boolean predicates

```text
{"and": [<predicate>, <predicate>]}
{"or": [<predicate>, <predicate>]}
{"not": <predicate>}
```

空 `and`、空 `or` 在 strict mode 下非法，避免产生不直观的全选或空选。

### 7.2 Scalar comparison

```text
eq
ne
lt
lte
gt
gte
between
approximately
```

浮点 property 禁止默认 exact equality。对 length/area/volume/radius 使用 `approximately` 或范围谓词。

### 7.3 Vector and direction predicates

```text
parallel_to
same_direction_as
opposite_direction_to
perpendicular_to
angle_to
```

语义定义：

- `parallel_to` 允许同向和反向。
- `same_direction_as` 只允许同向。
- `opposite_direction_to` 只允许反向。
- 所有方向 predicate 必须指定或继承 angle tolerance。
- curved face 的 normal 查询必须指定 sampling policy；CADQL 1.0 默认仅允许 planar face 的 stable normal predicate。

### 7.4 String和enum predicates

```text
eq
ne
in
exists
```

`geometry.surface_type`、`geometry.curve_type` 使用 enum，不使用 backend-specific Python class name。

### 7.5 Tag predicates

Tag 查询格式：

```json
{
  "property": "semantic.tags",
  "tag": {
    "scope": "effective",
    "op": "eq",
    "value": "role.mounting_surface"
  }
}
```

Tag scope：

| Scope | 含义 |
| --- | --- |
| `local` | 直接挂在 entity 上。 |
| `inherited` | 从 topology parent 或 model entity 传播。 |
| `effective` | local 与 inherited 的并集。 |
| `lineage` | 从 topology lineage ancestor 传播。 |

Python `cadql.tag(value, scope="effective")` 的默认 scope 是 `effective`，builder normalization 始终把默认值显式写入 IR。其他 scope 必须显式传参。

当前 SDK 仅保存扁平化 `_tags: set[str]`，传播后无法判断一个 tag 是 local 还是 inherited。因此迁移前只有 `effective` 可被可靠执行；请求 `local`、`inherited` 或 `lineage` 必须得到 `UnsupportedQueryCapabilityError`，不能把 effective tags 冒充为其他 scope。

Phase 4 必须增加保留来源的 canonical tag binding：

```json
{
  "tag": "role.mounting_surface",
  "assignment_node": "node_tag_mounting_surface",
  "scope_binding": "body",
  "target": {
    "kind": "selection_query",
    "query_hash": "sha256:...",
    "binding_hash": "sha256:..."
  },
  "attachment": "local",
  "propagation": "downward"
}
```

`effective` 是 local bindings 与适用 inherited bindings 的计算结果，不再通过复制字符串丢失来源。Lineage tags 根据 tag bindings 和 Topology Evolution Graph 在 query-time 计算。

匹配模式：

```text
eq
in
prefix
pattern
exists
```

`pattern` 只支持 dot-token wildcard，例如 `role.*` 和 `anchor.datum.*`。CADQL 1.0 不支持任意 regex。

### 7.6 Metadata predicates

Metadata 查询必须指定 namespace：

```json
{
  "property": "semantic.metadata.manufacturing.finish",
  "eq": "ground"
}
```

未指定 namespace 的自由 key 查询在 strict mode 下非法。

## 8. Units 和 Tolerance

### 8.1 Quantity

所有有量纲 value 使用：

```json
{
  "value": 100.0,
  "unit": "mm2"
}
```

CADQL 1.0 基础单位：

```text
length: mm, cm, m, in
area: mm2, cm2, m2, in2
volume: mm3, cm3, m3, in3
angle: deg, rad
```

Query IR 规范化阶段转换为 canonical units：

```text
length -> mm
area -> mm2
volume -> mm3
angle -> rad
```

### 8.2 Tolerance

QueryOptions 提供默认 tolerance profile：

```json
{
  "linear_abs": {"value": 1e-6, "unit": "mm"},
  "linear_rel": 1e-9,
  "angular_abs": {"value": 1e-6, "unit": "rad"},
  "area_abs": {"value": 1e-9, "unit": "mm2"},
  "area_rel": 1e-8,
  "volume_abs": {"value": 1e-12, "unit": "mm3"},
  "volume_rel": 1e-8
}
```

Predicate 可以覆盖默认 tolerance。Scalar approximate equality 统一使用：

```text
abs(a - b) <= max(abs_tolerance, rel_tolerance * max(abs(a), abs(b)))
```

Ordering key 的业务同分也使用对应量纲的同一 tolerance，而不是 exact float equality。NaN、infinity 或 property unavailable 在 strict query 中产生 `PropertyUnavailableError`，不能参与排序。Backend 不能自行改变 tolerance 语义，只能声明数值能力低于请求精度并拒绝执行。

### 8.3 Coordinate frame

`geometry.center`、`geometry.bbox`、`geometry.normal`、`geometry.tangent` 以及 query 中的 point/vector 都必须在同一显式 frame 中解释。QueryOptions 默认使用 world frame：

```json
{
  "frame": {"kind": "world"}
}
```

可选 frame：

```text
world
operation_context
frame_ref
```

`operation_context` 使用 scope producer 记录的 coordinate-system snapshot；`frame_ref` 引用 model 的 Frame Graph。Provider 必须先把属性转换到 query frame 再求值。Face entity 本身没有唯一 oriented normal；normal/tangent predicate 必须通过 `relative_to=` 绑定 parent Solid/Shell shape、query 或明确的 FaceUse。Provider 在该 parent occurrence 中计算 oriented normal，再转换到 query frame。

## 9. Cardinality 和 Ordering

### 9.1 Cardinality

正式类型：

```text
ANY
ONE
OPTIONAL_ONE
EXACTLY(n)
AT_LEAST(n)
AT_MOST(n)
BETWEEN(min, max)
```

Feature selection 不允许使用隐式 `ANY`。例如 fillet 的 edge query 必须明确至少一条 edge，remove-face shell query 必须明确预期数量或范围。

Cardinality 只验证完整 pattern、order 和 take 求值后的结果，不执行排序、截断或“选最佳候选”。`.expect_one()` 对两个匹配实体必须失败，即使 query 存在 `order_by`。

Validation outcome：

| 条件 | Error |
| --- | --- |
| `actual == 0` 且 minimum 大于 0 | `NoMatchError` |
| `0 < actual < minimum` | `SelectionCardinalityError` |
| `actual > maximum` | `AmbiguousSelectionError` |
| top-N boundary 出现业务排序同分 | `AmbiguousSelectionError` |

### 9.2 Ordering

`take` 必须在 `order_by` 后使用。CADQL 1.0 不提供 `first`、`last`、`offset` 或 `selection_item(index)`；这些写法要么重复 `order_by(...).take(...)`，要么重新引入不稳定 index。

合法示例：

```json
{
  "order_by": [
    {"property": "geometry.center.z", "direction": "desc"},
    {"property": "geometry.center.x", "direction": "asc"},
    {"property": "geometry.area", "direction": "desc"}
  ]
}
```

禁止使用 backend topology enumeration index 作为默认稳定排序。内部可用 deterministic final tie-breaker，但如果业务排序键全部相同且 query 要求唯一项，必须报告 ambiguity。

`take` 只能在显式 `order_by` 后使用。它默认采用 `boundary_ties: error`：如果第 N 项与第 N+1 项的全部业务排序键相同，则产生 `AmbiguousSelectionError`。内部 entity token 只能保证 deterministic materialization，不能用来打破业务并列。

### 9.3 Set semantics 和 ambiguity

Query 的自然结果始终是去重集合。Cardinality 决定该集合是否可接受：

- `EXACTLY(4)` 返回四个实体是成功，不是 ambiguity。
- `ONE` 返回两个实体时是 `AmbiguousSelectionError`。
- `AT_LEAST(1)` 返回多个实体是成功。
- `take(1)` 在业务排序边界同分时是 `AmbiguousSelectionError`。

因此 CADQL 1.0 不增加独立的 `ALLOW_SET`/`ERROR` policy。`PICK_FIRST` 也不进入 canonical contract。Python 临时探索 API 可以提供显式 unsafe helper，但不得写入 canonical model graph。

### 9.4 Result algebra

Match 结束后，所有 query 共用同一结果代数：

```text
distinct
union / intersection / difference
order_by
take
expect
partition_by
order_each_by
take_each
expect_each_one / expect_each_exactly
```

规则：

- 集合运算两侧必须是兼容的 `SelectionQuery[T]`，结果仍是 `SelectionQuery[T]`。
- 去重依据是 current entity identity 或 TopoUse identity，不是 geometry fingerprint。
- `order_by` 只建立业务顺序；`take` 才缩小集合。
- `expect` 只验证最终集合，不选择候选。
- 每个 operation 执行后类型都不改变，resolve 后统一返回 `SelectionSet[T]`。

`group_by()` 不进入 CADQL 1.0 public API，因为它会引入第二种 public result shape。需要“每个 group 选择一个”的 case 使用 CADQL 1.0 correlated partition stage：

```python
longest_edge_per_hole = (
    cadql.select(cadql.Coedge, in_=mounting_face)
    .where(cadql.topology.loop_role.eq("inner"))
    .partition_by(cadql.topology.loop_identity)
    .order_each_by(cadql.length.desc())
    .take_each(1, boundary_ties="error")
    .expect_each_one()
)
```

该 query 的 resolved result 仍是扁平 `SelectionSet[Coedge]`；partition key 和每组 cardinality 进入 evidence。若 feature 消费 underlying Edge，再用一个普通 `select(Edge).where(related(use_entity, ...))` query。Partition stages 只改变内部求值方式，不产生 `SelectionGroup` public result。

## 10. Query IR 1.0

### 10.1 顶层结构

```json
{
  "schema_version": "1.0",
  "variables": {
    "result": {"type": "face", "domain": "current"}
  },
  "match": {
    "node": "result",
    "where": {
      "property": "semantic.tags",
      "tag": {
        "scope": "effective",
        "op": "eq",
        "value": "role.mounting_surface"
      }
    }
  },
  "return": "result",
  "cardinality": {"kind": "one"},
  "projection": ["ref"],
  "options": {
    "frame": {"kind": "world"}
  }
}
```

### 10.2 Variables 和 binding

Variable domain：

```text
current          当前 scope snapshot 中的 entity/use
history          scope 可达的历史 EntityVersion
change           Topology Evolution Graph 中的 Change
operation        Operation Graph node
bound_source     外部 binding 提供的 entity set 或 operation output
```

`current` domain 已经表示由 `scope` binding 建立的 candidate domain；IR 不再额外生成 `contains(scope, result)` constraint。`bound_source` variable 必须通过 `from_binding` 关联 named binding，relation/path endpoint 只引用已声明 variable，不直接引用 binding name。

Query IR 外部的 runtime binding：

```json
{
  "bindings": {
    "scope": {
      "kind": "operation_output",
      "node_id": "node_result",
      "output_slot": 0
    },
    "box_source": {
      "kind": "operation_output",
      "node_id": "node_box",
      "output_slot": 0
    },
    "cylinder_source": {
      "kind": "operation_output",
      "node_id": "node_cylinder",
      "output_slot": 0
    }
  }
}
```

Graph node 内使用 named input bindings，避免 query params 重复持有 node ID：

```json
{
  "bindings": {
    "scope": {"kind": "input", "port": "scope"},
    "box_source": {"kind": "input", "port": "box_source"},
    "cylinder_source": {"kind": "input", "port": "cylinder_source"}
  }
}
```

Binding source 可以是 Shape output、SelectionSet output 或 operation reference。后者用于 source operand、feature target 和 semantic source query。Binding 是 query execution identity 的一部分，但不进入 normalized pattern hash。

后续 binding 可增加：

```text
selection_output
assembly_component
product_part
explicit_entity_refs
semantic_query
```

Explicit refs 只能作为 legacy/evidence binding，不能被描述为重建出的 semantic intent。

### 10.3 Pattern constraints

Canonical constraints：

```text
node             variable 的 property/semantic predicate
relation         两个 variable 之间的一条 typed relation
path             两个 variable 之间有界或传递的 typed relation path
change           EntityVersion/Change/Operation 的 evolution pattern
and/or/not        组合 constraints
exists/count      局部 variable quantifier
```

Box/cylinder union 后选择交界 edges 的完整例子：

```json
{
  "schema_version": "1.0",
  "variables": {
    "edge": {"type": "edge", "domain": "current"},
    "change": {"type": "change", "domain": "change"},
    "box_face": {"type": "face", "domain": "bound_source", "from_binding": "box_source"},
    "cylinder_face": {"type": "face", "domain": "bound_source", "from_binding": "cylinder_source"},
    "box_current_face": {"type": "face", "domain": "current"},
    "cylinder_current_face": {"type": "face", "domain": "current"}
  },
  "match": {
    "and": [
      {
        "change": {
          "variable": "change",
          "inputs": [
            {
              "variable": "box_face",
              "input_port": "subjects",
              "role": "support",
              "endpoint_quantifier": "any_member"
            },
            {
              "variable": "cylinder_face",
              "input_port": "tools",
              "role": "tool",
              "endpoint_quantifier": "any_member"
            }
          ],
          "outputs": [
            {
              "variable": "edge",
              "derivation": ["intersection"]
            }
          ]
        }
      },
      {
        "relation": "incident_faces",
        "from": "edge",
        "to": "box_current_face",
        "relation_quantifier": {"kind": "at_least", "value": 1}
      },
      {
        "path": {
          "from": "box_current_face",
          "relation": "descends_from",
          "to": "box_face",
          "min_depth": 1,
          "max_depth": 64,
          "to_quantifier": "any_member"
        }
      },
      {
        "relation": "incident_faces",
        "from": "edge",
        "to": "cylinder_current_face",
        "relation_quantifier": {"kind": "at_least", "value": 1}
      },
      {
        "path": {
          "from": "cylinder_current_face",
          "relation": "descends_from",
          "to": "cylinder_face",
          "min_depth": 1,
          "max_depth": 64,
          "to_quantifier": "any_member"
        }
      }
    ]
  },
  "return": "edge",
  "cardinality": {"kind": "exactly", "value": 3},
  "projection": ["ref", "lineage"]
}
```

该 query 不引用 circle、ellipse、length、center 或 backend topology index。它选择的是三条曲线在联合 topology/evolution graph 中的角色。

原 edge 经任意后续 feature 分裂后，选择其 current fragments：

```json
{
  "schema_version": "1.0",
  "variables": {
    "edge": {"type": "edge", "domain": "current"},
    "source_edge": {"type": "edge", "domain": "bound_source", "from_binding": "source_edge"}
  },
  "match": {
    "path": {
      "from": "edge",
      "relation": "descends_from",
      "to": "source_edge",
      "derivation": ["continuation", "fragment"],
      "min_depth": 1,
      "max_depth": 64,
      "to_quantifier": "any_member"
    }
  },
  "return": "edge",
  "cardinality": {"kind": "at_least", "value": 1},
  "projection": ["ref", "lineage"]
}
```

同样的 pattern 适用于 boolean split、fillet、chamfer、shell 或后续 trim；query 不检查 operation name。

### 10.4 Public builder lowering

Public builder 只有一个入口。`select/where/order_by/take/expect` normalize 后 lower 到 canonical variables + constraints：

```text
select(Face, in_=body).where(P)

=> bind body as scope
   seed candidate domain Face(current), including an applicable root
   node predicate P(result)
```

另一个 query 作为 `in_` 时建立其 current subgraph candidate domain：

```text
select(Edge, in_=face_query)

=> bind face_query SelectionSet[Face] as scope
   seed Edge(current) from each selected Face subgraph
```

非 containment 关系不通过改变入口表达：

```text
select(Face, in_=body).where(
    related(adjacent_faces, from_=seed_faces, to=this)
)

=> bind seed_faces
   relation adjacent_faces(seed, result)
```

Cardinality 是顶层 postcondition，不是可插入中间的 operation。多个各自需要 cardinality contract 的 query 通过内部 `SelectionSet` graph binding 组合；public Python composition 仍传入 `SelectionQuery[T]`，不要求用户提前 `resolve()`。

### 10.5 Projection

Projection 只影响 query result/evidence，不影响 match：

```json
[
  "ref",
  "semantic.tags",
  "geometry.area",
  "geometry.center",
  {
    "property": "geometry.normal",
    "relative_to_binding": "body"
  }
]
```

Oriented property projection 必须使用结构化 item，并携带 parent-relative binding；裸字符串 `geometry.normal`/`geometry.tangent` 不合法。

Canonical feature graph 至少要求 projection 包含 `ref`。

### 10.6 Query-to-query binding lowering

Query composition 不引入 Anchor 或 Context payload。每个被引用的 query 都是一个独立 Query IR object；引用方通过 named input port 绑定其 `SelectionSet<T>` output。

```python
source_face = (
    cadql.select(cadql.Face, in_=before_boolean)
    .where(cadql.tag("role.mounting_surface", scope="effective"))
    .expect_one()
)

current_faces = (
    cadql.select(cadql.Face, in_=after_boolean)
    .where(
        cadql.related(
            cadql.descends_from,
            from_=cadql.this,
            to=source_face,
            derivations=("continuation", "fragment"),
            depth=(1, 64),
        )
    )
    .expect_at_least(1)
)
```

Lowering：

```text
query source_face -> SelectionSet[Face]
query current_faces input source_face: SelectionSet[Face]

F: Face(current)
S: Face(bound_source)
F path(descends_from, derivation in {CONTINUATION, FRAGMENT}) S
return distinct F
```

局部 boundary query 同样只增加普通 bindings 和 relations：

```python
coedges = (
    cadql.select(cadql.Coedge, in_=after_boolean)
    .where(cadql.related(cadql.boundary_uses, from_=current_faces, to=cadql.this))
)
```

若 query 使用 `local.*` property，IR 额外声明 `SurfaceChart` variable：Face query 通过 `surface_chart` 绑定 chart，Coedge 通过 `use_chart` 绑定同一个 chart。Chart/frame evidence 属于该 query binding，不属于新的持久化 object kind。`MERGE`/`REPLACEMENT` 默认不传播 chart；validation 要求调用方提供新的 chart/frame binding。

## 11. GraphQL-like Text Syntax

推荐文本前端示例：

```graphql
query MountingFace($body: NodeRef!) {
  brep(node: $body) {
    matches: match(
      type: FACE
      where: {
        and: [
          {
            semantic: {
              tag: {
                scope: EFFECTIVE
                matches: "role.mounting_surface"
              }
            }
          }
          {
            geometry: {
              surfaceType: { eq: PLANE }
              normal: {
                sameDirectionAs: [0, 0, 1]
                angleTolerance: { value: 0.1, unit: DEG }
                relativeTo: $body
              }
            }
          }
        ]
      }
      expect: ONE
    ) {
      ref
      semantic { tags }
      geometry { area center }
    }
  }
}
```

语法约束：

- `match(type: FACE)` 负责 entity matching；文档保持为合法 GraphQL document subset，而不是发明 `match Face` 语法。
- `{ ref geometry semantic }` 是 projection selection set。
- `where` 编译为 predicate AST。
- `expect` 编译为 cardinality。
- `orderBy` 编译为 deterministic order stage。
- GraphQL fragments 只复用 projection；predicate 复用使用 typed input variables，因为标准 GraphQL fragment 不能展开 input object。
- directives 仅用于 debug/evidence 等非选择语义，不能改变 entity identity。

CADQL 1.0 parser 可后置实现。第一阶段以 Python builder 和 JSON IR 为主。

## 12. Python Builder API

目标 API：

```python
from simplecadapi import cadql

mounting_face = (
    cadql.select(cadql.Face, in_=body)
    .where(
        cadql.tag("role.mounting_surface", scope="effective")
        & cadql.surface_type.eq("plane")
        & cadql.normal.same_direction_as(
            (0.0, 0.0, 1.0),
            angle_tolerance=cadql.deg(0.1),
            relative_to=body,
        )
    )
    .expect_one()
)
```

执行：

```python
result = mounting_face.resolve()
face = result.one()
```

直接用于 feature：

```python
result = shell_rsolid(
    body,
    faces_to_remove=mounting_face,
    thickness=2.0,
)
```

Active `GraphSession` 中，feature 必须记录 Query IR，不允许只记录 resolved concrete face。

### 12.1 所有 query 返回同一种结果

`resolve()` 返回：

```python
SelectionSet[Face]
```

它包含：

```text
entities
refs
evidence
diagnostics
query_hash
```

`SelectionSet[T]` 是所有 query 的唯一 resolved result。它携带 entities、refs 和 execution evidence；不存在针对 Anchor、Context、history query 或 property query 的其他 result class。禁止通过普通 list slicing 隐式改变 canonical query semantics。

### 12.2 六种 match case 的统一表达

以下片段假定 `face_a`、`face_b`、`seed_edges`、`source_edge`、`box_faces` 和 `cylinder_faces` 是前面通过同一个 `cadql.select(...)` API 定义的 typed `SelectionQuery[T]` bindings。

类型全集：

```python
faces = cadql.select(cadql.Face, in_=body).expect_at_least(1)
```

属性约束，无论 property 来自 semantic、geometry、spatial 还是 local namespace，都使用 `.where(...)`：

```python
mounting_faces = (
    cadql.select(cadql.Face, in_=body)
    .where(
        cadql.tag("role.mounting_surface", scope="effective")
        & cadql.surface_type.eq("plane")
    )
    .expect_at_least(1)
)
```

Current topology relation，单步形式：

```python
shared_edges = (
    cadql.select(cadql.Edge, in_=body)
    .where(
        cadql.related(cadql.incident_faces, from_=cadql.this, to=face_a)
        & cadql.related(cadql.incident_faces, from_=cadql.this, to=face_b)
    )
    .expect_at_least(1)
)
```

同一个 current topology relation case 的 path 形式：

```python
tangent_chain = (
    cadql.select(cadql.Edge, in_=body)
    .where(
        cadql.related(
            cadql.adjacent_edges,
            from_=seed_edges,
            to=cadql.this,
            step_where=cadql.step.tangent_continuous(
                angle_tolerance=cadql.deg(0.1),
            ),
            depth=(0, 64),
        )
    )
    .expect_at_least(1)
)
```

Oriented occurrence：

```python
outer_coedges = (
    cadql.select(cadql.Coedge, in_=body)
    .where(
        cadql.related(cadql.boundary_uses, from_=mounting_faces, to=cadql.this)
        & cadql.topology.loop_role.eq("outer")
    )
    .expect_at_least(1)
)
```

Evolution relation：

```python
current_fragments = (
    cadql.select(cadql.Edge, in_=result)
    .where(
        cadql.related(
            cadql.descends_from,
            from_=cadql.this,
            to=source_edge,
            derivations=("continuation", "fragment"),
            depth=(1, 64),
        )
    )
    .expect_at_least(1)
)
```

Multi-source Change pattern：

Box/cylinder union 后，不依赖 curve 类型选择交界 edges：

```python
interface_edges = (
    cadql.select(cadql.Edge, in_=result)
    .where(
        cadql.change(
            inputs=(
                cadql.change_input(
                    box_faces,
                    input_port="subjects",
                    role="support",
                    endpoint_quantifier="any_member",
                ),
                cadql.change_input(
                    cylinder_faces,
                    input_port="tools",
                    role="tool",
                    endpoint_quantifier="any_member",
                ),
            ),
            output=cadql.this,
            derivation="intersection",
        )
    )
    .expect_exactly(3)
)
```

`cadql.change(...)` 直接对应 canonical Change constraint。每个 `change_input(...)` 必须声明 input port、role 和 `endpoint_quantifier`；`any_member` 表示 source query 中至少一个 Face 是该 Change input，不表示整个 Face set 被当作一个 graph node。它不检查 producer operation 是否名为 union，也不检查 edge 是 circle 或 ellipse。

选择由 source edge 参与生成、但不一定与 source 同维度连续的 current boundaries，仍是普通 evolution relation：

```python
generated_boundaries = (
    cadql.select(cadql.Edge, in_=result)
    .where(
        cadql.related(
            cadql.generated_from,
            from_=cadql.this,
            to=source_edge,
            derivations=("boundary", "intersection"),
            depth=(1, 64),
        )
    )
    .expect_at_least(1)
)
```

`descends_from` 是较强的材料/拓扑延续关系；`generated_from` 和 `depends_on` 是更宽的因果关系。调用者必须选择符合意图的关系，不能把所有 parent refs 都称作 descendants。

### 12.3 Query composition，不创建 Anchor 或 Context

先定义 source face query：

```python
mounting_surface = (
    cadql.select(cadql.Face, in_=body)
    .where(cadql.tag("role.mounting_surface", scope="effective"))
    .expect_one()
)
```

在 topology-changing operation 后，显式定义 current descendants query：

```python
current_mounting_faces = (
    cadql.select(cadql.Face, in_=result)
    .where(
        cadql.related(
            cadql.descends_from,
            from_=cadql.this,
            to=mounting_surface,
            derivations=("continuation", "fragment"),
            depth=(1, 64),
        )
    )
    .expect_at_least(1)
)
```

再通过普通 current relations 选择 boundary occurrences 和 underlying entities：

```python
outer_coedges = (
    cadql.select(cadql.Coedge, in_=result)
    .where(
        cadql.related(
            cadql.boundary_uses,
            from_=current_mounting_faces,
            to=cadql.this,
        )
        & cadql.topology.loop_role.eq("outer")
    )
    .expect_at_least(1)
)

outer_edges = (
    cadql.select(cadql.Edge, in_=result)
    .where(cadql.related(cadql.use_entity, from_=outer_coedges, to=cadql.this))
    .expect_at_least(1)
)
```

这里 lower 为：

```text
current face descends_from mounting_surface query result
AND current face boundary_uses coedge
AND coedge references returned edge
```

在 topology change 前的唯一 planar Face chart 中使用稳定局部坐标，仍然是相同 query 形态：

```python
right_side = (
    cadql.select(cadql.Coedge, in_=body)
    .where(
        cadql.related(
            cadql.boundary_uses,
            from_=mounting_surface,
            to=cadql.this,
        )
        & cadql.local.u.approximately(
            cadql.local.u_range.max,
            in_chart=mounting_surface,
        )
    )
    .expect_one()
)
```

如果 source face 被 split，`current_mounting_faces.resolve()` 自然返回 `SelectionSet[Face]`。如果业务要求恰好三个 fragments，就在这个 query 上写 `.expect_exactly(3)`；不需要 `FaceFamily` result type 或 `expect_faces_exactly` 专用方法。跨多个 fragments 使用 local UV 时，Coedge query 必须先 `.partition_by(cadql.use_chart)`，并在每个 partition 内绑定对应的 `ONE` Face chart；不能把 `AT_LEAST(1)` Face query 当作单一 chart。

Box/cylinder 交界的三个 box faces 不共面，也仍是普通 Face query：

```python
box_faces = (
    cadql.select(cadql.Face, in_=box)
    .expect_at_least(1)
)

cylinder_faces = (
    cadql.select(cadql.Face, in_=cylinder)
    .expect_at_least(1)
)

interface_edges = (
    cadql.select(cadql.Edge, in_=result)
    .where(
        cadql.change(
            inputs=(
                cadql.change_input(
                    box_faces,
                    input_port="subjects",
                    role="support",
                    endpoint_quantifier="any_member",
                ),
                cadql.change_input(
                    cylinder_faces,
                    input_port="tools",
                    role="tool",
                    endpoint_quantifier="any_member",
                ),
            ),
            output=cadql.this,
            derivation="intersection",
        )
    )
    .expect_exactly(3)
)
```

每个 face 有自己的 SurfaceChart。上例没有跨 chart 比较 UV，只使用 Change source bindings，因此仍是 geometry-independent pattern。

### 12.4 Indexed getter 的未来行为

`get_faces(0)` 等旧 API 暂时保留，但标记为 convenience/legacy selection。它不能被诚实地转换为 CADQL 1.0 semantic pattern，GraphSession 在迁移期继续记录 legacy materialized selection：

```text
legacy_selection(
    basis=backend_enumeration,
    index=0,
    evidence=fingerprint
)
```

该结构是 model schema 的 legacy extension，不属于 Query IR 1.0。文档和 examples 逐步迁移到 semantic/topology/lineage CADQL。

## 13. Operation Graph 集成

### 13.1 新 canonical operation

建议增加：

```text
query_brep_rselection
```

只定义这一个 canonical query operation。Result entity type 是 Query IR 和 typed output 的参数，不再按 Face/Edge/Vertex 拆分 `query_brep_rfaces`、`query_brep_redges` 等平行 operations。

Node 结构：

```json
{
  "op": "query_brep_rselection",
  "inputs": [
    {"port": "scope", "node_id": "node_result", "output_slot": 0},
    {"port": "box_source", "node_id": "node_box", "output_slot": 0},
    {"port": "cylinder_source", "node_id": "node_cylinder", "output_slot": 0}
  ],
  "params": {
    "query_object": "query_box_cylinder_interface",
    "query_hash": "sha256:..."
  },
  "outputs": [
    {"port": "result", "type": "selection_set", "entity_type": "edge"}
  ]
}
```

`query_box_cylinder_interface` 是 model 顶层 `query_objects` 中的完整 normalized Query IR，即 10.3 的完整 pattern，包括两个 current incident-face variables 和 source lineage constraints。Graph node 不保存语义缩水的第二份 query 副本。

该 node 输出 `SelectionSet<T>`，不是复制出来的 shape object。

这里有一个 typed SelectionSet output，而不是按匹配实体数量生成多个 graph outputs。实际 cardinality 位于 Query IR。

### 13.2 Operation Graph 类型桥接

当前 `OperationNode` 只有无名称的 `inputs` 和 `output_count`，不能表达 SelectionSet 与 Shape 的类型区别。引入 CADQL 时，model schema 必须增加：

```json
{
  "inputs": [
    {"port": "body", "node_id": "node_box", "output_slot": 0},
    {"port": "edges", "node_id": "node_query", "output_slot": 0}
  ],
  "outputs": [
    {"port": "result", "type": "solid"}
  ]
}
```

Operation registry 定义静态 signature，例如：

```text
query_brep_rselection(scope: Shape<K>, sources: BindingMap) -> SelectionSet<T>
query_brep_rselection(scope: SelectionSet<K>, sources: BindingMap) -> SelectionSet<T>
make_fillet_rsolid(body: Solid, edges: SelectionSet<Edge>) -> Solid
make_shell_rsolid(body: Solid, faces_to_remove: SelectionSet<Face>) -> Solid
apply_tag_rselection(scope: Shape<K>, targets: SelectionSet<T>, tag: Tag) -> Shape<K>
```

Importer 只能在 output slot 可恢复时把 2.0 graph 的 positional inputs 按 operation signature 升级为 named ports；无法恢复 slot 的多输出引用必须保留为 legacy binding 并报告 migration diagnostic，不能猜测。Exporter 在新 model schema 中不再用 params 中的 `selected_*_node_ids` 表达数据流。

该变更需要将 model/graph schema 从 `2.0` 升级为 `3.0`；Query IR 仍独立使用 `1.0`。Package 版本与 schema 版本不绑定。

### 13.3 Feature 消费 SelectionSet

例如 shell graph：

```text
body -----------------------> shell
  \                            /
   -> query_brep_rselection --
```

Feature params 不再新增并行的：

```text
selected_faces
selected_face_node_ids
selected_face_indices
selector_hint
selection_query
```

新 graph 只通过 typed input 消费 selection set。Legacy importer 可以将旧字段升级成 Query IR + evidence/fallback。

### 13.4 Semantic tag persistence

Semantic query 要可 replay，tag assignment 必须进入 Operation Graph，而不能只修改 Python wrapper 的 `_tags`。新增 canonical alias operation：

```text
apply_tag_rselection(
    scope: Shape<K>,
    targets: SelectionSet<T>,
    tag: Tag,
    propagation: LOCAL | DOWNWARD,
) -> Shape<K>
```

该 operation 不改变 geometry，返回具有新 semantic state 的 shape view。Root shape tagging 被 lower 为选择 scope root 的 SelectionSet。自动 tagging 也生成相同的 canonical `TagBinding`，但可作为 producer operation 的 semantic output metadata 存储，避免创建大量可见 node。

TagBinding 保存 assignment node、target query/ref、attachment 和 propagation policy。执行 CADQL 时，provider 以当前 scope producer 为版本边界计算 local/inherited/effective tags。下游 geometry operation 必须通过 topology delta 传播 tag binding；没有 lineage evidence 时不得猜测 lineage tag。

Legacy 2.0 payload 中只有扁平 tags，导入时统一标为 `effective_legacy`。它们只参与 `scope: effective` 查询并产生 migration warning，不能伪造 local/inherited 来源。

### 13.5 是否保留 `make_select_*`

迁移期保留：

```text
make_select_rvertex
make_select_redge
make_select_rwire
make_select_rface
make_select_rsolid
```

它们被定义为 legacy materialized selection node。新代码不再为 query 的每个 match 自动生成一个 `make_select_*` node。

迁移稳定后只保留 explicit one-entity materialization 作为 legacy graph adapter；CADQL 不增加 `selection_item_rentity`，避免通过另一名称恢复 index selection。

## 14. Query Execution

### 14.1 执行阶段

统一执行器流程：

```text
parse/build
-> normalize
-> type validate
-> capability validate
-> compile execution plan
-> resolve named bindings
-> build current BRep snapshot
-> load reachable Topology Evolution Graph
-> seed candidates for typed variables
-> join topology/evolution/provenance constraints
-> evaluate semantic and optional geometry predicates
-> project and distinct the return variable
-> order
-> take
-> cardinality validation
-> build refs/evidence
-> return SelectionSet[T]
```

### 14.2 Property provider

执行器不直接散落调用 OCP/FreeCAD API。定义 backend-neutral provider protocol：

```python
class BRepQueryProvider(Protocol):
    def resolve_binding(self, binding: QueryBinding) -> object: ...
    def snapshot(self, scope: object) -> BRepSnapshot: ...
    def evolution_graph(self, scope: object) -> TopologyEvolutionGraph: ...
    def related(self, entity: object, relation: Relation) -> Sequence[object]: ...
    def property(self, entity: object, property_id: str) -> object: ...
    def tags(self, entity: object, scope: TagScope) -> Sequence[str]: ...
    def evidence_ref(self, entity: object) -> TopoRef: ...
    def entity_token(self, entity: object) -> object: ...
    def use_token(self, use: object) -> object: ...
```

`entity_token` 只在一次 provider execution 内用于未定向 entity identity、`distinct` 和 deterministic materialization。OCP provider 应使用 topology identity (`IsSame` 等价语义)，不能使用 Python wrapper identity。`use_token` 还包含 parent、orientation 和 occurrence。两种 token 都不持久化，也不能作为业务 tie-breaker；`TopoRef` 只进入 evidence/fallback，不被命名为 durable stable identity。

实现：

```text
OCPQueryProvider
FreeCADQueryProvider
```

两者运行同一 Query IR conformance tests。

### 14.3 Determinism

执行器必须保证：

- `distinct` 的 equality semantics 明确。
- order keys 逐项稳定比较。
- 缺失 property 的排序行为明确，默认 validation error。
- query hash 由 normalized IR 生成，与 dict insertion order 无关。
- 同一 provider、相同 BRep 和相同 Query IR 返回相同 ordered refs。

### 14.4 History capability boundary

Provider 对每个 scope 声明 history level：

```text
NONE       只有当前 BRep snapshot，例如无 sidecar 的 STEP 导入。
PARTIAL    有部分 operation/topology parent evidence。
COMPLETE   查询可达范围内的 Change graph 满足 canonical completeness checks。
```

Current topology/semantic/geometry pattern 在 `NONE` 下仍可执行。任何引用 history/change domain 或 evolution path 的 query 必须在 validation 阶段计算所需 evidence coverage：

- `NONE`：current topology/semantic/geometry query 和同一 snapshot 的 query-to-query relation 可以执行；只有跨 snapshot evolution path 产生 `UnsupportedQueryCapabilityError`。
- `PARTIAL`：只有 query 所需 operation/path 均有完整 evidence 时才能执行，否则失败。
- `COMPLETE`：按正常 graph matcher 执行。

缺失 history 不是 predicate false，也不能自动切换到 geometry fingerprint。用户可以显式提供 semantic tag sidecar 或选择 current-space query，但系统不能声称恢复了不存在的建模历史。

## 15. Evidence 和 Drift Detection

### 15.1 Evidence schema

```json
{
  "query_hash": "sha256:...",
  "binding_hash": "sha256:...",
  "execution_hash": "sha256:...",
  "provider": "ocp",
  "provider_version": "7.9.3",
  "selected": [
    {
      "ref": {
        "graph_id": "graph_1",
        "node_id": "node_box",
        "output_slot": 0,
        "kind": "FACE",
        "topo_id": "face_7"
      },
      "properties": {
        "geometry.surface_type": "plane",
        "geometry.area": {"value": 245.0, "unit": "mm2"},
        "geometry.normal": {
          "value": [0, 0, 1],
          "relative_to_binding": "body"
        },
        "semantic.tags": ["role.mounting_surface"]
      },
      "fingerprint": {
        "bbox": {},
        "center": [0, 0, 10]
      }
    }
  ],
  "candidate_count": 1,
  "runner_up": null,
  "diagnostics": []
}
```

Hash 定义：

- `query_hash`：normalized typed graph pattern、cardinality、ordering、projection 和 options，不含具体 node IDs。
- `binding_hash`：所有 named bindings 的 graph/node/output/selection identity 的 canonical hash。
- `execution_hash`：`query_hash + binding_hash + provider semantic version + scope content fingerprint`。

Evidence 中的 `TopoRef.topo_id` 和 geometry fingerprint 只描述一次 execution 的结果，不是 durable query identity。

### 15.2 Replay behavior

Replay：

1. 重新执行 Query IR。
2. 验证 cardinality 和 ordering boundary ties。
3. 比较 query result 与旧 evidence。
4. `drift_mode=diagnose` 时，如果 execution identity 改变但 pattern 仍满足，记录 `selection_drift` diagnostic。
5. `drift_mode=strict` 时，同一情况产生 `SelectionDriftError`。
6. 如果 query 不再满足，不自动按旧 fingerprint 选择，除非 legacy query options 显式允许 fallback。

### 15.3 Fallback policy

```text
NONE
EVIDENCE_FINGERPRINT
LEGACY_INDEX
```

Canonical feature query 默认 `NONE`。Legacy model migration 可使用 `EVIDENCE_FINGERPRINT` 或 `LEGACY_INDEX`，并生成 warning。

## 16. Error Model

统一错误：

| Error | 条件 |
| --- | --- |
| `QuerySyntaxError` | 文本或 JSON IR 语法不合法。 |
| `QueryValidationError` | 类型、relation、property 或 unit 不合法。 |
| `UnsupportedQueryCapabilityError` | provider/backend 不支持所需能力。 |
| `QueryScopeError` | source node/output 不存在或类型错误。 |
| `SelectionCardinalityError` | 非零结果仍低于 cardinality minimum。 |
| `NoMatchError` | `SelectionCardinalityError` 的特例：结果为零且 minimum 大于零。 |
| `AmbiguousSelectionError` | 结果超过 cardinality maximum，或 top-N boundary 无法唯一确定。 |
| `PropertyUnavailableError` | 实体上无法稳定计算请求属性。 |
| `SelectionDriftError` | strict replay 中结果相对 evidence 发生不允许的漂移。 |
| `QueryComplexityError` | Pattern variable、constraint、path 或 candidate 数量超过限制。 |
| `LegacySelectionError` | Legacy index/fingerprint selector 缺少 basis 或无法解析。 |

所有错误必须包含的公共 payload：

```text
query_location
message
error_code
repair_suggestions
```

可用时附加 `query_hash`、`binding_hash`、scope、expected/actual cardinality、candidate summaries、unsupported capability 和 source location。Syntax error 不要求提供尚不能计算的 hash 或 candidates。

## 17. Translator Contract

### 17.1 Backend capability

Translator `capabilities.py` 增加：

```json
{
  "query_ir_versions": ["1.0"],
  "query_entity_kinds": [
    "compound", "compsolid", "solid", "shell", "face", "wire", "edge", "vertex", "topo_use", "coedge"
  ],
  "query_domains": ["current", "history", "change", "operation", "bound_source"],
  "query_relations": [
    "contains_direct", "contains", "incident_faces", "adjacent_faces", "adjacent_edges",
    "boundary_uses", "use_entity", "use_parent", "use_chart", "surface_chart",
    "next_coedge", "previous_coedge", "mate_coedge", "starts_at", "ends_at", "belongs_to_loop",
    "descends_from", "generated_from", "depends_on", "co_result_of", "changed_with"
  ],
  "history_level": "complete",
  "use_history": "ordered",
  "evolution_derivations": [
    "continuation", "fragment", "merge", "intersection", "boundary", "replacement"
  ],
  "query_properties": [
    "geometry.length",
    "geometry.area",
    "geometry.volume",
    "geometry.center",
    "geometry.normal",
    "geometry.curve_type",
    "geometry.surface_type",
    "topology.loop_role",
    "topology.loop_identity",
    "local.u_range.min",
    "local.u_range.max",
    "semantic.tags"
  ]
}
```

### 17.2 FreeCAD translator

FreeCAD 不再维护独立 selector scoring contract，而是实现 `FreeCADQueryProvider`。

`query_brep_rselection` runtime：

1. 从 `GRAPH_NODES[source_node_id]` 取得 shape。
2. 使用统一 Query IR evaluator。
3. 返回 `GRAPH_SELECTIONS[node_id]` 中的 typed selection result。
4. 默认不为每个 selection 创建 visible `Part::Feature`。
5. 如果需要 materialized helper object，放入 construction group 并隐藏。
6. fillet/chamfer/shell 直接将 SelectionSet refs 转换为 FreeCAD `EdgeN/FaceN`。

### 17.3 Backend parity

同一 fixture 必须在 OCP 和 FreeCAD provider 上满足：

- result cardinality 一致。
- semantic tags 匹配一致。
- geometry predicate tolerance 一致。
- normal orientation semantics 一致。
- ambiguity outcome 一致。
- Change input roles 和 output derivations 一致。
- `descends_from/generated_from/depends_on` path result 一致。

不要求 backend 的 raw topology index 一致。

## 18. Security 和复杂度限制

CADQL 不是任意 Python 执行环境。

禁止：

- Python lambda/callable predicate 进入 canonical IR。
- 任意 module/class introspection。
- 任意 regex。
- unbounded recursive traversal。
- backend-specific property path 注入。

QueryOptions 限制：

```text
max_pattern_variables
max_pattern_constraints
max_path_changes
max_candidate_count
max_projection_fields
max_fragment_expansion
execution_timeout
```

超限产生 `QueryComplexityError`。

## 19. Versioning

Query IR 独立版本：

```text
query.schema_version = 1.0
```

它不与 model schema version 强绑定。Model schema 声明支持的 Query IR version 范围。

Version policy：

- 新增 optional property/predicate：minor-compatible。
- 改变 predicate、normal、tag scope、cardinality 语义：major change。
- Provider capability 可以小于完整 schema，但必须显式声明。

## 20. 迁移方案

### Phase 0：Characterization

目标：锁住当前 behavior 和问题。

工作：

- 收集当前 QL、indexed getter、tag selection、`make_select_*` fixtures。
- 增加对称 geometry、nested selection、Compound、pattern、fillet/chamfer/shell tests。
- 增加 box/cylinder boolean interface、edge split、face trim、split/merge lineage characterization fixtures。
- 审计每个 topology-changing operation 当前能提供的 input/output parent mapping；区分 complete、partial 和 absent evidence。
- 增加 OCP replay 与 FreeCAD translator parity tests。
- 不修改 public API。

退出标准：

- 当前每种 selection path 都有 model JSON fixture。
- 已知 ambiguity 和 backend mismatch 有明确 failing test。

### Phase 1：Typed Graph Pattern IR

新增模块建议：

```text
src/simplecadapi/cadql/
├── __init__.py
├── types.py
├── predicates.py
├── relations.py
├── ir.py
├── validation.py
├── normalize.py
├── errors.py
└── provider.py
```

实现：

- Query IR dataclasses 和 JSON schema。
- Variable、topology relation、evolution path 和 pattern constraint registry。
- Property/relation applicability registry。
- Unit/tolerance normalization。
- Cardinality 和 set semantics。
- Query hash。
- 不实现 GraphQL parser。

退出标准：

- JSON IR round-trip 稳定。
- invalid variable/relation/path/property/unit 在执行前失败。
- normalized IR hash 稳定。

### Phase 2：Topology Evolution Evidence

目标：为 geometry-independent history query 建立可靠事实源。

实现：

- 将当前 `TopoDelta` 扩展为显式 Change inputs/outputs。
- 增加 `TopoUseVersion`、`USE_ENTITY/USE_PARENT` 和可选 ordered use-fragment evidence。
- 每个 input 记录 entity ref、input port 和 role。
- 每个 output 记录 entity ref、event 和 derivation。
- 为 boolean、fillet、chamfer、shell、cut、transform 和 pattern 建立 topology history adapter。
- 区分 `TopoEntityVersion` 与 oriented `TopoUse`。
- 序列化完整 parent refs，不只保存宏观 generated/modified lists。
- Capability 按 operation 和 derivation 分类声明 complete/partial/unsupported。

退出标准：

- split、merge、intersection、boundary 和 continuation fixtures 可重建 Change graph。
- Seam/coedge fixture 能区分 underlying entity ancestry 与 occurrence ancestry；不支持 use ordering 时 capability 明确为 partial。
- 同一 fixture 的 OCP record-time evidence 可 JSON round-trip。
- 证据不完整时 lineage query 在执行前失败，不做 geometry fallback。

### Phase 3：OCP Pattern Evaluator 和 Python Builder

新增：

```text
cadql/builder.py
cadql/evaluator.py
cadql/providers/ocp.py
```

实现：

- Solid/Face/Wire/Edge/Vertex topology pattern。
- Current/history/change domains 和 typed joins。
- `descends_from`、`generated_from`、`depends_on` 和 Change constraints。
- 基础 geometry properties。
- semantic tags。
- pattern/order/cardinality/evidence。
- Python fluent builder。

Feature API 开始接受 `SelectionQuery[T]`/`SelectionSet[T]`，但旧 list/ShapeSelector 继续兼容。

退出标准：

- 新 builder 能表达 boolean interface 和任意 feature 后的 edge fragments，且不需要 geometry predicate。
- 新 builder 可替代 fillet/chamfer/shell 的主要 QL examples。

### Phase 4：Operation Graph 和 Semantic Integration

实现：

- 新增 `query_brep_rselection` canonical op。
- Graph/model schema 3.0 增加 named input ports 和 typed outputs。
- Feature graph 通过 typed selection input 消费 query result。
- Serializer/replay 支持 Query IR 和 Evidence。
- `apply_tag_rselection` 和 source-preserving TagBinding。
- Legacy selected params 导入升级。

退出标准：

- 新 graph 不再依赖 `selected_*_indices` 作为 primary contract。
- QL semantic intent 在 model JSON 中可见。
- active GraphSession 能记录完整 Query IR、bindings 和 TagBinding。

### Phase 5：FreeCAD Provider

实现：

- `FreeCADQueryProvider`。
- Generated runtime graph-pattern evaluator。
- FreeCAD topology history 到 canonical Change graph 的 adapter。
- detail feature SelectionSet 转换。
- selection helper 默认 internal/hidden。
- OCP/FreeCAD conformance suite。

退出标准：

- 所有共享 query fixture 在两个 provider 中 outcome 一致。
- Boolean interface 和 feature fragment lineage outcome 一致。
- 不再维护独立的 ad hoc FreeCAD geo selector scorer。

### Phase 6：GraphQL-like Parser

在 IR 和 evaluator 稳定后实现：

- parser。
- variables。
- fragments。
- schema introspection。
- formatter。
- query explain/debug tools。

GraphQL parser 不是前五阶段的 blocker。

### Phase 7：Deprecation

逐步 deprecate：

- 当前 `ShapeSelector` 作为 canonical graph representation。
- `selection_query`、`selected_*_node_ids`、indices 多轨并存。
- indexed getter 作为推荐 replayable selection。
- backend-specific geo selector scoring。

旧 model JSON 继续通过 migration adapter 导入。

## 21. 测试方案

### 21.1 IR tests

- JSON round-trip。
- schema version。
- normalized hash。
- property/relation type validation。
- unit conversion。
- tolerance override。
- cardinality validation。

### 21.2 Geometry tests

- box 最大/最小平面。
- cylinder planar/cylindrical faces。
- circular edge radius。
- face normal same/opposite/parallel semantics。
- inner/outer wire。
- nested face-to-edge traversal。
- planar chart frame 在 face split 后保持一致。
- periodic surface chart 的 seam coedges 保留 occurrence。

### 21.3 Topology evolution/composition tests

- box/cylinder union 交界 edge 只通过两个 source bindings 和 `INTERSECTION` 选择。
- 原 edge 经 boolean/fillet/chamfer 后的 current fragments。
- 原 face trim/split 后的 query 返回多个 current Face。
- `select(T, in_=query)` 只做 containment，不隐式加入 incident 或 history candidates。
- 显式 `incident_faces` relation 能选到 fillet/chamfer transition faces。
- 显式 Change constraint 能选到同一 Change 的 boundaries。
- coedge fragment ordering 有 evidence 时可用，无 evidence 时明确拒绝 ordered query。
- 多个不共面 faces 各自维护 chart，禁止直接跨 chart 比较 UV。
- 无 history 的导入 shape 可执行同一 snapshot 的 query composition。
- 无 history 的 source query 跨 topology-changing snapshot evolution 明确失败。
- Source face 完全被 feature 消耗时，Change constraint 仍可从历史 input 到达 generated outputs。
- `MERGE/REPLACEMENT` 默认不继承 source chart；重新定义 Face query 和 frame 后才允许 local query。

### 21.4 Semantic tests

- local tag。
- inherited/effective tag。
- lineage tag。
- wildcard token pattern。
- metadata namespace。

### 21.5 Ambiguity tests

- 对称 box 的相同 edge。
- duplicated holes。
- radial pattern 中相同 faces。
- 同 area/normal/center 的候选。
- order keys 同分。

预期：需要唯一实体时产生 `AmbiguousSelectionError`。

### 21.6 Replay tests

- 参数变化后 query 仍匹配同一语义实体。
- topology id 改变但 semantic query 仍成立。
- query result drift evidence。
- strict/no fallback。
- legacy fingerprint fallback warning。

### 21.7 Translator conformance

- OCP 和 FreeCAD cardinality 一致。
- OCP 和 FreeCAD property normalization 一致。
- normal orientation 一致。
- tag scope 一致。
- ambiguous query 均失败。
- fillet/chamfer/shell subelement mapping 正确。

## 22. API 示例

### 22.1 最大平面

```python
top_face = (
    cadql.select(cadql.Face, in_=body)
    .where(cadql.surface_type.eq("plane"))
    .order_by(cadql.center.z.desc(), cadql.area.desc())
    .take(1, boundary_ties="error")
    .expect_one()
)
```

如果多个面 center.z 和 area 均相同，查询失败，而不是取第一个。

### 22.2 Semantic mounting faces

```python
mounting_faces = (
    cadql.select(cadql.Face, in_=body)
    .where(
        cadql.tag("role.mounting_surface", scope="effective")
        & cadql.surface_type.eq("plane")
    )
    .expect_at_least(1)
)
```

### 22.3 Face boundary 中的 circular edges

```python
mounting_surface = (
    cadql.select(cadql.Face, in_=body)
    .where(cadql.tag("role.mounting_surface", scope="effective"))
    .expect_one()
)

holes = (
    cadql.select(cadql.Edge, in_=mounting_surface)
    .where(
        cadql.curve_type.eq("circle")
        & cadql.radius.approximately(cadql.mm(2.5), rel=1e-6)
    )
    .expect_exactly(4)
)
```

### 22.4 Feature consumption

```python
rounded = fillet_rsolid(
    body,
    edges=(
        cadql.select(cadql.Edge, in_=body)
        .where(cadql.tag("edge.outer.vertical"))
        .expect_exactly(4)
    ),
    radius=2.0,
)
```

### 22.5 Corner case: source face 被 split 成多个 current faces

假设 boolean 或后续 trim 将原来的一个 mounting face 切成三个不连续的 face fragments。Source query 要求唯一；current query 独立要求三个结果：

```python
mounting_surface = (
    cadql.select(cadql.Face, in_=before_boolean)
    .where(cadql.tag("role.mounting_surface", scope="effective"))
    .expect_one()
)

current_mounting_faces = (
    cadql.select(cadql.Face, in_=after_boolean)
    .where(
        cadql.related(
            cadql.descends_from,
            from_=cadql.this,
            to=mounting_surface,
            derivations=("continuation", "fragment"),
            depth=(1, 64),
        )
    )
    .expect_exactly(3)
)

# Query all current boundary occurrences across the three fragments.
outer_coedges = (
    cadql.select(cadql.Coedge, in_=after_boolean)
    .where(
        cadql.related(
            cadql.boundary_uses,
            from_=current_mounting_faces,
            to=cadql.this,
        )
        & cadql.topology.loop_role.eq("outer")
    )
    .expect_at_least(3)
)

# Most detail features consume underlying 3D edges, not oriented coedges.
fragment_edges = (
    cadql.select(cadql.Edge, in_=after_boolean)
    .where(cadql.related(cadql.use_entity, from_=outer_coedges, to=cadql.this))
    .expect_at_least(3)
)
```

Lowering 的关键部分：

```text
F: Face(current)
U: TopoUse(current)
E: Edge(current)

F descends_from mounting_surface query result
  through derivation in {CONTINUATION, FRAGMENT}
F boundary_uses U
U use_entity E
return distinct E
```

这里不能沿用 source query 的 `.expect_one()` 检查 current results。两个 query 有两个独立 cardinality contract。若参数变化后只产生两个 fragments，current query 的 `.expect_exactly(3)` 必须产生 `SelectionCardinalityError`，而不是按旧 topology index 补选第三个 face。

### 22.6 Corner case: source face 被 fillet/chamfer 完全消耗

假设一个很窄的 face 被 fillet 或 chamfer 完全消耗，最终结果中不存在任何 `CONTINUATION/FRAGMENT/REPLACEMENT` face。Descendant query 应返回空集；generated-output query 直接从消费 source face 的 Change 开始，不需要 context expansion mode：

```python
narrow_surface = (
    cadql.select(cadql.Face, in_=before_fillet)
    .where(cadql.tag("role.narrow_transition", scope="effective"))
    .expect_one()
)

transition_faces = (
    cadql.select(cadql.Face, in_=after_fillet)
    .where(
        cadql.related(
            cadql.generated_from,
            from_=cadql.this,
            to=narrow_surface,
            derivations=("boundary",),
            depth=1,
        )
    )
    .expect_at_least(1)
)

transition_edges = (
    cadql.select(cadql.Edge, in_=after_fillet)
    .where(
        cadql.related(
            cadql.depends_on,
            from_=cadql.this,
            to=narrow_surface,
            depth=1,
        )
        & cadql.related(
            cadql.co_result_of,
            from_=cadql.this,
            to=transition_faces,
        )
    )
    .expect_at_least(1)
)
```

对应语义：

```text
source current descendants may be empty
Change consumes historical narrow_surface query result
Change outputs transition_faces with BOUNDARY derivation
transition_edges are outputs of the same Change and depend on the source
```

该查询不检查 operation 名称是否为 fillet/chamfer，也不假定 transition edge 是 line、circle 或 spline。若 backend 只有 current BRep、没有消费 source face 的 Change evidence，必须产生 `UnsupportedQueryCapabilityError`；不能退化为按距离或面积猜测 transition faces。

## 23. Open Questions

以下问题在 Phase 1 前需要做 ADR 决策：

1. SelectionSet 是否允许作为 public Python sequence，还是只暴露显式 `.all()`、`.one()`。
2. Curved face normal/curvature sampling policy 在哪个版本加入。
3. Evidence 是否默认进入 model JSON，还是只对 feature-consumed query 持久化。
4. Legacy index fallback 的废弃周期。
5. GraphQL-like parser 是自行实现最小 grammar，还是复用 GraphQL parser 后转换 AST。
6. Periodic surface chart 的 canonical seam 和 UV unwrap policy。
7. Source Face query 的 frame 在非刚性/拓扑替换 operation 后允许 continuation，还是必须显式提供新 frame。

## 24. 推荐结论

采用以下方向：

1. 新建 `simplecadapi.cadql`，不继续把当前 `ql.py` 扩展为长期 canonical contract。
2. Query IR 1.0 是核心规范；GraphQL-like text 是后置前端。
3. Canonical query 是 Current BRep Graph 与 Topology Evolution Graph 上的 typed graph pattern，不是 operation-specific selector。
4. Public API 只有 `cadql.select(ResultType, in_=scope)` 一个 query 入口；Shape、operation output 和已有 query 都通过同一个 `in_` binding 进入。
5. 所有选择归约为六类 match capability；所有 query 使用相同的 `where/order_by/take/expect` 行为并产生 `SelectionQuery[T]`，`.resolve()` 统一返回 `SelectionSet[T]`。
6. Geometry predicate 是可选约束；topology role、source binding、semantic tag 和 evolution path 可以独立完成选择。
7. 完整 Change input/output/role/derivation evidence 是 history query 的前置条件，缺失时明确报 capability error。
8. Unit、tolerance、oriented TopoUse、ordering 和 cardinality 必须进入 contract。
9. Query intent 与 Evidence/fingerprint 分离；`TopoRef` 只作 evidence/fallback。
10. 新 graph 使用 typed SelectionSet node，不再把每个 query match 自动展开为 geometry-only `make_select_*`。
11. OCP replay 和所有 translator 运行同一 Query IR、Change Graph、TopoUse 和 surface-chart conformance suite。
12. GraphQL-like parser 只有在 Query IR 和 evaluator 稳定后才实现。

该方案的核心不是设计更漂亮的 filter API，而是建立一个可以跨参数变化、跨 replay、跨 CAD backend 保留用户选择意图的 topology query contract。
