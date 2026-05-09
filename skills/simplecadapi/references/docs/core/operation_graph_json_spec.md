# SimpleCADAPI JSON Operation Graph Spec

本文档定义 SimpleCADAPI 当前用于导出、交换、replay、以及外部转译适配的 JSON 规范。

目标读者：

- 需要消费 `export_graph_json()` / `export_model_json()` 输出的适配器开发者
- 需要把当前 JSON 图转译到其他 CAD / DSL / workflow 系统的实现者
- 需要确认字段语义、版本边界、以及节点参数格式的集成方

本文档描述的是当前实现行为，而不是理想化设计稿。外部适配请以本文档和当前测试为准。

## 1. Scope

当前存在两类相关 JSON 载荷：

1. `graph JSON`
   - 由 `export_graph_json(graph)` 导出
   - 表示 API 级操作图
   - `schema_version` 当前为 `1.0`
   - 适合轻量 roundtrip、节点级检查、简单 replay

2. `model JSON`
   - 由 `export_model_json(session)` 导出
   - 表示完整 2.0 interchange payload
   - `schema_version` 当前为 `2.0-draft`
   - 包含 `graph`、`leaf_ids`、`expression_graph`、`frame_graph`、registry/log 等附加信息
   - 是当前对外推荐的 interchange / replay 边界

## 2. Versioning And Compatibility

### 2.1 graph JSON

- 导出版本：`schema_version = "1.0"`
- 导入兼容规则：`import_graph_json()` 仅接受 `1.x`
- 也就是说，适配器应把 graph payload 视为 `1.x` 系列 schema

### 2.2 model JSON

- 导出版本：`schema_version = "2.0-draft"`
- 导入兼容规则：`import_model_json()` 接受任何 `2.0*` 前缀
- 当前 canonical contract 版本：`canonical_contract.contract_version = "2.0-final-state"`

### 2.3 Producer Version

- `producer_version` 是 Python package 版本号
- 它用于调试和排查，不应用作 schema 判断依据

## 3. High-Level Data Model

### 3.1 graph

`graph` 是唯一真相源的 canonical low-level graph。

特点：

- 必须限制在冻结的 canonical op set 内
- 不能泄漏 convenience-only 或 macro-only op
- composite builtin 可以内部构造表达式和 low-level 调用，但最终写入图中的节点只能是 low-level op

典型结果：

- `make_box` -> rectangle face chain + `extrude`
- `make_circle_face` -> `make_circle_edge` + `make_wire_from_edges` + `make_face_from_wire`
- `linear_pattern` -> 多个显式 `translate`
- `radial_pattern` -> 多个显式 `rotate`
- `helical_sweep` 不会作为独立 core node 出现

### 3.2 leaf_ids

`leaf_ids` 是最终结果集的显式 node id 列表。

规则：

- 多输出场景不能依赖 `graph.leaf_nodes()` 猜测最终结果
- `leaf_ids` 是模型导出时的显式返回集合

### 3.3 expression_graph

`expression_graph` 记录参数表达式 DAG。

规则：

- `params` 中保存的是数值快照
- 若某参数来自 `var(...)` / `Expr`，则 `param_exprs` 中会保存到 expression node 的引用
- 适配器如果只做纯几何转译，可以只消费 `params`
- 适配器如果需要恢复参数化关系，应同时消费 `param_exprs + expression_graph`

### 3.4 frame_graph

`frame_graph` 记录每个 operation node 在记录时的坐标系快照。

规则：

- 每个记录节点通常对应一个 `frame:<node_id>` frame
- 这是重建工作平面 / 本地坐标环境的重要辅助信息
- 当前 replay 实现本身主要依赖节点参数，不直接依赖 frame_graph
- 但外部转译器可使用它恢复局部工作坐标语义

## 4. graph JSON Schema

`export_graph_json()` 的顶层对象结构如下：

```json
{
  "schema_version": "1.0",
  "producer_version": "2.0.0b1",
  "capabilities": {
    "selection_ref_strategies": true,
    "selector_hint_fallback": true,
    "display_payload": true,
    "topology_delta_summary": false,
    "assembly_graph": false,
    "scalar_field_graph": true,
    "expression_graph": true
  },
  "graph_id": "graph_xxxxxxxx",
  "nodes": [...],
  "edges": [["src_node_id", "dst_node_id"]]
}
```

### 4.1 Top-Level Fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `string` | yes | graph schema version, current `1.0` |
| `producer_version` | `string` | yes | package version of exporter |
| `capabilities` | `object` | yes | feature flags for downstream consumers |
| `graph_id` | `string` | yes | unique graph instance id |
| `nodes` | `array<object>` | yes | operation nodes in topological order |
| `edges` | `array<[string,string]>` | yes | adjacency list, each entry is `[src, dst]` |

### 4.2 capabilities

当前导出固定包含以下字段：

| Field | Type | Meaning |
| --- | --- | --- |
| `selection_ref_strategies` | `bool` | detail feature 支持显式 topo refs / index / query 等多种选择策略 |
| `selector_hint_fallback` | `bool` | replay 时支持 selector hint 近似匹配回退 |
| `display_payload` | `bool` | node 中包含 `display` 字段 |
| `topology_delta_summary` | `bool` | 当前为 `false`，表示没有额外 summary-only delta schema |
| `assembly_graph` | `bool` | 当前 graph JSON 本身不承载 assembly graph |
| `scalar_field_graph` | `bool` | `make_field_surface` 支持记录 scalar field tree |
| `expression_graph` | `bool` | session/model payload 支持 expression graph |

## 5. Operation Node Schema

`nodes[]` 中每个元素是一个 operation node。

### 5.1 Base Shape

```json
{
  "node_id": "node_xxxxxxxx",
  "op": "extrude",
  "params": {...},
  "inputs": ["node_a", "node_b"],
  "output_count": 1,
  "tags": [],
  "display": {...},
  "param_exprs": {...},
  "context": {...},
  "semantic_delta": {...},
  "topo_delta": {...}
}
```

### 5.2 Field Semantics

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `node_id` | `string` | yes | unique node id within graph |
| `op` | `string` | yes | operation type |
| `params` | `object` | yes | replay / interchange parameter payload |
| `inputs` | `array<string>` | yes | upstream node ids in data-flow order |
| `output_count` | `int` | yes | number of shape outputs produced by this node |
| `tags` | `array<string>` | yes | free-form labels attached at record time |
| `display` | `object` | yes | UI-friendly derived summary; advisory only |
| `param_exprs` | `object` | no | mapping from param name to expression references |
| `context` | `object` | no | workplane / coordinate system snapshot |
| `semantic_delta` | `object` | no | semantic entity delta |
| `topo_delta` | `object` | no | topology lineage delta |

### 5.3 Node Invariants

适配器应假设并维持以下不变量：

1. `nodes` 按拓扑序输出
2. `inputs` 中的 node id 必须已在更早节点中出现
3. `edges` 与 `inputs` 表达同一依赖关系，二者必须一致
4. `output_count >= 1`
5. 多输出节点的输出 slot 范围是 `[0, output_count - 1]`

### 5.4 display

`display` 是冗余的、面向 UI 的派生字段，不是 replay 所必需。

当前结构：

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `label` | `string` | yes | 例如 `Box`、`Fillet` |
| `category` | `string` | yes | `primitive` / `profile` / `feature` / `boolean` / `detail` / `transform` / `pattern` / `operation` |
| `summary` | `string` | yes | 基于 `params` 自动生成的短摘要 |
| `selection_count` | `int` | no | 当 `selected_edges` 或 `selected_faces` 存在时出现 |

消费建议：

- 可直接忽略 `display`
- 不要把 `display.summary` 当成结构化数据来源

### 5.5 context

当前 `context` 形状：

```json
{
  "origin": [0.0, 0.0, 0.0],
  "x_axis": [1.0, 0.0, 0.0],
  "y_axis": [0.0, 1.0, 0.0],
  "z_axis": [0.0, 0.0, 1.0]
}
```

字段含义：

- `origin`: 当前局部坐标系原点
- `x_axis`: 当前局部 X 轴方向
- `y_axis`: 当前局部 Y 轴方向
- `z_axis`: 当前局部 Z 轴方向

### 5.6 param_exprs

`params` 保存已求值后的数值；`param_exprs` 保存哪些参数来自表达式图。

示例：

```json
{
  "params": {
    "radius": 2.0
  },
  "param_exprs": {
    "radius": {
      "expr_id": "var_119b16e4"
    }
  }
}
```

规则：

- 如果某个参数没有表达式来源，则 `param_exprs` 中没有该键
- 离散索引参数不会被表达式提升，例如：
  - `selected_edge_indices`
  - `selected_face_indices`
  - `count`
  - `edge_count`
  - `profile_count`
  - `output_count`

注意：

- 由于 canonicalize 规则，非离散标量通常会变成 JSON number，当前实现多数会导出成浮点数
- 即使原始输入是整数，也不要假设它一定以 integer 形式出现

## 6. Semantic Delta Schema

`semantic_delta` 表示语义实体层面的变化。

结构：

```json
{
  "created": [SemanticRef, ...],
  "modified": [SemanticRef, ...],
  "deleted": [SemanticRef, ...],
  "metadata": {...}
}
```

### 6.1 SemanticRef

```json
{
  "graph_id": "graph_xxx",
  "node_id": "node_xxx",
  "entity_type": "Feature",
  "entity_id": "extrude:0"
}
```

字段含义：

| Field | Type | Meaning |
| --- | --- | --- |
| `graph_id` | `string` | 所属 graph id |
| `node_id` | `string` | 产生该语义实体的 node id |
| `entity_type` | `string` | 语义实体类型，如 `Body` / `Feature` / `Sketch` / `Profile` / `Point` / `ShapeOutput` / `AssemblyConstraint` |
| `entity_id` | `string` | 在 node 内部稳定的实体 id，通常是 `<op>:<slot>` |

### 6.2 Current Entity Type Mapping

当前实现的默认映射如下：

- `make_point` -> `Point`
- 草图/轮廓类节点 -> `Profile` 或 `Sketch`
- primitive solid / transform body -> `Body`
- feature / detail / boolean 类节点 -> `Feature`
- 无法分类时 -> `ShapeOutput`

其中：

- `make_*_face` 与 `make_face_from_wire` -> `Sketch`
- `make_*_edge` / `make_*_wire` -> `Profile`
- `extrude` / `revolve` / `loft` / `sweep` / `fillet` / `chamfer` / `shell` / `cut` / `union` / `intersect` -> `Feature`

## 7. Topology Delta Schema

`topo_delta` 表示子拓扑级别的 lineage 变化。

结构：

```json
{
  "preserved": [TopoRef, ...],
  "modified": [TopoRef, ...],
  "generated": [TopoRef, ...],
  "deleted": [TopoRef, ...],
  "section_edges": [TopoRef, ...],
  "entries": [TopoEntry, ...],
  "raw_event": {...}
}
```

### 7.1 TopoRef

```json
{
  "graph_id": "graph_xxx",
  "node_id": "node_xxx",
  "output_slot": 0,
  "kind": "EDGE",
  "topo_id": "edge_640974"
}
```

字段含义：

| Field | Type | Meaning |
| --- | --- | --- |
| `graph_id` | `string` | 所属 graph id |
| `node_id` | `string` | 产生该 subshape 的 node id |
| `output_slot` | `number` | 对应 node 输出槽位；消费端应按整数解释 |
| `kind` | `string` | `VERTEX` / `EDGE` / `WIRE` / `FACE` / `SOLID` |
| `topo_id` | `string` | 当前实现生成的 opaque subshape id |

注意：

- `output_slot` 在 node-level topo refs 中通常是整数
- 但当 `TopoRef` 被嵌入 `params.selected_edges[]` 等深层对象并经过参数 canonicalize 后，可能表现为 `0.0`
- 消费端应将其按整数语义处理

### 7.2 TopoEntry

当前 schema 支持 richer entry，但多数情况下 `entries` 为空数组。

结构：

```json
{
  "ref": TopoRef,
  "event": "GENERATED",
  "origin_role": "tool",
  "parent_refs": [TopoRef, ...],
  "metadata": {...}
}
```

### 7.3 Topology Delta Notes

- 当前 `raw_event` 为保留字段，通常为空对象
- 许多 primitive node 没有 `topo_delta`
- 追踪型 feature / boolean node 更可能包含 `topo_delta`

## 8. Selection Reference Schema

detail feature 使用显式选择引用来稳定 replay。

### 8.1 Canonical Contract

`model.json.canonical_contract.selection_ref_schema` 当前固定声明：

```json
{
  "edge_param": "selected_edges",
  "face_param": "selected_faces",
  "edge_index_param": "selected_edge_indices",
  "face_index_param": "selected_face_indices",
  "required_topo_ref_fields": [
    "graph_id",
    "node_id",
    "output_slot",
    "kind",
    "topo_id"
  ],
  "optional_fields": ["selector_hint"],
  "replay_resolution_order": [
    "explicit_topo_refs",
    "stable_indices",
    "selection_query",
    "selector_hint"
  ]
}
```

### 8.2 Explicit Edge / Face Ref

`selected_edges[]` / `selected_faces[]` 的元素结构：

```json
{
  "graph_id": "graph_xxx",
  "node_id": "node_xxx",
  "output_slot": 0.0,
  "kind": "EDGE",
  "topo_id": "edge_640974",
  "selector_hint": {
    "kind": "edge",
    "tags": ["edge", "left"],
    "length": 4.0,
    "start": [-2.0, -2.0, 4.0],
    "end": [-2.0, -2.0, 0.0]
  }
}
```

### 8.3 selector_hint

`selector_hint` 是最后一级 fallback 信息，不保证稳定命中，但可提高恢复率。

不同 shape kind 的可见字段：

| Shape Kind | Possible Hint Fields |
| --- | --- |
| `edge` | `kind`, `tags`, `length`, `start`, `end`, `center` |
| `face` | `kind`, `tags`, `area`, `center`, `normal` |
| `wire` | `kind`, `tags`, `edge_count`, `closed` |
| `vertex` | `kind`, `tags`, `coordinates` |
| `solid` | `kind`, `tags`, `volume`, `bbox` |

### 8.4 selection_query

当 detail feature 使用 QL selector 而不是显式 shape list 时，当前实现会额外记录 `selection_query`。

这是 `ShapeSelector.to_dict()` 的结果，示例：

```json
{
  "target_kind": "edge",
  "order_desc": false,
  "cardinality": {"exactly": 1},
  "predicate": {
    "kind": "property_compare",
    "data": {
      "path": "geom.type",
      "op": "==",
      "value": "CIRCLE"
    },
    "children": []
  },
  "order_key": {
    "kind": "property",
    "data": {
      "path": "geom.center.z",
      "default": null
    }
  },
  "limit": 1
}
```

更复杂的 traversal selector 会出现：

- `source`
- `traversal`

例如 boundary traversal：

```json
{
  "target_kind": "edge",
  "source": {
    "target_kind": "wire",
    "source": {
      "target_kind": "face",
      "predicate": {...},
      "limit": 1,
      "cardinality": {"exactly": 1},
      "order_desc": true,
      "order_key": {...}
    },
    "traversal": {"relation": "boundary"},
    "predicate": {...},
    "limit": 1,
    "cardinality": {"exactly": 1},
    "order_desc": false
  },
  "traversal": {"relation": "boundary"},
  "order_desc": false,
  "cardinality": {"exactly": 4}
}
```

### 8.5 Replay Resolution Order

detail feature replay 的固定解析顺序为：

1. `selected_edges` / `selected_faces` 中的显式 topo refs
2. `selected_edge_indices` / `selected_face_indices`
3. `selection_query`
4. `selector_hint`

适配器若要实现等价行为，必须保持这个顺序。

## 9. Expression Graph Schema

`expression_graph` 结构：

```json
{
  "nodes": [
    {
      "expr_id": "var_119b16e4",
      "kind": "var",
      "name": "r",
      "default": 2.0
    }
  ]
}
```

### 9.1 Node Variants

#### const

```json
{
  "expr_id": "const_xxx",
  "kind": "const",
  "value": 3.0
}
```

#### var

```json
{
  "expr_id": "var_xxx",
  "kind": "var",
  "name": "radius",
  "default": 2.0
}
```

#### expr

```json
{
  "expr_id": "expr_xxx",
  "kind": "expr",
  "op": "mul",
  "args": ["var_xxx", "const_xxx"]
}
```

### 9.2 Supported Expression Ops

当前实现支持：

- `add`
- `sub`
- `mul`
- `div`
- `pow`
- `neg`
- `abs`
- `sin`
- `cos`
- `tan`
- `sqrt`

## 10. Frame Graph Schema

`frame_graph` 结构：

```json
{
  "nodes": [
    {
      "frame_id": "frame:node_abc",
      "origin": [0.0, 0.0, 0.0],
      "x_axis": [1.0, 0.0, 0.0],
      "y_axis": [0.0, 1.0, 0.0],
      "z_axis": [0.0, 0.0, 1.0],
      "parent_frame_id": null,
      "metadata": {"node_id": "node_abc"}
    }
  ]
}
```

字段含义：

| Field | Type | Meaning |
| --- | --- | --- |
| `frame_id` | `string` | frame 唯一 id |
| `origin` | `vec3` | frame 原点 |
| `x_axis` | `vec3` | frame X 轴 |
| `y_axis` | `vec3` | frame Y 轴 |
| `z_axis` | `vec3` | frame Z 轴 |
| `parent_frame_id` | `string|null` | 父 frame；当前 node frames 通常为 `null` |
| `metadata` | `object` | 当前至少包含 `node_id` |

## 11. model JSON Schema

`export_model_json()` 的顶层结构：

```json
{
  "schema_version": "2.0-draft",
  "canonical_contract": {...},
  "graph": {...},
  "expression_graph": {...},
  "frame_graph": {...},
  "geometry_registry": [...],
  "semantic_entity_registry": [...],
  "sketch_profile_registry": [...],
  "assembly_registry": [...],
  "constraint_registry": [...],
  "semantic_delta_log": [...],
  "topology_delta_log": [...],
  "leaf_ids": [...],
  "assembly": {...}
}
```

### 11.1 Top-Level Fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `schema_version` | `string` | yes | current `2.0-draft` |
| `canonical_contract` | `object` | yes | machine-readable interchange contract |
| `graph` | `graph object` | yes | canonical low-level graph and only source of truth |
| `leaf_ids` | `array<string>` | yes | explicit result set for multi-output graph replay/export |
| `expression_graph` | `object` | yes | expression DAG |
| `frame_graph` | `object` | yes | frame snapshots |
| `geometry_registry` | `array<object>` | yes | output geometry registry |
| `semantic_entity_registry` | `array<object>` | yes | semantic entity registry |
| `sketch_profile_registry` | `array<object>` | yes | sketch/profile node registry |
| `assembly_registry` | `array<object>` | yes | assembly summary registry |
| `constraint_registry` | `array<object>` | yes | assembly constraint registry |
| `semantic_delta_log` | `array<object>` | yes | semantic delta log |
| `topology_delta_log` | `array<object>` | yes | topology delta log |
| `assembly` | `object` | no | raw assembly payload when export provided `assembly=` |

### 11.2 canonical_contract

当前固定结构：

```json
{
  "contract_version": "2.0-final-state",
  "graph_roles": {
    "graph": "canonical_low_level_graph",
    "leaf_ids": "explicit_result_set"
  },
  "replay_policy": {
    "preferred_graph": "graph"
  },
  "core_op_set": [...],
  "selection_ref_schema": {...}
}
```

消费规则：

- `replay_model_json()` 直接使用 `graph`
- 多输出 graph 的最终结果集由 `leaf_ids` 显式声明

### 11.3 geometry_registry

每条记录结构：

```json
{
  "graph_id": "graph_xxx",
  "node_id": "node_xxx",
  "entity_type": "Feature",
  "entity_id": "extrude:0",
  "source_op": "extrude"
}
```

来源规则：

- 若 node 有 `semantic_delta.created`，则按其 created refs 写入 registry
- 若 node 没有 semantic delta，则按 `output_count` fallback 生成 `ShapeOutput`

### 11.4 semantic_entity_registry

当前内容与 `geometry_registry` 高度重叠，但语义上强调 semantic entity 视角。

此外，当导出 assembly 约束时，也会追加：

```json
{
  "graph_id": "graph_xxx",
  "node_id": "assembly-constraint:0",
  "entity_type": "AssemblyConstraint",
  "entity_id": "constraint:0",
  "source_op": "offset"
}
```

### 11.5 sketch_profile_registry

仅收录草图/轮廓相关 op，当前集合包括：

- `make_point`
- `make_line`
- `make_segment_wire`
- `make_circle_edge`
- `make_circle_wire`
- `make_circle_face`
- `make_rectangle_wire`
- `make_rectangle_face`
- `make_three_point_arc`
- `make_three_point_arc_wire`
- `make_angle_arc`
- `make_angle_arc_wire`
- `make_spline`
- `make_spline_wire`
- `make_polyline_wire`
- `make_helix`
- `make_helix_wire`
- `make_wire_from_edges`
- `make_face_from_wire`

记录结构：

```json
{
  "graph_id": "graph_xxx",
  "node_id": "node_xxx",
  "op": "make_circle_face",
  "params": {...}
}
```

### 11.6 assembly_registry / constraint_registry

只有在 `export_model_json(session, assembly=...)` 时才会包含有效内容。

当前是轻量摘要，不是完整 assembly interchange schema。

### 11.7 semantic_delta_log / topology_delta_log

两者都按 graph 的拓扑顺序记录。

结构分别为：

```json
{
  "node_id": "node_xxx",
  "op": "extrude",
  "delta": {...}
}
```

## 12. graph Canonical Op Set

当前 canonical low-level graph op set 固定为：

- `make_point`
- `make_line`
- `make_circle_edge`
- `make_three_point_arc`
- `make_angle_arc`
- `make_spline`
- `make_helix`
- `make_wire_from_edges`
- `make_face_from_wire`
- `make_field_surface`
- `extrude`
- `revolve`
- `loft`
- `sweep`
- `translate`
- `rotate`
- `mirror`
- `cut`
- `union`
- `intersect`
- `fillet`
- `chamfer`
- `shell`

下列 node 不允许出现在 canonical `graph`：

- `make_box`
- `make_cylinder`
- `make_sphere`
- `make_cone`
- `make_circle_face`
- `make_rectangle_face`
- `make_circle_wire`
- `make_rectangle_wire`
- `make_polyline_wire`
- `make_segment_wire`
- `make_three_point_arc_wire`
- `make_angle_arc_wire`
- `make_spline_wire`
- `make_helix_wire`
- `linear_pattern`
- `radial_pattern`
- `helical_sweep`

## 13. Recorded Operation Catalog

本节定义当前会出现在 graph/model JSON 中的 operation node 格式。

说明约定：

- `Inputs` 表示 `inputs[]` 依赖的上游输出类型
- `Outputs` 表示当前 node 的 shape 输出类型
- `Params` 只写当前真正落盘的键，不写 Python API 的全部形参名
- 如果某个 Python API 会被宏展开而不是单独记录，会单独说明

### 13.1 Primitive And Profile Ops

#### `make_point`

- Inputs: none
- Outputs: 1 `Vertex`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `x` | scalar | X coordinate |
| `y` | scalar | Y coordinate |
| `z` | scalar | Z coordinate |

#### `make_line`

- Inputs: none
- Outputs: 1 `Edge`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `start` | `vec3` | start point |
| `end` | `vec3` | end point |

Notes:

- `make_segment_redge()` 是别名 API，但记录成 `make_line`

#### `make_segment_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `start`, `end`

#### `make_circle_edge`

- Inputs: none
- Outputs: 1 `Edge`
- Params: `center`, `radius`, `normal`

#### `make_circle_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `center`, `radius`, `normal`

#### `make_circle_face`

- Inputs: none
- Outputs: 1 `Face`
- Params: `center`, `radius`, `normal`

#### `make_rectangle_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `width`, `height`, `center`, `normal`

#### `make_rectangle_face`

- Inputs: none
- Outputs: 1 `Face`
- Params: `width`, `height`, `center`, `normal`

#### `make_face_from_wire`

- Inputs: 1 `Wire`
- Outputs: 1 `Face`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `normal` | `vec3` | desired normal hint |

#### `make_wire_from_edges`

- Inputs: N `Edge`
- Outputs: 1 `Wire`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `edge_count` | `int` | number of consumed edges |

#### `make_three_point_arc`

- Inputs: none
- Outputs: 1 `Edge`
- Params: `start`, `middle`, `end`

#### `make_three_point_arc_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `start`, `middle`, `end`

#### `make_angle_arc`

- Inputs: none
- Outputs: 1 `Edge`
- Params: `center`, `radius`, `start_angle`, `end_angle`, `normal`

#### `make_angle_arc_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `center`, `radius`, `start_angle`, `end_angle`, `normal`

#### `make_spline`

- Inputs: none
- Outputs: 1 `Edge`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `points` | `array<vec3>` | control points |
| `tangents` | `array<vec3> | null` | optional per-point tangents |

#### `make_spline_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `points`, `tangents`, `closed`

#### `make_polyline_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `points`, `closed`

#### `make_helix`

- Inputs: none
- Outputs: 1 `Edge`
- Params: `pitch`, `height`, `radius`, `center`, `dir`

#### `make_helix_wire`

- Inputs: none
- Outputs: 1 `Wire`
- Params: `pitch`, `height`, `radius`, `center`, `dir`

### 13.2 Primitive Solid Ops

#### `make_box`

- Inputs: none
- Outputs: 1 `Solid`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `w` | scalar | width |
| `h` | scalar | height |
| `d` | scalar | depth |
| `bottom_face_center` | `vec3` | placement anchor |

Important:

- 当前 graph JSON 使用 `w/h/d`，不是 `width/height/depth`

#### `make_cylinder`

- Inputs: none
- Outputs: 1 `Solid`
- Params: `radius`, `height`, `bottom_face_center`, `axis`

#### `make_cone`

- Inputs: none
- Outputs: 1 `Solid`
- Params: `bottom_radius`, `top_radius`, `height`, `bottom_face_center`, `axis`

#### `make_sphere`

- Inputs: none
- Outputs: 1 `Solid`
- Params: `radius`, `center`

#### `make_field_surface`

- Inputs: none
- Outputs: 1 `Solid`
- Params base fields:

| Key | Type | Meaning |
| --- | --- | --- |
| `bounds` | object | bounding box used for sampling |
| `resolution` | `array<int>` | sampling resolution `(nx, ny, nz)` |
| `iso` | number | iso value |
| `cap_bounds` | bool | whether the field was clipped to bounds |
| `field_serialization_mode` | string | `scalar_field` or `opaque_callable` |

`bounds` 结构：

```json
{
  "min": [xmin, ymin, zmin],
  "max": [xmax, ymax, zmax]
}
```

若 `field_serialization_mode == "scalar_field"`，则还会包含：

- `field_tree`

若 `field_serialization_mode == "opaque_callable"`，则还会包含：

- `field_callable_repr`

Replay note:

- 只有 `scalar_field` 模式可 replay
- `opaque_callable` 会在 replay 时抛错

### 13.3 Transform Ops

#### `translate`

- Inputs: 1 shape
- Outputs: 1 shape
- Params: `vector`

#### `rotate`

- Inputs: 1 shape
- Outputs: 1 shape
- Params: `angle`, `axis`, `origin`

#### `mirror`

- Inputs: 1 shape
- Outputs: 1 shape
- Params: `plane_origin`, `plane_normal`

### 13.4 Feature Ops

#### `extrude`

- Inputs: 1 `Wire` or `Face`
- Outputs: 1 `Solid`
- Params: `direction`, `distance`

#### `revolve`

- Inputs: 1 `Wire` or `Face`
- Outputs: 1 `Solid`
- Params: `axis`, `angle`, `origin`

#### `loft`

- Inputs: N `Wire`
- Outputs: 1 `Solid`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `profile_count` | `int` | number of profiles |
| `ruled` | `bool` | whether ruled loft mode was requested |

#### `sweep`

- Inputs: 1 profile + 1 path
- Outputs: 1 `Solid`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `is_frenet` | `bool` | sweep orientation mode |

### 13.5 Boolean Ops

#### `union`

- Inputs: N `Solid`
- Outputs:
  - 1 `Solid`, or
  - multiple `Solid` outputs when union result stays disconnected
- Params base fields:

| Key | Type | Meaning |
| --- | --- | --- |
| `input_count` | `int` | number of input solids |
| `clean` | `bool` | whether post-clean was requested |
| `glue` | `bool` | OCC glue mode flag |
| `tol` | `number | null` | effective fuzzy tolerance |

Optional field:

| Key | Type | Meaning |
| --- | --- | --- |
| `result_count` | `int` | only present when union produced multiple solids |

Notes:

- `output_count` is the authoritative output multiplicity
- when `output_count > 1`, output slot order matches the returned result list order

#### `cut`

- Inputs: base solid + tool solids
- Outputs: 1 `Solid` (wrapped in a single-output node)
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `tool_count` | `int` | number of subtractive tool solids |

#### `intersect`

- Inputs: N `Solid`
- Outputs: 1 `Solid` when overlap exists
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `input_count` | `int` | number of intersected solids |

### 13.6 Detail Feature Ops

#### `fillet`

- Inputs: 1 `Solid`
- Outputs: 1 `Solid`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `radius` | scalar | fillet radius |
| `edge_count` | `int` | number of targeted edges |
| `selected_edges` | `array<TopoRefWithHint>` | explicit edge refs |
| `selected_edge_indices` | `array<int>` | stable index fallback against `solid.get_edges()` |
| `selection_query` | `ShapeSelector object` | optional serialized QL selector |

#### `chamfer`

- Inputs: 1 `Solid`
- Outputs: 1 `Solid`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `distance` | scalar | chamfer distance |
| `edge_count` | `int` | number of targeted edges |
| `selected_edges` | `array<TopoRefWithHint>` | explicit edge refs |
| `selected_edge_indices` | `array<int>` | stable index fallback |
| `selection_query` | `ShapeSelector object` | optional serialized QL selector |

#### `shell`

- Inputs: 1 `Solid`
- Outputs: 1 `Solid`
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `thickness` | scalar | shell thickness |
| `removed_face_count` | `int` | number of faces removed |
| `selected_faces` | `array<TopoRefWithHint>` | explicit face refs |
| `selected_face_indices` | `array<int>` | stable index fallback against `solid.get_faces()` |
| `selection_query` | `ShapeSelector object` | optional serialized QL selector |

### 13.7 Pattern Ops

#### `linear_pattern`

- Inputs: 1 shape
- Outputs: `count` shape instances
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `direction` | `vec3` | translation direction |
| `count` | `int` | number of instances |
| `spacing` | `number` | distance between adjacent instances |

Notes:

- canonical graph does not keep a single `linear_pattern` node
- the pattern must expand into explicit `make_translate_rshape` instance nodes and declare final outputs via `leaf_ids`

#### `radial_pattern`

- Inputs: 1 shape
- Outputs: `count` shape instances
- Params:

| Key | Type | Meaning |
| --- | --- | --- |
| `center` | `vec3` | rotation center |
| `axis` | `vec3` | rotation axis |
| `count` | `int` | number of instances |
| `total_rotation_angle` | `number` | angular coverage of the pattern |

Notes:

- canonical graph does not keep a single `radial_pattern` node
- the pattern must expand into explicit `make_rotate_rshape` / `make_translate_rshape` instance nodes and declare final outputs via `leaf_ids`

### 13.8 Macro / Non-Node Cases

#### `helical_sweep_rsolid`

这不是一个稳定记录节点。

规则：

- 当 `GraphSession` 处于激活状态时，`helical_sweep_rsolid()` 不记录 `helical_sweep`
- 它会显式展开为：
  - `make_helix_redge`
  - `make_wire_from_edges_rwire`
  - `make_face_from_wire_rface`
  - `make_sweep_rsolid` with `is_frenet=true`
- 因此 graph JSON / model JSON 中不应期待存在 `op == "helical_sweep"`

#### `make_segment_redge`

- 这是 `make_line_redge()` 的别名 API
- 记录时仍然是 `op == "make_line"`

## 14. Scalar Field Tree Schema

`make_field_surface.params.field_tree` 使用如下递归结构：

```json
{
  "op": "smooth_subtract",
  "params": {
    "k": 0.12
  },
  "children": [
    {...},
    {...}
  ]
}
```

### 14.1 Node Shape

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `op` | `string` | yes | scalar field op |
| `params` | `object` | yes | op-local params |
| `children` | `array<object>` | yes | child field nodes |

### 14.2 Supported field_tree Ops

#### Leaf field ops

| `op` | Params |
| --- | --- |
| `sphere` | `center`, `radius` |
| `ellipsoid` | `center`, `radii` |
| `box` | `center`, `size` |
| `capsule` | `p0`, `p1`, `radius` |

#### CSG field ops

| `op` | Params | Children |
| --- | --- | --- |
| `union` | `{}` | 1+ |
| `intersect` | `{}` | 1+ |
| `subtract` | `{}` | 2 |
| `smooth_union` | `k` | 2 |
| `smooth_subtract` | `k` | 2 |

#### Transform field ops

| `op` | Params | Children |
| --- | --- | --- |
| `translate` | `offset` | 1 |
| `scale` | `factors` | 1 |
| `rotate` | `axis`, `angle` | 1 |

## 15. Replay Semantics

### 15.1 graph replay

`replay_graph(graph)`：

- 逐节点按拓扑序执行
- 使用节点 `op + params + inputs` 恢复几何
- 返回 leaf node outputs

### 15.2 model replay

`replay_model_json(json_str)`：

1. 先导入 model payload
2. 直接 replay `graph`
3. 若存在 `leaf_ids`，返回这些显式 leaf ids 对应的 outputs
4. 否则返回 graph leaf outputs

### 15.3 Output Collection Rule

- 如果未显式指定 leaf ids，最终结果等于 graph 的 leaf node outputs 拼接
- 多输出 node 会把其所有 output slots 依序加入结果

## 16. Adapter Guidance

### 16.1 Strong Recommendations

1. 优先消费 `model.json`
2. 若要做工业 interchange，请直接消费 canonical low-level `graph`
3. 若要恢复参数化，请同时读取 `params`、`param_exprs`、`expression_graph`
4. detail feature 必须按声明顺序解析选择：explicit refs -> indices -> query -> hint
5. 不要依赖 `display.summary` 解析业务语义

### 16.2 Tolerances For Consumers

消费端应对以下实现细节保持宽容：

- 数值字段可能表现为整数或浮点数
- `output_slot` 在深层 param 对象中可能是 `0.0`
- `tags` 可能为空
- `semantic_delta` / `topo_delta` 可能缺失
- `selection_query` 只在调用方用 QL selector 时出现

### 16.3 Recommended Minimal Interchange Subset

如果外部系统只需做几何重建，最小可消费集合是：

- `model.schema_version`
- `model.graph`
- 每个 node 的 `op` / `params` / `inputs` / `output_count`
- `leaf_ids`

如果需要稳定 detail feature 选择，还必须消费：

- `selected_edges` / `selected_faces`
- `selected_edge_indices` / `selected_face_indices`
- `selection_query`
- `selector_hint`

## 17. Known Limitations

1. `helical_sweep` 不是独立 stable node，而是宏展开
2. `opaque_callable` field surface 不可 replay
3. `assembly_registry` / `constraint_registry` 当前是摘要，不是完整装配 IR
4. `display` 是派生字段，不保证长期稳定
5. composite builtins may expand into multiple low-level nodes, so node count/granularity should not be assumed from public API call count

## 18. Worked Examples

### 18.1 fillet Node Example

```json
{
  "node_id": "node_caf7b43f",
  "op": "fillet",
  "params": {
    "radius": 0.3,
    "edge_count": 2,
    "selected_edges": [
      {
        "graph_id": "graph_24fc9c20",
        "node_id": "node_f7e1ea08",
        "output_slot": 0.0,
        "kind": "EDGE",
        "topo_id": "edge_640974",
        "selector_hint": {
          "kind": "edge",
          "tags": ["0", "edge", "left"],
          "length": 4.0,
          "start": [-2.0, -2.0, 4.0],
          "end": [-2.0, -2.0, 0.0]
        }
      }
    ],
    "selected_edge_indices": [0, 1]
  },
  "inputs": ["node_f7e1ea08"],
  "output_count": 1
}
```

### 18.2 extrude Node With Expression Reference

```json
{
  "op": "make_circle_face",
  "params": {
    "center": [0.0, 0.0, 0.0],
    "radius": 2.0,
    "normal": [0.0, 0.0, 1.0]
  },
  "param_exprs": {
    "radius": {
      "expr_id": "var_119b16e4"
    }
  }
}
```

## 19. Summary

可以把当前 JSON interchange 简化理解为：

- `graph` = 唯一真相源的 canonical low-level 图
- `expression_graph` = 参数化依赖图
- `frame_graph` = 工作坐标快照
- `semantic/topology delta` = 语义与拓扑 lineage 补充信息

外部转译适配的主实现建议是：

1. 读 `model.json`
2. 直接使用 `graph`
3. 按本文件的 operation catalog 解释 `params`
4. 对 detail feature 按固定顺序恢复选择对象
5. 在需要参数化恢复时联动 `param_exprs + expression_graph`
