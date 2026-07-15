# CADQL Tagging 与 Auto Semantics 重构设计

## 文档状态

- 状态：Partially implemented (bounded transition)
- 目标版本：Semantic Binding Schema 1.0
- 依赖：`design-docs/cadql-brep-query-language.md`
- 目标项目：SimpleCADAPI 2.x
- 主要影响模块：`tagging.py`、`autotag.py`、`core.py`、`topology.py`、`tracking.py`、`graph.py`、`serializer.py`、`cadql/`、各 translator backend
- 非目标：继续扩展当前 `ql.py`、为每种 feature 增加专用 selector、用 tag 替代完整 topology history

### 当前实现边界

当前 2.0 graph/model schema 已实现 Semantic Binding Schema 1.0 的 bounded subset：source-preserving `TagBinding`、`local`/`inherited`/`effective`/`lineage` scope、显式 downward policy、evidence-gated tracking projection、semantic-only graph node、model-level `semantic_bindings` registry 与 strict replay。当前 `ql.py` 仅作为过渡层增加 scoped tag predicate、typed operation/origin/output-role predicate，以及 projected source-binding/source-topology predicate，不是完整 CADQL Query IR。

尚未实现完整 typed CADQL Query IR、完整 Topology Evolution Graph、GraphQL-like parser、所有 topology/use 类型以及全部 translator backend parity。当前实现继续使用 graph/model schema `2.0`；本文中依赖 schema `3.0` 或完整 provider contract 的部分仍为 proposed。

### 已实现的 feature output role 子集

当前 `TopoDelta.roles: Tuple[TopoRoleEntry, ...]` 将 output role 与
`TopoEntry.event` 分开保存。每个 role entry 使用 geometry-node-owned durable
`TopoRef`，并要求 operation-owned OCC witness、`coverage=complete`、
`status=proven` 与 exact result membership。以下是当前 public contract：

| Operation | Role | Kind | Requested cardinality |
| --- | --- | --- | --- |
| Extrude | `extrusion.start` | Face | exactly one |
| Extrude | `extrusion.end` | Face | exactly one |
| Extrude | `extrusion.side` | Face | at least one, bind all |
| Revolve | `revolution.start` | Face | exactly one |
| Revolve | `revolution.end` | Face | exactly one |
| Revolve | `revolution.side` | Face | at least one, bind all |
| Fillet | `fillet.patch` | Face | at least one, bind all |
| Chamfer | `chamfer.patch` | Face | at least one, bind all |
| Shell | `shell.body_face` | Face | at least one, bind all |
| Shell | `shell.offset_face` | Face | at least one, bind all |
| Shell | `shell.closing_descendant` | Face | at least one, bind all |
| Shell | `shell.wall` | Edge | at least one, bind all |
| Loft | `loft.start` | Face | exactly one |
| Loft | `loft.end` | Face | exactly one |
| Loft | `loft.side` | Face | at least one, bind all |
| Sweep | `sweep.start` | Face | exactly one |
| Sweep | `sweep.end` | Face | exactly one |
| Sweep | `sweep.side` | Face | at least one, bind all |

这些 role 由 `FirstShape`、`LastShape`、`Generated`、`Modified`、Fillet/Chamfer
contour API 和 exact result membership 产生；不使用 center/normal、enumeration
index 或 unmatched-to-generated fallback。Public feature 的 named tag argument 与
`output_tags` generic mapping lower 为独立 `apply_tag_rselection` node，用户
binding 是 `USER_OPERATION + ASSERTED`，自动 role binding 是
`AUTO_RULE + PROVEN + RECOMPUTE`。Geometry node params 不保存这些 tag。

Strict replay 会重建 feature 后比较 serialized/recomputed role entries，并验证
role allowlist、feature node ownership、output slot、coverage/status、topology
kind、binding ancestry、cardinality 和 exact selected refs。Full revolve 不具有
独立 start/end cap；OCC 未证明的 shell role 也保持 unavailable。调用方请求这些
role 时整个 operation 失败，不以 geometry guess 补齐。

当前 bounded QL 增加：

```python
ql.output_role(role_name="extrusion.end")
ql.source_binding(binding_id="tag_binding_...")
ql.source_topology(topo_id="edge_...")
```

后两个 predicate 只查询 canonical local `TagBinding.evidence`。Extrude 的
source Edge 到 generated side Face 投影只复制完整 witness 下的 local
`USER_OPERATION` binding，并保存 source binding/topology、target topology、
operation、role 和 evidence method。Replay-safe authoring 必须把
`apply_tag_rselection(...)` 返回的 semantic view 作为 feature input；detached
semantic branch 不会引入隐藏 graph coupling。Predicate payload
deserialization 对 unknown kind、unknown/missing fields 与非法 child cardinality
fail closed。

## 1. 摘要

下一代 tagging 系统不再把所有语义压入 topology wrapper 上的 `_tags: set[str]`。Canonical truth 是可序列化、保留来源的 `TagBinding`；CADQL 将 tag 作为 `semantic.tags` 属性查询，并在执行时计算 `local`、`inherited`、`effective` 和 `lineage` 四种 scope。

Auto tagging 也不再表示“给所有结果实体补一些字符串”。它是一组 evidence-gated semantic rules：规则只能在所需事实可证明时产生 `TagBinding`，证据不足时产生 `UNKNOWN`/diagnostic 或不产生 assertion，不能把 unmatched entity 推断为 generated。

本设计遵循以下边界：

1. 用户或产品域赋予的 unary categorical meaning 使用 tag。
2. Current BRep 结构事实使用 topology property/relation。
3. 数值、枚举、几何分类和诊断使用 typed property/metadata。
4. Operation、source role、split/merge/generated/preserved 和多来源因果使用 Topology Evolution Graph。
5. Tag 可以作为稳定意图锚点，但不能成为 relation、history 或 evidence 的损失性副本。

## 2. 当前问题

当前实现由四套机制叠加而成：

| 机制 | 例子 | 当前问题 |
| --- | --- | --- |
| 用户显式 tag | `role.mounting_surface` | 与系统 tag 共用一个 set，无法识别作者和 assignment。 |
| Wrapper 结构 tag | `wire.outer`、`edge.boundary` | 把可直接从 BRep graph 得到的事实 materialize 为字符串。 |
| 几何分类 tag | `face.top`、`face.side` | frame、算法和置信度不明确；未知几何退化为 enumeration index。 |
| Tracking tag | `op.cut.generated`、`origin.tool` | 把 Change event 和 source role 降级为 unary string，且依赖 Face-only matcher。 |

具体缺陷包括：

- `_tags: set[str]` 不保存 assignment、producer、target query、attachment、propagation、evidence 和 lifecycle。
- Downward propagation 直接复制字符串，之后无法区分 local 与 inherited。
- `_carry_source_tags()` 直接复制 source Face 字符串，无法恢复 lineage witness。
- `apply_tracking_tags()` 只遍历 Face，不能消费 Edge/Wire/TopoUse history。
- Unmatched Face 默认被标记 `generated`，把 history 缺失伪装成确定事件。
- Boolean `section_edges` 是 Edge evidence，却用 Face ID 匹配，不能正确工作。
- Loft/sweep 提供 Edge history，但 Face-only auto tagger仍会给结果 Face生成看似完整的 operation tag。
- Transform 的 pure-preserve fallback 没有逐实体 correspondence，却对所有结果 Face声称 preserved。
- `face.face_0`、pattern index 和 sketch edge zip-order 依赖 backend enumeration，不是 durable semantic identity。
- Operation runtime 的 rich `delta_entries` 与 canonical `TopoDelta.entries` 分离，replay/translator 无法保证同一 semantic output。

当前测试中的“每个结果 Face 都有 operation tag”不是正确性证明，因为该覆盖率可以完全由 unmatched-to-generated fallback 产生。

## 3. 与 CADQL 的关系

CADQL 在三种图的联合视图上执行：

| 数据层 | 职责 | Tagging 是否拥有该事实 |
| --- | --- | --- |
| Operation Graph | 模型构建、assignment producer、query binding | 否；TagBinding 引用它。 |
| Current BRep Graph | contains、boundary、incident、adjacent、TopoUse | 否；tag 只作为 entity 的 semantic property。 |
| Topology Evolution Graph | Change input/output、role、event、derivation | 否；lineage scope 依赖它计算。 |
| Semantic Binding Store | 用户/系统声明的稳定 unary meaning | 是。 |

CADQL 只有一种 tag predicate：

```python
cadql.tag("role.mounting_surface", scope="effective")
```

它是对 `semantic.tags` 的 property predicate，不创建新的 selector、anchor 或 context 类型。Tag assignment 的 target 本身使用同一套 `SelectionQuery[T]`；不再引入另一套 tag selector DSL。

## 4. 设计原则

### 4.1 一项事实只有一个 canonical owner

以下映射是强制的：

| 事实 | Canonical owner | 可否派生为 tag |
| --- | --- | --- |
| Face 的 outer/inner loop | `topology.loop_role` | 默认否。 |
| Edge 是 Face boundary | `boundary_uses`/`use_entity` | 否。 |
| Surface 是 plane/cylinder | `geometry.surface_type` | 默认否。 |
| Face 当前在 world +Z 方向 | oriented geometry predicate + frame | 否。 |
| Entity 由某 operation 产生 | `provenance.produced_by` | 否。 |
| Entity 是 preserved/modified/generated | Change output event | 否。 |
| Entity 来自 body/tool/profile/path | Change input role/path | 否。 |
| 用户声明 mounting surface | TagBinding | 是，且这是 canonical truth。 |
| 业务规则证明某面是 sealing surface | TagBinding + rule evidence | 是。 |
| 长度、半径、pattern index | typed property/metadata | 否。 |

Tag materialized cache 可以为性能复制 relation/property 的结果，但必须标记为 derived cache、可丢弃且不能成为 replay truth。Semantic Binding Schema 1.0 不定义此优化。

CADQL 中的 `semantic.role` 和 `semantic.group` 是 registry-backed TagBinding projection，例如从 `role.*` 和 `group.*` bindings 得到结构化视图，不建立第二份 writable storage。`semantic.material` 等具有独立 schema、互斥或结构化值的属性使用 typed semantic property，不同时编码为 tag。查询 provider必须从同一个 canonical owner求值这些属性。

### 4.2 Tag 只表达 unary categorical semantics

适合 tag 的内容：

```text
role.mounting_surface
role.sealing_surface
anchor.datum.primary
group.fasteners
process.inspect
```

不适合 tag 的内容：

```text
op.make_cut_rsolid.generated
origin.tool
face.area.245
edge.index.3
face.normal.+z
wire.outer
```

判断标准：如果完整含义需要 source、target、operation、frame、单位、置信度或多个参与者，它就不是单个 tag。

### 4.3 Evidence 不足时保持未知

Auto semantic rule 的三值结果为：

```text
PROVEN       所需 evidence 完整，允许发出 binding。
NOT_APPLICABLE 规则已完整求值，candidate 不满足。
UNKNOWN      evidence 或 capability 不足，禁止发出 binding。
```

`UNKNOWN` 不能被实现为 false、generated、preserved 或最佳猜测。Strict replay 中，如果 feature 依赖该 auto semantic，`UNKNOWN` 必须产生结构化错误；非依赖型装饰 semantic 可以只生成 diagnostic。

### 4.4 Query intent 与 execution evidence 分离

Target query 描述要标记谁；assignment evidence 描述某次执行为何解析到这些 entities。Replay 先重新执行 query，再比较 evidence。`TopoRef.topo_id` 和 geometry fingerprint 只属于 evidence，不是 TagBinding identity。

### 4.5 Semantic state 是版本化 shape view

`apply_tag_rselection` 不修改 geometry，但产生新的 semantic state version。相同 BRep entity 在 assignment 前后可以有不同 effective tags。CADQL provider 必须相对当前 scope producer/version 读取 bindings，不能从全局 mutable wrapper set 读取历史无关的并集。

## 5. Canonical 数据模型

### 5.1 TagDefinition

Tag token 继续使用 normalized dot-token 格式：

```text
[a-z][a-z0-9_-]*(.[a-z][a-z0-9_-]*)*
```

可选 registry 为已知 namespace 声明行为：

```json
{
  "tag": "role.mounting_surface",
  "namespace": "role",
  "value_kind": "categorical",
  "allowed_target_types": ["face"],
  "default_topology_propagation": "local",
  "default_lineage_policy": "continuation_fragment"
}
```

Registry 用于 validation 和文档，不拥有 assignment。未注册但格式合法的 custom tag 可以被允许，但必须显式提供 propagation 和 lineage policy，不能从字符串前缀静默猜测。

### 5.2 TagBinding

Canonical assignment：

```json
{
  "schema_version": "1.0",
  "binding_id": "tag_binding_mounting_surface",
  "tag": "role.mounting_surface",
  "producer": {
    "kind": "user_operation",
    "node_id": "node_tag_mounting_surface",
    "rule_id": null,
    "rule_version": null
  },
  "scope": {
    "node_id": "node_body",
    "output_slot": 0
  },
  "target": {
    "kind": "selection_query",
    "query_hash": "sha256:...",
    "binding_hash": "sha256:..."
  },
  "attachment": "local",
  "propagation": {
    "topology": "local",
    "lineage": "continuation_fragment"
  },
  "evidence": {
    "kind": "query_execution",
    "execution_hash": "sha256:...",
    "selected_refs": []
  },
  "certainty": "asserted",
  "lifecycle": "assertion"
}
```

字段语义：

| 字段 | Contract |
| --- | --- |
| `binding_id` | Assignment identity，不由 selected topology ID 生成。 |
| `tag` | Unary semantic token。 |
| `producer` | 用户 operation 或 versioned auto rule。 |
| `scope` | Target query 的 current snapshot/version boundary。 |
| `target` | Canonical Query IR binding 或仅用于 legacy import 的 explicit refs。 |
| `attachment` | 新 assignment 只允许 `local`；`inherited` 是计算结果。`effective_legacy` 仅用于迁移。 |
| `propagation.topology` | `local` 或显式 `downward`；`local` 表示不沿 topology传播。 |
| `propagation.lineage` | 允许沿哪些 derivation 计算 lineage visibility。 |
| `evidence` | Assignment execution witness，不参与 query intent hash。 |
| `certainty` | `asserted` 或 `proven`；猜测值不能进入 canonical bindings。 |
| `lifecycle` | replay 时重新解析、重新计算或保持 legacy snapshot。 |

### 5.3 TargetBinding

新 assignment 的 target 必须是：

```text
selection_query   canonical Query IR + runtime bindings
scope_root        lower 为选择当前 scope root 的 canonical query
```

以下 target 只用于迁移：

```text
explicit_refs     execution-local refs，无 semantic intent
legacy_effective  只有旧 flat tag snapshot
```

Auto rule 可以直接在 producer operation 的已知 Change outputs 上产生 target，但 serialization 时仍 lower 为 canonical source-preserving target：

- 引用 producer output variable 的 query；或
- 引用 versioned Change output set 的 internal binding。

不能只保存“当时第 3 个 Face”。

### 5.4 Producer

Producer kind：

```text
user_operation
auto_rule
imported_sidecar
legacy_import
```

Auto rule 必须保存稳定 `rule_id` 和 `rule_version`。修改 rule 语义必须提升 version；replay 可据此检测 semantic drift。

### 5.5 Evidence

Evidence 是 tagged union：

| Kind | 必需内容 | 适用场景 |
| --- | --- | --- |
| `user_assertion` | assignment node、authoring source | 用户明确声明。 |
| `query_execution` | query/binding/execution hash、selected refs | Query target assignment。 |
| `topology_change` | Change IDs、input/output witnesses、coverage | 基于 lineage 的 auto rule。 |
| `geometry_classification` | algorithm/version、frame、tolerance、measured properties | 几何分类规则。 |
| `imported_sidecar` | source URI/hash/schema | 外部 semantic data。 |
| `legacy_snapshot` | imported tags、migration diagnostic | 旧模型兼容。 |

Evidence 可以证明 assignment，但不会把几何 fingerprint 升级为 durable target identity。

## 6. Tag Scope 的正式语义

### 6.1 Local

`local` 返回当前 semantic state version 中，target query 直接匹配该 entity/use 的 bindings。

```text
local(e, v) = {b.tag | binding b is visible in semantic version v
                       AND target(b, v) contains e}
```

它不包含 topology parent、model entity 或 lineage ancestor 的 tag。

### 6.2 Inherited

`inherited` 只来自显式 topology propagation policy：

```text
inherited(e, v) = bindings attached to ancestor a
                  where topology propagation is downward
                  and contains-path(a, e) is valid in snapshot v
```

规则：

- 不再根据 `role.*`、`anchor.*`、`group.*` 前缀自动决定传播。
- Propagation 在 assignment 时显式冻结并序列化。
- Downward 传播计算于 Current BRep containment，不复制字符串。
- 默认是 `local`，即不传播。
- 给 Solid 标记 `role.mounting_plate` 不应默认让每条 Edge 都成为 mounting plate。
- 若确实表达 assembly/model membership，优先使用 model relation 或显式 group binding；不要依靠 topology descendants 模拟产品结构。

### 6.3 Effective

```text
effective(e, v) = local(e, v) union inherited(e, v)
```

`effective` 不自动包含 lineage。这样 current snapshot 内的 attachment semantics 与跨 operation ancestry 保持正交。

### 6.4 Lineage

`lineage` 通过 TagBinding 与 Topology Evolution Graph 联合计算：

```text
lineage(e, v) = source bindings whose tagged entities are reachable
                through allowed Change output derivations
```

默认 policy：

| Policy | 允许 derivation | 说明 |
| --- | --- | --- |
| `none` | 无 | 不跨 operation 可见。 |
| `continuation` | `CONTINUATION` | 只接受同角色延续。 |
| `continuation_fragment` | `CONTINUATION`、`FRAGMENT` | 允许 trim/split fragments。 |
| `explicit` | assignment 指定集合 | 允许 `MERGE`/`REPLACEMENT` 等业务定义。 |

`INTERSECTION` 和 `BOUNDARY` 默认不继承 source tag，因为新 entity 是由 source 参与生成，不等于 source 语义角色的延续。需要选择这类结果时使用 `generated_from`、`depends_on` 或 `cadql.change(...)`。`MERGE`/`REPLACEMENT` 也不默认继承，除非 assignment 显式声明。

`lineage` scope 只返回 lineage-derived tags；调用方若需要本地与 lineage 并集，应显式组合 predicates，不把 `effective` 的含义扩大。

History capability 为 `NONE` 或所需 path evidence 不完整时，请求 `lineage` 必须产生 `UnsupportedQueryCapabilityError`，不能返回空集冒充“没有 tag”。

### 6.5 TopoUse

TagBinding 可以 target entity 或 oriented use：

- Entity tag 对同一 underlying entity 的所有 occurrences 可见。
- TopoUse tag 只对该 parent/orientation/occurrence 可见。
- TopoUse 的 inherited 与 lineage 依赖 use-level containment/evolution evidence。
- 缺少 use ancestry 时不能把 entity lineage tag 冒充 occurrence lineage tag。

## 7. Public API 与 Operation Graph

### 7.1 用户赋值

保留简单入口：

```python
apply_tag(body, "role.mounting_plate")
```

新 schema 中该 convenience API 的固定默认值是：

```text
topology_propagation = LOCAL
lineage_policy = CONTINUATION_FRAGMENT
```

因此它不会把 Solid 的 role 复制给所有 Face/Edge，但在 backend 提供完整 `CONTINUATION`/`FRAGMENT` evidence 时，该 assertion 可以通过 `scope="lineage"` 从后续版本查询。需要 topology downward inheritance 时必须调用带显式 policy 的 `apply_tag_rselection`。迁移期执行旧 model时可以保留旧 effective结果，但新 assignment不能继续按token prefix选择policy。

它 lower 为 scope-root query 和 canonical operation：

```text
apply_tag_rselection(
    scope: Shape<K>,
    targets: SelectionSet<T>,
    tag: Tag,
    topology_propagation: LOCAL | DOWNWARD,
    lineage_policy: NONE | CONTINUATION | CONTINUATION_FRAGMENT | EXPLICIT,
) -> Shape<K>
```

推荐的精确赋值：

```python
mounting_face = (
    cadql.select(cadql.Face, in_=body)
    .where(
        cadql.surface_type.eq("plane")
        & cadql.normal.same_direction_as(
            (0, 0, 1),
            relative_to=body,
            angle_tolerance=cadql.deg(0.1),
        )
    )
    .expect_one()
)

tagged_body = apply_tag_rselection(
    body,
    targets=mounting_face,
    tag="role.mounting_surface",
    topology_propagation="local",
    lineage_policy="continuation_fragment",
)
```

Active `GraphSession` 必须记录 target Query IR 和 binding，不能只记录 resolved Face refs。

### 7.2 读取

CADQL 是 canonical query API：

```python
cadql.select(cadql.Face, in_=body).where(
    cadql.tag("role.mounting_surface", scope="effective")
)
```

`list_tags(shape)` 可以保留为 current wrapper convenience，但默认返回当前 version 的 `effective` tags，并应允许显式 scope：

```python
list_tags(shape, scope="local")
list_tags(shape, scope="effective")
list_tags(shape, scope="lineage")
```

它不得绕过 provider 从 `_tags` 直接读取。迁移期旧签名等价于 `scope="effective"`。

### 7.3 删除和替换

Tag 删除不是从 entity set 中 `discard()` 字符串，而是产生新的 semantic operation，撤销或 supersede 指定 binding：

```text
remove_tag_rselection(scope, targets, tag, matching_producer?) -> Shape<K>
```

默认不能静默删除其他 producer 的同名 binding。例如移除 auto-rule binding 不应删除用户 assertion。

### 7.4 Conflict semantics

同一个 entity 可同时存在多个 producer 的同名 tag，查询结果按 token 去重，但 evidence/projection 保留所有 bindings。

Tag 1.0 不定义基于命名约定的互斥，例如 `state.open` 与 `state.closed`。真正互斥的数据应使用 typed enum property。若产品域 registry 声明 tag group 互斥，assignment validation 必须报告 conflict，不能按“最后写入者获胜”处理。

## 8. Auto Semantics Rule Contract

### 8.1 Rule schema

每条规则必须声明：

```json
{
  "rule_id": "simplecad.primitive.box.face_roles",
  "rule_version": "1.0",
  "trigger": "make_box_rsolid",
  "candidate_type": "face",
  "required_capabilities": [
    "operation_output_roles",
    "oriented_face_geometry"
  ],
  "required_evidence": {
    "history": "operation_native",
    "frame": "operation_context",
    "coverage": "complete"
  },
  "output": {
    "kind": "tag_binding",
    "allowed_tags": ["role.cap.start", "role.cap.end", "role.side"]
  },
  "unknown_policy": "diagnostic",
  "lifecycle": "recompute"
}
```

Rule evaluator 返回：

```text
bindings
status: PROVEN | NOT_APPLICABLE | UNKNOWN
evidence
diagnostics
coverage
```

### 8.2 权威等级

| Level | Source | 可产生的结果 |
| --- | --- | --- |
| 1 | 用户显式 assertion/imported authoritative sidecar | `certainty=asserted` binding。 |
| 2 | Kernel/operation-native topology history | Change graph；满足业务规则时可产生 `certainty=proven` binding。 |
| 3 | Exact current topology fact | topology property/relation；通常不 materialize 为 tag。 |
| 4 | Deterministic geometry classifier | typed geometry property；只有注册业务映射后才能产生 tag。 |
| 5 | Heuristic/fingerprint | diagnostic/evidence only。 |

低等级 evidence 不能覆盖或伪装为高等级事实。尤其 geometry proximity 不能产生 preserved/generated lineage。

### 8.3 Coverage

每个 rule evaluation 必须声明：

```text
COMPLETE    候选 universe 与所需 evidence 完整。
PARTIAL     只有部分 candidates/relations 有 evidence。
NONE        无法求值。
```

只有 `COMPLETE` 且 rule 对具体 candidate 得到 `PROVEN` 时才发出需要全局排他性的 tag，例如“唯一 start cap”。`PARTIAL` 不能通过给其余 candidates 标记 opposite role 来补齐结果。

### 8.4 禁止行为

以下规则在新系统中非法：

- unmatched result entity => `generated`。
- pure-preserve delta => 所有 result entities preserved，而无逐实体 mapping。
- backend enumeration index => semantic tag。
- geometry look-alike => lineage continuation。
- 将 operation 名、event 和 origin role拼接为 tag作为唯一事实。
- 给所有 descendants 无条件复制 `role.*`。
- 多来源 Change => 只保留一个 `origin.*` 字符串。
- rule 失败后静默回退到 fingerprint 并仍标记 `proven`。

## 9. Operation-by-Operation 策略

### 9.1 Primitive

Primitive operation 自己知道构造参数和 output roles，优先使用 operation-native evidence，而不是事后猜测几何。

| 当前输出 | 新 canonical 表达 |
| --- | --- |
| `geom.primitive.box` | `provenance.operation_type == make_box_rsolid` 或 typed semantic metadata，不需要 tag。 |
| 裸 `box` | 删除。 |
| `face.top/bottom/front/...` | 不自动作为 world-direction tag。使用 geometry predicate + explicit frame。 |
| `face.surface` | `geometry.surface_type`。 |

如果产品 API 需要稳定 feature role，可定义 frame-aware operation role：

```text
role.cap.start
role.cap.end
role.side
```

这些角色必须绑定 primitive 的参数方向和 operation context，并保存 rule evidence。对于 box 的四个侧面，如果没有额外业务区别，不自动命名 front/back/left/right；数学对称性应保留为集合。

Cone 必须与 cylinder 使用同一 role contract，不再因为当前实现遗漏 `auto_tag_faces()` 而表现不同。

### 9.2 Extrude 和 Revolve

Feature provenance 和 topology evolution进入 Change graph：

- Profile Face/Coedge 是 `subject` 或 `support` input。
- Start/end continuation、side/boundary outputs使用 event + derivation表示。
- `face.extrusion.start/side/end` 若保留为用户友好 semantic，必须由 operation-native role mapping产生 TagBinding，不使用 center exact equality或 normal exact equality。
- `solid.extrusion` 改为 `provenance.operation_type`，不作为 tag。
- Revolve 使用相同 Change contract；full/partial revolve 的 caps必须按实际 operation evidence处理。

推荐 query：

```python
side_faces = (
    cadql.select(cadql.Face, in_=extruded)
    .where(
        cadql.related(
            cadql.generated_from,
            from_=cadql.this,
            to=profile_boundary,
            derivations=("boundary",),
            depth=1,
        )
    )
)
```

只有业务代码确实需要可命名的 feature role 时才额外发出 `role.extrusion.side`。

### 9.3 Boolean

Boolean 不再产生 canonical `op.*` 或 `origin.*` tags。

必须记录：

- 每个 operand 的 named input port。
- 每个 source entity 的 role：`subject`、`tool`、`support` 或 `context`。
- 每个 output entity 的 event 和 derivation。
- Intersection Edge 的多 source Change witness。

交界 edge 使用：

```python
cadql.change(
    inputs=(
        cadql.change_input(subject_faces, input_port="subjects", role="support"),
        cadql.change_input(tool_faces, input_port="tools", role="tool"),
    ),
    output=cadql.this,
    derivation="intersection",
)
```

不能用 `role.section_face` 替代 Edge-level `INTERSECTION` Change。若产品域确实定义“section interface”业务角色，可在上述 query 上显式应用 tag；该 tag 的 target intent仍是 Change pattern。

多步 cut/intersect 必须保留每一步 Change，不能简单拼接 event buckets 后覆盖相同 `topo_id` 的 `delta_entries`。

### 9.4 Fillet、Chamfer 和 Shell

这些 feature 的核心是 target selection 与 Change graph：

- 用户选择的 Edge/Face 是 `target` input。
- 邻接 support Face 是 `support` input。
- Trimmed source entities 是 `CONTINUATION`/`FRAGMENT` output。
- Transition Face 和新 boundary Edge 是 `BOUNDARY` output。
- 完全消耗的 source entity保留为 historical input与 `DELETED` output event。

默认不产生 `op.fillet.generated` 等 tag。查询 transition geometry 应使用 `generated_from`、`depends_on` 和 `co_result_of`。

用户已有 `role.mounting_surface` 的 source Face，只沿 `CONTINUATION`/`FRAGMENT` 进入 lineage scope；fillet transition Face 不自动继承该角色。

### 9.5 Transform 和 Mirror

Rigid transform 不改变 topology role，但必须提供逐 entity/use `CONTINUATION` mapping。只有 mapping complete 时 lineage tag 才可查询。

- `solid.transform.mirrored` 改为 provenance/operation property。
- 不复制 source wrapper `_tags`。
- Mirror 的 orientation-sensitive TopoUse/normal 必须在新 parent occurrence和 frame中重新求值。
- 没有逐实体 mapping 时 history capability 为 `PARTIAL`，不能把所有 Face声明 preserved。

### 9.6 Loft 和 Sweep

Loft/sweep 必须首先修复 evidence kind mismatch：

- Profile/path Edge history进入 Change graph。
- Result Face/Edge 与 profile/path source的关系必须由 operation-native adapter提供。
- Auto semantic evaluator按 candidate type消费对应 Change outputs，不允许 Face-only fallback。
- Profile 与 path 是不同 input ports/roles，不能把二者 tags union到 result Solid后丢失来源。

如果 backend只能提供 Edge-level partial history，Face lineage query与依赖它的 auto rule必须报告 unsupported/unknown；不能给全部 Faces标记 generated。

### 9.7 Pattern

Pattern 应有显式 Pattern operation 和 instance output relation：

```text
source EntityVersion -> Change(instance identity) -> instance EntityVersion
```

每个 instance 保存稳定 operation-local `instance_key`，index只作为 typed property：

```text
provenance.pattern_instance_key
provenance.pattern_ordinal
```

`solid.pattern.linear/radial` 改为 operation provenance，不是 semantic tag。Source tags通过 `CONTINUATION` lineage policy可见；不要复制到每个 instance wrapper。

对完全对称的 instances，若没有用户 tag或业务 key，CADQL返回集合或 ambiguity，不用 ordinal伪造 semantic identity。

### 9.8 Sketch Promotion

Sketch entity到 BRep Edge的映射是 source binding，不是 tag naming问题：

- Sketch entity/profile使用稳定 semantic refs。
- Promotion adapter记录每个 output Edge对应的 source entity ref和 evidence。
- `sketch.*`、`sketch_profile.*`、`sketch_entity.*` 不再作为唯一 mapping。
- 禁止仅通过 `zip(edges, entity_ids)` 声称 correspondence。
- 用户附着在 sketch entity上的 semantic tag可通过 proven promotion Change在 `lineage` scope查询。

## 10. Topology、Geometry、Provenance 与 Tag 的迁移表

| 现有 tag/数据 | 新位置 | 迁移行为 |
| --- | --- | --- |
| `wire.outer`/`wire.inner` | `topology.loop_role` on WireUse/Coedge | 不导入为 semantic tag。 |
| `edge.boundary` | `boundary_uses` + `use_entity` | 不导入为 semantic tag。 |
| `face.top/bottom/...` | Legacy effective tag；新模型使用 frame-aware geometry query或 explicit role binding | 导入并警告方向语义未声明。 |
| `face.face_N` | Legacy enumeration annotation | 不生成新 binding；仅保留 migration evidence。 |
| `geom.primitive.*` | `provenance.operation_type`/typed metadata | 可保留 legacy effective，不再新发出。 |
| `op.<op>.<event>` | Change output event + performed_by Operation | 不生成新 binding。 |
| `origin.<role>` | Change input role/path | 不生成新 binding。 |
| `solid.boolean.*` | Operation provenance | 不生成新 binding。 |
| `solid.pattern.*` | Pattern provenance/property | 不生成新 binding。 |
| `role.*` 用户 tag | TagBinding | 尽可能恢复 assignment；否则 `effective_legacy`。 |
| `anchor.*` 用户 tag | TagBinding | 同上。 |
| `group.*` 用户 tag | TagBinding 或 model membership relation | 按 domain schema迁移。 |
| Numeric/index tags | typed metadata/property | 不作为 semantic binding。 |

## 11. Legacy 兼容

旧模型只有 flat tags时，导入为：

```json
{
  "producer": {"kind": "legacy_import"},
  "target": {"kind": "legacy_effective", "refs": []},
  "attachment": "effective_legacy",
  "propagation": {"topology": "local", "lineage": "none"},
  "certainty": "asserted",
  "lifecycle": "snapshot",
  "evidence": {"kind": "legacy_snapshot"}
}
```

Provider 只把 `effective_legacy` 暴露给 `scope="effective"`。它不能回答 local、inherited 或 lineage，并产生 migration diagnostic；该 attachment不是正常assignment可写入的值。

兼容规则：

- 旧 public `list_tags()` 继续看到原 effective tokens。
- 旧 QL tag predicate可由 adapter lower 为 CADQL `effective` predicate。
- 不从 token prefix反推旧 propagation。
- 不从 `op.*`/`origin.*` 反向构造可信 Change graph。
- 如果 graph中同时有真实 TopoDelta evidence，可以独立迁移为 Change；仍不能仅依据旧 tag补齐缺失 parent mapping。

## 12. Serialization 与 Provider Contract

Model schema 3.0 增加：

```text
semantic_bindings: TagBinding[]
semantic_rules: AutoSemanticRuleRef[]
semantic_diagnostics: SemanticDiagnostic[]
```

Operation node可以引用其产生的 binding IDs。TagBinding target query复用 model顶层 `query_objects`，不嵌入语义缩水的第二份 query。

Provider 增加：

```python
class SemanticProvider(Protocol):
    def bindings(self, scope_version, entity_or_use) -> Sequence[TagBinding]: ...
    def tags(self, entity_or_use, scope: TagScope) -> Sequence[str]: ...
    def explain_tag(self, entity_or_use, tag: str, scope: TagScope) -> Sequence[TagWitness]: ...
```

`explain_tag()` 至少返回：

```text
binding_id
producer
attachment path
topology inheritance path, if any
lineage Change path, if any
evidence status
diagnostics
```

OCP 和 FreeCAD provider必须运行同一 scope和rule conformance suite。Backend不支持某 rule所需 capability时报告 unknown/unsupported，不自行更换算法。

## 13. Invalidation 与 Replay

TagBinding lifecycle：

| Lifecycle | Replay behavior |
| --- | --- |
| `recompute` | 重跑 target query或auto rule，生成新 evidence并比较 drift。 |
| `assertion` | 重跑 target query；用户 semantic保留，但 query不再满足时失败。 |
| `snapshot` | 仅 legacy/import sidecar；不能声称动态 lineage。 |

参数变化后：

1. 重建 geometry和 Change graph。
2. 重新解析 assignment target query。
3. 重新运行 versioned auto rules。
4. 撤销本次 replay中不再 proven的 derived bindings。
5. 比较旧/新 evidence并生成 drift diagnostic。
6. Feature依赖的 semantic target违反 cardinality时按 CADQL错误模型失败。

Derived auto binding不能因为曾经写入 wrapper set而永久残留。Semantic state由当前有效 bindings重新计算，不执行增量字符串清理猜测。

## 14. 错误与诊断

新增结构化错误：

| Error | 条件 |
| --- | --- |
| `TagValidationError` | token、target type、policy或registry不合法。 |
| `TagTargetResolutionError` | Assignment target query无法满足 cardinality。 |
| `SemanticConflictError` | Registry定义的互斥 semantic同时成立。 |
| `AutoSemanticEvidenceError` | Strict dependency所需rule evidence为UNKNOWN/PARTIAL。 |
| `SemanticCapabilityError` | Provider不能计算请求的tag scope或rule。 |
| `SemanticDriftError` | Strict replay中assignment/rule结果发生不允许的漂移。 |

Diagnostic 至少包含：

```text
binding_id/rule_id
scope version
required and available capability
coverage
candidate count
missing witnesses
repair suggestions
```

## 15. 测试策略

### 15.1 Binding tests

- TagBinding JSON round-trip和stable hash。
- 同名tag、不同producer不会互相覆盖。
- Target query intent与execution refs分离。
- Remove/supersede只影响指定binding。

### 15.2 Scope tests

- local不包含parent和lineage tags。
- inherited只沿显式downward policy计算。
- effective严格等于local union inherited。
- lineage只沿允许的derivations计算。
- `BOUNDARY`/`INTERSECTION` 默认不继承source role tag。
- history缺失时lineage产生capability error而不是空结果。
- entity tag和TopoUse tag保持不同visibility。

### 15.3 Auto rule precision/recall

- 每个emitted binding有required evidence witness。
- 可证明的semantic不会遗漏。
- Unmatched candidate不会得到generated/preserved tag。
- Partial coverage不会产生排他性role。
- Rule version变化产生semantic drift diagnostic。

### 15.4 Operation fixtures

- Primitive roles使用operation frame，不依赖world axis或Face枚举。
- Extrude/revolve caps和sides使用operation-native mapping。
- Boolean interface保留多input Change，Edge evidence不被当作Face。
- Fillet/chamfer source fragments、transition Faces和boundaries可通过evolution relation选择。
- Transform/mirror有逐entity continuation mapping。
- Loft/sweep在只有Edge evidence时拒绝Face lineage assertion。
- Pattern instances保留source lineage和instance key，不以ordinal作为semantic identity。
- Sketch promotion不依赖zip/enumeration order。

### 15.5 Replay与translator

- OCP和FreeCAD的tag scopes一致。
- Model JSON round-trip后producer/evidence/policies不丢失。
- 参数变化后过期auto bindings消失。
- Legacy effective tags仍可查询，但local/inherited/lineage明确unsupported。

## 16. 实施阶段

### Phase A：Characterization 与止损

- 锁定当前public tag行为和serialized fixtures。
- 给unmatched-to-generated、section Edge/Face mismatch、loft/sweep mismatch增加failing characterization tests。
- 停止新增`op.*`、`origin.*`和enumeration-derived tags。
- `apply_tracking_tags()`增加diagnostic mode，逐步取消unsound fallback。

退出标准：所有已知误报都有测试，不再扩大flat-tag contract。

### Phase B：Semantic Binding Schema

- 实现TagBinding、producer、target、policy、evidence和serialization。
- 实现semantic state version与binding store。
- `apply_tag_rselection`记录target Query IR。
- Flat `_tags` 暂时作为effective cache，不再是canonical truth。

退出标准：用户assignment可JSON round-trip并解释来源。

### Phase C：CADQL Scope Provider

- 实现local/inherited/effective。
- 移除prefix-driven runtime copying；迁移为binding-time explicit policy。
- 实现`explain_tag()`。
- Legacy tags仅通过effective adapter暴露。

退出标准：三个current-snapshot scopes通过OCP conformance tests。

### Phase D：Topology Evolution Graph

- 按CADQL设计建立完整Change inputs/outputs。
- 将`delta_entries`合并进canonical序列化schema。
- 修复Face-only consumer、section Edge、transform correspondence和多步Change。
- 实现lineage scope与history capability validation。

退出标准：continuation/fragment/boundary/intersection fixtures可查询且缺证据时失败。

### Phase E：Auto Semantic Rules

- 引入versioned rule registry和三值求值。
- 先迁移primitive与extrude roles，再迁移其他feature。
- 删除unmatched-generated和operation/origin tags的canonical生成。
- Geometry heuristic仅作为typed property或diagnostic。

退出标准：每个auto binding都有rule、evidence、coverage和replay lifecycle。

### Phase F：Translator 与清理

- FreeCAD provider实现相同semantic binding/scope contract。
- 更新docs、skills和examples到CADQL tag query。
- Deprecate `Solid.auto_tag_faces()`和内部直接`_tags`复制。
- 删除flat tag作为truth的代码路径。

退出标准：OCP/FreeCAD semantic conformance一致，新model不依赖flat tags。

## 17. 推荐决策

1. 采用`TagBinding`作为唯一canonical tag assignment；`_tags`只能是迁移期effective cache。
2. Tag仅表达用户/业务域的unary categorical semantics。
3. `wire.outer`、`edge.boundary`迁移到Current BRep properties/relations。
4. `op.*`、`origin.*`、preserved/modified/generated迁移到Operation/Topology Evolution Graph。
5. 几何类型、方向、数值和pattern ordinal迁移到typed properties，不再自动materialize为tag。
6. Downward propagation默认关闭并在每个binding中显式保存；不再按prefix复制字符串。
7. `effective = local union inherited`；lineage保持独立scope并依赖完整Change evidence。
8. Lineage默认只允许`CONTINUATION`/`FRAGMENT`；`BOUNDARY`、`INTERSECTION`、`MERGE`和`REPLACEMENT`不自动继承semantic role。
9. Auto semantics使用versioned、evidence-gated、三值规则；`UNKNOWN`是一等结果。
10. 立即禁止unmatched => generated、enumeration => semantic role、geometry guess => proven history。
11. 所有tag target复用`cadql.select(...)`和Query IR，不建设第二套selector或anchor API。
12. Replay和translator必须保存并解释assignment intent、producer、scope、evidence和drift，不能只搬运最终字符串集合。

这套策略的核心不是让auto tagging覆盖更多实体，而是让每个可查询semantic都有明确作者、目标意图、适用scope、证明依据和失效规则。CADQL负责查询这些事实；Current BRep Graph和Topology Evolution Graph负责证明结构与历史；TagBinding只负责承载真正的semantic assertion。
