# SimpleCADAPI 2.0 需求与验收文档

## 文档目的

本文档是 `docs/core/rearchitecture_2_0.md` 的配套执行文档，用于把 2.0 的架构方向压缩成：

- 明确的功能需求
- 明确的非目标
- 可验证的验收标准
- 可执行的测试映射

本文档面向实现与测试，不替代架构文档。

## 适用范围

本文档覆盖 `SimpleCADAPI 2.0` 的第一阶段和第二阶段建设要求，重点包括：

- API 连续性
- 表达式图
- OCP 内核迁移方向
- 几何值模型
- 历史/拓扑变化模型
- 装配约束整合
- 模型序列化方向

## 硬约束

以下要求已经确定，后续实现不得违反：

1. 保留纯函数风格 API。
2. 保留 `Vertex -> Edge -> Wire -> Face -> Solid` 作为公开几何对象主线。
3. 保留 `*_rvertex`、`*_redge`、`*_rwire`、`*_rface`、`*_rsolid` 命名风格。
4. 尽量保证已有脚本只需小改动即可迁移。
5. 2.0 第一阶段全部按无单位标量处理。
6. 2.0 核心实现以 `OCP` 为主，不再以 `OCP` 作为内核前提。

## 非目标

以下内容不属于 2.0 第一阶段必做项：

1. 单位系统。
2. 通用符号代数系统。
3. 完整 2D sketch constraint solver。
4. 所有 evolve/macro 函数进入稳定 IR。
5. 跨所有外部 CAD 软件的原生参数树兼容导出。

## 需求列表

### A. API 连续性

#### REQ-API-001

2.0 必须继续公开以下几何主类型：

- `Vertex`
- `Edge`
- `Wire`
- `Face`
- `Solid`

#### REQ-API-002

2.0 必须继续公开核心建模函数的 `r` 风格命名。例如：

- `make_point_rvertex`
- `make_line_redge`
- `make_rectangle_rface`
- `make_box_rsolid`
- `extrude_rsolid`
- `revolve_rsolid`
- `fillet_rsolid`
- `chamfer_rsolid`
- `shell_rsolid`
- `cut_rsolidlist`
- `union_rsolid`
- `intersect_rsolidlist`

#### REQ-API-003

2.0 必须保留“常量参数直接建模”的调用体验，不允许把表达式系统变成基本建模的前置条件。

允许：

```python
box = scad.make_box_rsolid(10, 20, 30)
```

不允许要求用户必须写成：

```python
box = scad.make_box_rsolid(scad.const(10), scad.const(20), scad.const(30))
```

#### REQ-API-004

2.0 的变换与特征操作必须继续保持闭包式返回：

- `translate_shape(solid) -> Solid`
- `rotate_shape(solid) -> Solid`
- `extrude_rsolid(face) -> Solid`
- `fillet_rsolid(solid) -> Solid`

### B. 表达式图

#### REQ-EXPR-001

2.0 必须提供显式变量创建入口：

```python
r = scad.var("r", 10.0)
```

变量名必须由用户显式提供。

#### REQ-EXPR-002

2.0 必须支持在变量上使用标准算术运算构造表达式图，包括：

- `+`
- `-`
- `*`
- `/`
- `**`
- unary `-`

#### REQ-EXPR-003

2.0 必须允许表达式对象直接作为公开建模 API 的参数输入，而不要求额外包装。

允许：

```python
r = scad.var("r", 10.0)
face = scad.make_circle_rface((0, 0, 0), r)
solid = scad.extrude_rsolid(face, (0, 0, 1), r * 2)
```

#### REQ-EXPR-004

所有公开建模 API 在入口处必须统一做参数 canonicalization：

- `int/float -> Const`
- `Var -> Var`
- `Expr -> Expr`
- 向量/点参数逐项 lift

#### REQ-EXPR-005

表达式图必须独立于操作图存在，不能简单把表达式树反复内嵌在每个操作节点中。

最小要求：

- 存在 `ExpressionGraph`
- `OperationNode` 通过引用关系绑定参数表达式

#### REQ-EXPR-006

2.0 第一阶段全部按无单位标量处理。表达式系统不引入单位类型。

### C. 几何值模型

#### REQ-GEO-001

2.0 公开几何对象必须继续保持值对象风格，而不是对外暴露 scene graph 节点风格。

#### REQ-GEO-002

2.0 应引入 `Sketch` 作为新增一等对象，但 `Sketch` 不能替代 `Vertex/Edge/Wire/Face/Solid` 主线。

#### REQ-GEO-003

每个公开几何对象都必须可查询空间信息，但对象空间信息的内部来源允许不同：

- 直接拥有 placement/frame
- 从上游 owner/instance 推导

这属于内部实现约束，不作为用户侧公开类型分裂。

### D. OCP 内核

#### REQ-KERNEL-001

2.0 的核心 evaluator 必须以 `OCP` 为主实现，而不是继续依赖 `cadquery` 作为核心构造层。

#### REQ-KERNEL-002

2.0 的 `Vertex/Edge/Wire/Face/Solid` 内部实现应逐步迁移为 OCP thin wrapper。

#### REQ-KERNEL-003

如保留 `OCP`，只能作为过渡期兼容工具或开发辅助工具，而不能作为 2.0 核心前提。

### E. 基础操作集

#### REQ-OPS-001

2.0 第一阶段稳定基础操作集为：

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

#### REQ-OPS-002

第一阶段不要求把复杂宏、evolve case 和特殊建模脚本纳入核心稳定 IR。

### F. 历史与变化记录

#### REQ-HIST-001

2.0 不能只记录最终几何结果，必须记录可 replay 的操作图。

#### REQ-HIST-002

2.0 必须区分两层变化：

- `SemanticDelta`
- `TopoDelta`

#### REQ-HIST-003

`TopoDelta` 至少必须能表达：

- `created`
- `preserved`
- `modified`
- `deleted`

#### REQ-HIST-004

以下基础操作应具备可靠的历史/变化记录能力：

- `extrude`
- `revolve`
- `fillet`
- `chamfer`
- `shell`
- `cut`
- `union`
- `intersection`

#### REQ-HIST-005

对象引用体系必须至少同时支持：

- `SemanticRef`
- `TopoRef`

### G. 装配与约束

#### REQ-ASM-001

装配系统必须整合进统一模型 IR，而不是继续作为完全独立的旁路系统。

#### REQ-ASM-002

装配约束参数必须复用同一套表达式系统。

#### REQ-ASM-003

2.0 第一阶段装配重点仍是 rigid pose solving，不要求在 assembly solve 中直接改 part 内部拓扑。

### H. 序列化与导出

#### REQ-IO-001

2.0 必须以模型 IR 作为 canonical export，而不是 STEP/STL。

#### REQ-IO-002

canonical export 至少应包含：

- expression graph
- operation graph
- geometry registry
- optional assembly/constraint data
- semantic/topology deltas

#### REQ-IO-003

STEP/STL/BRep 继续保留，但只作为最终几何导出，不作为参数化事实来源。

## 验收标准

### 阶段 1 验收标准

满足以下条件即认为 Phase 1 完成：

1. `var()` API 已存在。
2. `Var` 可参与算术表达式。
3. 至少 2 个公开建模 API 能直接接受表达式参数。
4. 常量参数建模脚本仍可不加 wrapper 正常运行。
5. `ExpressionGraph` 可序列化和反序列化。
6. 至少有一组契约测试覆盖 API 连续性与表达式入口。

### 阶段 2 验收标准

满足以下条件即认为 Phase 2 完成：

1. `Vertex/Edge/Wire/Face/Solid` 至少一部分已切换到 OCP thin wrapper。
2. `extrude` 和 `revolve` 具备表达式驱动与历史记录。
3. `TopoDelta` 对基础 feature 可用。
4. replay 可以从模型 IR 重新生成结果。

### 阶段 3 验收标准

满足以下条件即认为 Phase 3 完成：

1. `cut/union/intersection` 具备稳定变化记录。
2. `fillet/chamfer/shell` 具备稳定变化记录。
3. assembly 约束参数可复用表达式图。
4. canonical JSON export 初步稳定。

### 最终状态验收标准

当以下条件全部满足时，认为当前 2.0 主线已经达到本轮冻结的“最终状态”：

1. `model.json` 是 canonical export，且可以不依赖 `.graph.json` 独立 replay。
2. `model.json` 顶层必须同时包含：
   - `graph`
   - `leaf_ids`
   - `expression_graph`
   - `frame_graph`
   - `geometry_registry`
   - `semantic_entity_registry`
   - `sketch_profile_registry`
   - `assembly_registry`
   - `constraint_registry`
   - `semantic_delta_log`
   - `topology_delta_log`
   - `canonical_contract`
3. `canonical_contract` 必须明确声明：
   - `graph` 的角色是唯一真相源的 canonical low-level graph
   - `leaf_ids` 是多输出场景的显式结果集
   - replay 默认直接使用 `graph`
4. `graph` 必须限制在冻结的 canonical op set 内，不能泄漏 convenience 或 macro-only op；至少不允许出现：
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
5. `helical_sweep` 必须被视为组合宏，而不是基础 canonical 节点；最终 `graph` 中只能出现它 lower 后的基础链条。
6. `linear_pattern` / `radial_pattern` 必须 lower 为显式 transform 实例链，并通过 `leaf_ids` 明确哪些实例是最终结果集。
7. detail feature 的 canonical 参数必须保留 explicit selected refs：
   - `fillet/chamfer` 使用 `selected_edges`
   - `shell` 使用 `selected_faces`
8. selection-ref schema 必须冻结，并至少要求每个 explicit topo ref 具备：
   - `graph_id`
   - `node_id`
   - `output_slot`
   - `kind`
   - `topo_id`
   - 可选 `selector_hint`
9. `replay_model_json()` 对 detail feature 的选择解析顺序必须固定为：
   - explicit topo refs
   - stable indices
   - selection query
   - selector hint
10. 上述最终状态必须由自动化测试锁定，并在 `uv run python -m unittest discover -s test` 下全量通过。

## 测试映射

### 现阶段已落地的契约测试

以下 requirement 将由新建的契约测试文件覆盖：

- `REQ-API-001`
- `REQ-API-002`
- `REQ-API-003`
- `REQ-API-004`
- `REQ-EXPR-001` 的入口占位检查
- `REQ-EXPR-003` 的未来占位检查

### 推荐测试文件

- `test/test_public_api_surface.py`
- `test/test_original_api_integration.py`
- `test/test_rearchitecture_2_0_contract.py`

### 推荐执行命令

项目使用 `uv`，因此测试执行统一建议使用：

```bash
uv run python -m unittest test/test_public_api_surface.py test/test_rearchitecture_2_0_contract.py
```

后续如果表达式系统开始落地，可追加：

```bash
uv run python -m unittest test/test_rearchitecture_2_0_contract.py
```

## 分支策略

2.0 重构建议在独立分支上推进，不在旧实现上做原地无序叠加。当前建议分支策略为：

- 使用独立重构分支承载 2.0 需求、测试和新内核工作
- 逐步让兼容层指向新内核
- 不把临时过渡性旧逻辑继续扩散到新模块中

## 结论

本文件将 2.0 的方向收束成了可以逐条验收的要求。后续实现应以 requirement ID 为基准推进，测试也应优先围绕 requirement ID 来补齐，而不是围绕临时实现细节写脆弱测试。
