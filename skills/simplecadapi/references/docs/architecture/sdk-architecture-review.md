# SimpleCADAPI SDK 架构评价报告

日期：2026-05-21

视角：函数式风格 programmer + CAD 软件架构师

前提：本报告认同并保留 SimpleCADAPI 的顶层 API 风格。`make_*_r*`、`*_rsolid`、`*_rwire`、`GraphSession`、`export_model_json` 这一套方向不是问题本身，反而是这个 SDK 最有价值的部分。真正的问题在于：内部实现还没有完全配得上这个顶层风格所暗示的稳定性、可组合性和可重放性。

## 总结判断

SimpleCADAPI 的顶层 API 选择是正确的：它没有把用户拖进传统 CAD kernel 的继承层级和 builder 生命周期，而是用一组接近纯函数的建模函数表达几何变换。这是适合 Python、适合自动化、适合 LLM/脚本生成、也适合未来 GUI 低代码编排的 API 形态。

但当前架构的真实状态是：顶层像函数式 CAD DSL，底层仍是“带全局上下文、带隐藏运行时元数据、带 OCC 对象身份、带启发式 replay”的工程拼装体。它能跑通大量示例，但还没有形成足够硬的 CAD SDK 契约。最危险的地方不是 primitive 建模能力，而是拓扑命名、选择语义、replay 严格性、装配求解、schema 稳定性和测试强度。

如果用一句话评价：这是一个有正确 API 直觉的 OCP-native CAD SDK 原型，已经越过玩具阶段，但还没有越过“可靠参数化 CAD 平台”的门槛。

## 评价边界

本报告基于当前仓库源码、文档、示例和测试，不评价尚未落地的设想。

主要检查对象：

- `src/simplecadapi/__init__.py`
- `src/simplecadapi/core.py`
- `src/simplecadapi/operations.py`
- `src/simplecadapi/graph.py`
- `src/simplecadapi/serializer.py`
- `src/simplecadapi/topology.py`
- `src/simplecadapi/tracking.py`
- `src/simplecadapi/ql.py`
- `src/simplecadapi/tagging.py`
- historical assembly/constraint implementation, now removed from the active public/support surface
- historical scalar-field/SDF implementation, now removed from the active public/support surface
- `docs/core/serialization/`
- `docs/core/operation_graph_json_spec.md`
- `examples/07_serialization_operation_tree.py`
- `test/` 与 `tests/`

## 顶层 API 评价

顶层 API 的方向值得保留。

`make_box_rsolid(...)`、`make_line_redge(...)`、`extrude_rsolid(...)`、`union_rsolid(...)` 这种命名确实有点“硬”，但它有一个重要优点：它把 CAD 操作建模成从参数到几何值的映射，返回类型在名字里显式出现。对脚本、生成式建模、图记录、schema 生成和 IDE 补全来说，这比传统 OOP fluent builder 更稳定。

强项：

- `__init__.py` 明确导出建模函数、核心类型、graph/session、serializer、expression 和 `ql` 子模块，公开面可见性好。参考：`src/simplecadapi/__init__.py`。
- 大多数核心创建函数遵守返回类型后缀，例如 `make_point_rvertex -> Vertex`、`make_line_redge -> Edge`、`make_circle_rwire -> Wire`、`make_box_rsolid -> Solid`。参考：`src/simplecadapi/operations.py:691`、`src/simplecadapi/operations.py:723`、`src/simplecadapi/operations.py:1465`。
- composite convenience API 在 `GraphSession` 内降低为 canonical low-level graph，这个设计非常正确。用户调用 `make_box_rsolid`，图里记录 rectangle/profile/extrude，这是 CAD DSL 和 replay IR 分层的正确方式。参考：`src/simplecadapi/operations.py:1480`、`examples/07_serialization_operation_tree.py:52`、`examples/07_serialization_operation_tree.py:272`。
- `union_rsolid(...)` 明确返回单个 `Solid`，失败就报错，不默默返回多个实体。这对机械 CAD 是正确的默认语义。参考：`src/simplecadapi/operations.py:2856`、`src/simplecadapi/operations.py:2876`。
- `GraphSession` + `export_model_json` + `replay_model_json` 的主线是对的。它把脚本建模提升为可交换、可 replay 的模型记录。参考：`src/simplecadapi/graph.py:44`、`src/simplecadapi/serializer.py:416`、`src/simplecadapi/serializer.py:732`。
- `ql` 被放到子模块而非全部塞进顶层，是正确的边界意识。参考：`src/simplecadapi/__init__.py`、`docs/api/README.md:5`。

问题：

- 顶层 API 被 aliases 稀释了。`create_box`、`create_line`、`extrude`、`union`、`to_step` 等别名降低了 canonical API 的唯一性。对用户友好，但对文档、LLM、图记录和长期兼容不友好。参考：`src/simplecadapi/__init__.py:145`、`src/simplecadapi/__init__.py:318`。
- README 说 API 函数统一用 return type 反映命名，但公开面包含 `translate_shape`、`rotate_shape`、`export_step`、`export_stl` 和大量 aliases。这个声明过强。参考：`README.md:200`、`src/simplecadapi/__init__.py:47`、`src/simplecadapi/__init__.py:187`。
- `rsolidlist` 命名混杂了“参数类型”和“返回类型”：`cut_rsolid`、`intersect_rsolid` 实际返回 `Solid`，而 `linear_pattern_rsolidlist` 返回 `List[Solid]`。这会伤害 API 语义一致性。参考：`src/simplecadapi/operations.py:2994`、`src/simplecadapi/operations.py:3102`、`src/simplecadapi/operations.py:4121`。
- public op 名和 graph op 名不完全一致：`translate_shape` 记录为 `make_translate_rshape`，`extrude_rsolid` 记录为 `make_extrude_rsolid`。这种分层可以接受，但必须正式化为“source API”和“canonical IR”的稳定映射表。参考：`src/simplecadapi/operations.py:117`、`src/simplecadapi/serializer.py:116`。
- 一些非 session 分支仍记录 legacy op 名，如 `make_box`、`make_cylinder`、`make_segment_wire`，和 canonical `make_*_r*` 命名不一致。参考：`src/simplecadapi/operations.py:785`、`src/simplecadapi/operations.py:1534`、`src/simplecadapi/operations.py:1638`。

建议：保留 `make_*_r*`，但把 aliases 降级为 compatibility surface，不作为文档主路径；把 source API 到 canonical graph op 的映射写成稳定规范；把 `rsolidlist` 这种历史命名列入 3.0 前清理清单。

## 函数式架构评价

顶层是函数式的，底层不是。

从函数式 programmer 的角度看，这套 SDK 最好的设计是“操作返回新几何值，而不是用户手动驱动 mutable builder”。但当前实现中，几何值本身携带大量隐藏可变状态：tags、metadata、runtime graph node、topo refs、track summary。这不是不能接受，但必须承认它是 effect system，而不是纯函数系统。

可取之处：

- `operations.py` 的 `_finalize_primitive_shape`、`_finalize_derived_shape`、`_finalize_tracked_solid` 把 graph recording、semantic delta、tracking summary 收敛到少数 finalizer。这个方向正确。参考：`src/simplecadapi/operations.py:597`、`src/simplecadapi/operations.py:629`、`src/simplecadapi/operations.py:650`。
- 旧 `ScalarField` 尝试用 frozen dataclass 表达隐式建模 AST；该 surface 已移除，后续如恢复需先统一 SDF 语义。
- `ShapeSelector`、`SerializablePredicate`、`SerializableKey` 都是 dataclass/frozen 风格，QL 作为可序列化 AST 的方向正确。参考：`src/simplecadapi/ql.py:258`、`src/simplecadapi/ql.py:320`、`src/simplecadapi/ql.py:396`。

问题：

- `GraphSession` 使用模块级 `_active_session` 和 `_recording_suspend_depth`。嵌套 session、并发 session、异步建模都会互相污染。参考：`src/simplecadapi/graph.py:40`、`src/simplecadapi/graph.py:69`、`src/simplecadapi/graph.py:91`。
- `SimpleWorkplane` 使用模块级 `_current_cs` 栈，和 `GraphSession` 一样是隐式全局 effect。参考：`src/simplecadapi/core.py:276`、`src/simplecadapi/core.py:298`。
- `attach_graph_node` 会把 graph node、node id、output slot、topo ref 写入 shape runtime/metadata。这个副作用是设计核心，但它破坏了“同样输入得到同样纯值”的直觉。参考：`src/simplecadapi/graph.py:231`、`src/simplecadapi/graph.py:247`、`src/simplecadapi/graph.py:259`。
- tagging 已收敛到 `apply_tag(shape, tag)` / `list_tags(shape)` 的 functional public surface；底层仍然是对 shape tag store 的受控 mutation，需要在 docs 中明确这是 controlled tagging effect。
- `GraphSession` 记录了 context/frame，但 replay 不使用 context 重建 workplane。这个会让“记录的是建模意图”的函数式承诺打折。参考：`src/simplecadapi/graph.py:132`、`src/simplecadapi/topology.py:338`、`src/simplecadapi/serializer.py:991`。

函数式层面的根本建议：把 `GraphSession`、workplane、tag/metadata/runtime 都明确视为 effect context，并用 `contextvars` 或显式 session 参数隔离；公开文档不要暗示全纯函数，而要说“functional surface with controlled recording/tagging effects”。

## CAD Kernel 边界评价

这套 SDK 是 OCP-native，不是 kernel-agnostic。这一点没有问题，但必须讲清楚。

优点：

- wrapper 很薄，直接包 OCP TopoDS，性能和能力不会被中间抽象拖死。参考：`src/simplecadapi/core.py:422`、`src/simplecadapi/core.py:465`、`src/simplecadapi/core.py:597`、`src/simplecadapi/core.py:713`。
- `kernel/` 目录已经把 builders、booleans、curves、features、mesh、properties、topology、transforms、export 分层出来，比把所有 OCP 调用塞到 `operations.py` 更可维护。参考：`src/simplecadapi/kernel/ocp_booleans.py:1`、`src/simplecadapi/kernel/ocp_features.py`、`src/simplecadapi/kernel/ocp_transforms.py`。
- tests 已经明确防止 CadQuery 依赖回流，这是好边界。参考：`tests/test_ocp_core_no_cadquery.py:9`。

问题：

- `.wrapped` 是公开事实，docs 也承认 public geometry wrappers expose `.wrapped`。这不是错，但这意味着 SDK 没有真正封装 kernel，只是提供了 OCP-native convenience layer。参考：`docs/core/README.md:5`、`src/simplecadapi/core.py:427`、`src/simplecadapi/core.py:718`。
- QL 内部直接用 OCP adaptor 判断 curve/surface type。这个实现合理，但进一步证明 QL 当前绑定 OCP 语义，而不是中立 CAD 语义。参考：`src/simplecadapi/ql.py:193`。
- 旧 constraints 实现直接用 OCP transform 重建 solid，装配层和 kernel 层耦合很深；该 public/support surface 已移除，等待新契约重做。
- `operations.py` 仍然直接 import OCP builder 类型并手写部分 kernel 操作。kernel adapter 层还没有完全收敛。参考：`src/simplecadapi/operations.py:14`、`src/simplecadapi/operations.py:17`。

建议：不要假装 kernel-agnostic。短期应该明确定位为 OCP-native functional SDK。中期把 `operations.py` 中剩余 OCP 直接调用继续下沉到 `kernel/`，让 public ops 只做参数验证、effect finalization 和 semantic recording。

## 拓扑身份与命名

这是当前最核心的 CAD 风险。

CAD SDK 真正难的不是画 box、cylinder、extrude，而是模型变化后还能稳定地说“我要这个孔的圆边”“我要这个安装面”。当前 SimpleCADAPI 已经意识到这个问题，但实现还没有解决它。

已有基础：

- `_TopologyEntityCache` 用 OCC `HashCode` bucket 加 `IsSame` 做同一 shape occurrence 的合并，能让一个 box 的 shared edge occurrences 共享 topo id。参考：`src/simplecadapi/core.py:42`、`tests/test_topology_identity.py:16`。
- `TopoRef`、`TopoDelta`、`TopoEntry`、`SemanticDelta` 数据模型已经存在，说明架构上知道需要 graph-aware topology references。参考：`src/simplecadapi/topology.py:60`、`src/simplecadapi/topology.py:203`、`src/simplecadapi/topology.py:223`。
- `tracking.py` 直接查询 OCC builder 的 `Modified()`、`Generated()`、`IsDeleted()`、`SectionEdges()`，方向正确。参考：`src/simplecadapi/tracking.py:1`、`src/simplecadapi/tracking.py:107`。

硬伤：

- `TopoRef.topo_id` 文档自己承认 implementation-defined，可能是 sequential integer、hash 等。这不够 durable。参考：`src/simplecadapi/topology.py:69`。
- `_safe_shape_hash` 使用 `HashCode(1000000)`，fallback 是 `hash(shape)`。这只能做运行期/构建期身份辅助，不能做跨 replay 稳定身份。参考：`src/simplecadapi/core.py:22`。
- `TaggedMixin.topo_id` 在无 entity 时 fallback 到 `id(self)`，这是进程内对象身份，不是 CAD 拓扑身份。参考：`src/simplecadapi/core.py:321`。
- `tracking._topo_id` 也使用 OCC hash，并且注释叫 “Stable-ish”。这句话本身就是风险说明。参考：`src/simplecadapi/tracking.py:80`。
- `TopoEntry` 支持 richer lineage，但 `tracking._build_boolean_result` 只把 rich entries 放进 `delta_entries` dict，没有填入 `TopoDelta.entries`。导出时 `export_model_json` 只序列化 `node.topo_delta`，丰富 lineage 没有成为 durable graph contract。参考：`src/simplecadapi/tracking.py:283`、`src/simplecadapi/tracking.py:291`、`src/simplecadapi/serializer.py:480`。
- boolean、fillet、chamfer、shell 后的 topology tracking 是有用的，但不是 stable topology naming system。它记录了 OCC 的历史回答，不等于建立了语义身份。

结论：当前拓扑身份适合调试、局部 selection replay 和轻量 semantic tagging，不适合作为长期参数化模型的核心契约。必须尽快把 QL/SelectionSpec 作为 primary identity，把 raw topo refs 降级为 fallback。

## QL 与选择语义

QL 是架构上最应该继续投资的部分。

好处：

- QL 已经有 serializable predicate、serializable key、selector、order、limit、exactly cardinality。参考：`src/simplecadapi/ql.py:258`、`src/simplecadapi/ql.py:320`、`src/simplecadapi/ql.py:396`。
- QL 支持 tag/meta/property/curve_type/surface_type/normal/center/length/area/volume 等基础语义。参考：`src/simplecadapi/ql.py:77`、`src/simplecadapi/ql.py:94`、`src/simplecadapi/ql.py:125`。
- fillet/chamfer/shell 现在会把 QL selector 的运行时结果编译为 `make_select_*` geo select nodes；`selection_query` 仅保留为旧 payload fallback。参考：`test/test_serialization.py:443`、`src/simplecadapi/serializer.py:1365`。

问题：

- QL graph scope 现在通过 `make_select_*` 节点的 source input 表达，而不是只靠 query AST；未来还需要把这个契约扩展到非 detail-feature 的通用 selection 工作流。
- 当前 replay resolution order 已经变为 geo select nodes -> selection_query fallback -> topo refs -> indices -> hint；后续风险主要是外部 adapter 需要跟进新顺序。
- 只有 `exactly(n)`，没有 `at_least`、`at_most`，cardinality 还不够表达真实 CAD 选择约束。参考：`src/simplecadapi/ql.py:457`。
- ordering 只有单 key，不支持 lexicographic multi-key。复杂 CAD 选择里单 key 很容易产生不稳定 tie。参考：`src/simplecadapi/ql.py:429`。
- `_shape_identity` 仍然优先用 topo id 或 topo_ref metadata，说明 QL 运行时仍被当前 topology identity 牵引。参考：`src/simplecadapi/ql.py:566`。

建议：把 `SelectionSpec` 做成正式 schema：source scope、query AST、多 key order、limit、cardinality、fallback。所有接受 `List[Edge]`、`List[Face]` 的 feature API，在 GraphSession 内都应该 normalize 成 SelectionSpec。replay 必须 QL first，topo refs/indices/hints 只能 fallback。

## Graph、Serialization 与 Replay

这是 SDK 的战略性资产，也是当前最需要变硬的契约。

做得好的地方：

- `OperationGraph` 是 DAG，节点保存 op、params、param_exprs、inputs、context、semantic_delta、topo_delta、tags。结构完整。参考：`src/simplecadapi/topology.py:318`、`src/simplecadapi/topology.py:476`。
- `export_model_json` 输出 graph、leaf_ids、expression_graph、frame_graph、registries、delta logs、canonical contract。方向很对。参考：`src/simplecadapi/serializer.py:627`。
- `_assert_graph_is_canonical` 在 export model 前拒绝非 canonical ops，这是保持 IR 干净的正确动作。参考：`src/simplecadapi/serializer.py:246`、`src/simplecadapi/serializer.py:624`。
- `examples/07_serialization_operation_tree.py` 非常有价值。它把 source API 到 operation tree 的映射讲清楚，是 SDK 最该保留和扩展的示例。参考：`examples/07_serialization_operation_tree.py:1`、`examples/07_serialization_operation_tree.py:217`。

严重问题：

- replay 过于宽松。多个 replay 分支在输入缺失时 `continue`，最终 leaf collection 用 `outputs.get(node_id, [])`。坏图可能静默变成少输出或空输出。参考：`src/simplecadapi/serializer.py:1018`、`src/simplecadapi/serializer.py:1051`、`src/simplecadapi/serializer.py:1294`。
- primitive replay 使用 permissive defaults。缺少 `x` 就默认为 0，缺少 radius 就默认为 1。这会把坏 JSON 变成错误几何，而不是报错。参考：`src/simplecadapi/serializer.py:767`。
- `OperationGraph.from_dict` 对 edges 和 inputs 的缺失引用采取静默跳过。对 interchange schema 来说这太软。参考：`src/simplecadapi/topology.py:692`、`src/simplecadapi/topology.py:701`。
- graph schema version 是 `1.0`，model schema 是 `2.0-draft`，canonical contract 是 `2.0-final-state`。这三个版本信号混在一起，会让外部消费者不知道哪个才是稳定承诺。参考：`src/simplecadapi/topology.py:19`、`src/simplecadapi/serializer.py:221`、`src/simplecadapi/serializer.py:628`。
- node.context 和 frame_graph 被记录，但 replay 不恢复 frame/workplane；所有 ops 按当前 ambient world context 执行。参考：`src/simplecadapi/graph.py:132`、`src/simplecadapi/serializer.py:991`。
- `leaf_ids` 自动来自 graph leaves，而不是用户显式声明的 final outputs。debug/intermediate 独立节点会成为 replay 输出。参考：`src/simplecadapi/serializer.py:624`、`src/simplecadapi/topology.py:563`。
- expression replay 是 numeric snapshot，不是 parametric replay。这个可以接受，但必须在 SDK 主文档里反复强调。参考：`examples/07_serialization_operation_tree.py:40`、`examples/07_serialization_operation_tree.py:287`。

建议：replay 应该默认 strict。所有 missing input、missing param、unknown op、leaf missing output、selection cardinality mismatch 都应该 hard failure。需要宽松模式时显式 `strict=False`。

## Boolean 与 Feature Tracking

当前 boolean API 的用户语义比很多 CAD wrapper 都清楚，但 tracking 和 replay 还不够可信。

优点：

- `union_rsolid`  flatten nested inputs，使用 scale-aware fuzzy tolerance，支持 glue，默认 clean，并强制单 solid。参考：`src/simplecadapi/operations.py:221`、`src/simplecadapi/operations.py:2856`、`src/simplecadapi/kernel/ocp_booleans.py:40`。
- `fuse_shapes` 使用 OCC Fuse、parallel、OBB、fuzzy value、GlueShift 和 same-domain cleanup，基本工程判断正确。参考：`src/simplecadapi/kernel/ocp_booleans.py:45`。
- `tracked_cut`、`tracked_union`、`tracked_intersect` 使用 OCC history，这比只比较结果 faces 靠谱。参考：`src/simplecadapi/tracking.py:308`、`src/simplecadapi/tracking.py:338`、`src/simplecadapi/tracking.py:374`。

问题：

- `tracked_union` 接收 `glue` 和 `tol`，但没有把它们设置到 `BRepAlgoAPI_Fuse`。也就是说用于结果的 union 和用于 tracking 的 union 参数可能不一致。参考：`src/simplecadapi/tracking.py:338`、`src/simplecadapi/tracking.py:352`。
- `union_rsolid` replay 忽略记录过的 `clean`、`glue`、`tol`，只调用 `ops.union_rsolid(all_solids)`。参数不 faithful。参考：`src/simplecadapi/operations.py:2946`、`src/simplecadapi/serializer.py:1029`。
- `cut_rsolid` 对无交集 tool 直接跳过，这对 modeling convenience 可能友好，但对 replay/diagnostic 来说可能隐藏错误。参考：`src/simplecadapi/operations.py:3033`。
- 多 tool cut/intersect 只保留最后一次 delta，前面 tool 的 lineage 丢失。参考：`src/simplecadapi/operations.py:3020`、`src/simplecadapi/operations.py:3127`。
- extrude face classification 使用 center 精确相等、normal dot 精确等于 0、angle 精确等于 pi，这在 CAD 数值几何里非常脆弱。参考：`src/simplecadapi/operations.py:2631`、`src/simplecadapi/operations.py:2646`、`src/simplecadapi/operations.py:2653`。

建议：boolean result 和 boolean tracking 必须用同一 builder 或至少同一参数配置；replay 必须重放 boolean params；feature tagging 不应靠 exact float equality，应使用 tolerance 和 topology history。

## Tagging 与 Metadata

tagging 的目标是对的，但现在新旧体系混在一起。

优点：

- `tagging.py` 定义了 normalized tag grammar 和 `TagPolicy`，这是 QL 和 anchor semantics 的基础。参考：`src/simplecadapi/tagging.py:8`、`src/simplecadapi/tagging.py:58`。
- `apply_tag(shape, tag)` / `list_tags(shape)` 是唯一推荐的 public tagging surface，`list_tags` 输出稳定排序。
- 当前约定是不在 tags 中存数字，而是在 metadata[`geo`] 中保存结构化几何事实。

问题：

- QL、anchor lookup、auto tagging、metadata[`geo`] 之间还需要一个正式 schema 文档把它们串起来。
- tagging 仍然是 shape-local side effect；graph/session replay 文档应继续明确哪些 tags 会进入 serialized selector hints。

建议：建立 tag schema version。新代码只产生 normalized tags，旧 tags 标成 `legacy.*` 或仅作为 lookup fallback。

## Assembly 与 Constraints

旧装配 API 的顶层形态有可取之处，但 solver 只是 MVP；该 surface 已移除，等待基于新 assembly IR / constraint graph 重做。

优点：

- assembly 层和 geometry construction 分开，这是正确的 CAD 架构。geometry API 做 integrated parts，未来 assembly constraints 做最终空间关系。
- anchor/part handle 这类表达形式可以作为新设计参考，但不能直接恢复旧实现。
- solved snapshot 的函数式方向可以保留，但需要新的 solver contract 支撑。

问题：

- 旧 solver 是顺序应用约束的迭代 pose adjustment，不是 DOF solver、不是约束图求解器、没有 Jacobian/least-squares、没有 overconstraint/underconstraint 严格诊断。
- 旧 diagnostics 主要只有 non-convergence 和 unconstrained parts。对真实机械装配不够。
- 旧 bbox anchor 基于 local AABB，旋转或复杂形体下语义会很粗糙。
- 旧 `export_model_json` assembly frame 摘要不完整，因此已从当前 schema 中撤回。

建议：把当前 assembly 文档称为 “layout constraints” 或 “MVP rigid pose helper”，不要称成熟 assembly solver。下一步优先修 export frame rotation，然后再谈 DOF solver。

## Scalar Field 与 Implicit Modeling

旧 scalar field/SDF surface 已移除；下面记录的是移除前的历史评审结论。

优点：

- 旧 `ScalarField` tree 曾尝试做可序列化/replay 的隐式建模表达。
- 旧 `make_field_surface_rsolid` 曾区分 replayable scalar field tree 和 opaque callable。

问题：

- sphere 返回平方距离减 `r^2`，box/capsule 接近 signed distance。smooth union/subtract 假设 field value 单位可比，但这里不成立。
- `scale` 使用 min scale 乘回 field value，对非 SDF field 更不稳定。
- 这意味着 implicit smooth operations 目前更像 demo/experimental，而不是可靠 SDF modeling kernel。

建议：明确 `ScalarField` 是 algebraic implicit field 还是 true SDF。若要支持 smooth booleans，必须统一到 SDF 或至少在每个 primitive 标记 value metric，并拒绝不兼容 smooth blend。

## 错误模型与 Developer Experience

优点：

- public operations 大量使用 `raise_harness_error` 包装上下文，错误信息对脚本用户友好。参考：`src/simplecadapi/operations.py:204`。
- import/replay 的错误也有 what happened / possible causes / how to fix，这对 SDK 很有价值。参考：`src/simplecadapi/serializer.py:345`、`src/simplecadapi/serializer.py:743`。

问题：

- 一些地方直接 `print` warning，而不是走 warning/error policy。参考：`src/simplecadapi/core.py:787`、`src/simplecadapi/core.py:808`。
- 一些 tracking 异常被吞掉，例如 union tracking 失败就继续记录无 delta。这对 robustness 友好，但对 auditability 很差。参考：`src/simplecadapi/operations.py:2930`。
- replay 对 malformed graph 静默跳过比报错更危险。参考：`src/simplecadapi/serializer.py:1018`。

建议：区分 user modeling error、kernel failure、replay schema error、tracking degraded warning。replay/schema 默认必须严格。

## 测试体系评价

测试覆盖了很多 API，但 CAD robustness 测试还不够狠。

已有价值：

- 有 no-CadQuery boundary test。参考：`tests/test_ocp_core_no_cadquery.py:9`。
- 有 topology occurrence identity test。参考：`tests/test_topology_identity.py:16`。
- 有 graph serialization/replay tests，包括 QL selector replay、mirror、sweep、pattern 等。参考：`test/test_serialization.py:233`、`test/test_serialization.py:420`、`test/test_serialization.py:491`。

不足：

- 一些断言是无效断言，如 `len(modified) >= 0`、`len(tagged) >= 0`，这永远成立。参考：`test/test_original_api_integration.py:23`、`test/test_original_api_integration.py:50`。
- topology identity 测试只证明单个 box 内 shared edge occurrence，不证明跨 operation、跨 replay、跨 boolean 的 durable identity。参考：`tests/test_topology_identity.py:16`。
- replay tests 多数验证 happy path volume，不够验证 malformed graph、missing inputs、schema rejection、workplane context、boolean params faithful、selection ambiguity。
- assembly tests没有证明 overconstraint/underconstraint、DOF、rotation frame export 的正确性。

建议优先加这些测试：

- GraphSession nested/concurrent isolation。
- SimpleWorkplane 内记录后在 world context replay，结果必须一致。
- replay missing param 必须报错，不允许默认生成几何。
- replay missing input 必须报错。
- union clean/glue/tol 参数 replay faithful。
- QL selection ambiguity 必须按 cardinality 报错。
- boolean tracking result 和 actual result 用同一参数。
- assembly frame export 必须保留旋转轴。
- scalar field smooth union 拒绝混合非同量纲 field 或统一 SDF。

## 最重要的架构矛盾

SimpleCADAPI 当前最大的矛盾不是“函数式 API vs OOP core”。薄 wrapper core 可以接受。

真正的矛盾是：顶层 API 和 v2 model JSON 暗示了稳定、可 replay、可交换的 CAD DSL，但底层仍依赖隐式全局状态、runtime metadata、OCC hash、fallback indices、permissive defaults 和非严格 replay。

这会带来一个危险结果：demo 看起来很强，复杂模型一旦进入参数变化、拓扑变化、跨进程 replay、GUI roundtrip、自动生成代码迭代，就会出现“没报错但选错面/少输出/变成不同模型”的问题。对 CAD 来说，静默错误比显式失败更糟。

## 优先级建议

P0：把 replay 变 strict。

- 缺参数直接报错。
- 缺输入直接报错。
- leaf id 没 output 直接报错。
- unknown op 直接报错。
- selection cardinality mismatch 直接报错。
- 保留 permissive replay 也必须显式 opt-in。

P0：修 GraphSession 和 workplane context。

- `_active_session` 改成 `contextvars.ContextVar` 或 session stack。
- `_recording_suspend_depth` 同样 context-local。
- `_current_cs` 至少 context-local，最好 frame 显式进入 replay。
- replay 必须使用 node.context 或 frame graph 重建坐标上下文。

P0：把 QL/SelectionSpec 升为 canonical selection。

- SelectionSpec 加 source node/output slot。
- replay 改成 QL first。
- topo refs、indices、hints 只做 fallback。
- 支持 multi-key order。
- 支持 `at_least`、`at_most`。

P1：统一 canonical op 和 schema version。

- 明确 source API、canonical graph op、model JSON schema 三层。
- 移除或隔离 legacy op names。
- `2.0-draft`、`2.0-final-state` 不要混用。
- canonical op coverage 变成测试强约束。

P1：修 boolean/tracking/replay faithful。

- tracking builder 和 actual boolean builder 使用相同参数。
- union replay 传回 `clean`、`glue`、`tol`。
- multi-tool cut/intersect 保留完整 delta chain。
- 无交集 tool 是否跳过应由参数控制，Graph replay 默认不跳过。

P1：收敛 tag schema。

- normalized tags 成为默认。
- legacy numeric tags 移出 tags，放 metadata[`geo`]。
- anchor lookup 明确 role > anchor > face/edge/wire > legacy。
- QL docs 使用 normalized tags。

P2：装配系统诚实命名并逐步增强。

- 当前称 layout solver，不称完整 assembly solver。
- 先修 frame export rotation。
- 再做 DOF/overconstraint diagnostics。

P2：scalar field 数学语义统一。

- 决定是否承诺 SDF。
- smooth booleans 只允许可比 distance fields。
- surface extraction 对 closure/validity 给硬失败或明确 warning。

## 最终评价

这套 SDK 最值得肯定的是 API 直觉：用函数表达 CAD 操作，用返回类型后缀表达几何类型，用 GraphSession 捕获建模过程，用 model JSON 做 replay 边界。这条路线是对的，不应该推翻。

最需要批评的是工程契约：它现在过于相信 OCC runtime identity，过于容忍 replay 缺失，过于依赖 hidden mutable metadata，过早把 draft schema 包装成 canonical contract，过少用失败来保护用户。

CAD 软件架构里，能建出模型只是第一层；能在参数变化后稳定找到同一个语义面，能跨进程 replay 出同一个设计，能在选择歧义时拒绝继续，能在 schema 损坏时报错，才是 SDK 级别的可靠性。

SimpleCADAPI 已经有正确的外形和几块关键骨架。下一阶段不应该继续堆更多 primitive，而应该把 graph、selection、topology、schema、test 这些基础层做硬。否则 API 越漂亮，用户越容易误以为它已经是稳定 CAD 平台。

最终判断：保留顶层 API，收紧内部契约；少加功能，多加确定性；少相信对象身份，多表达语义选择；少 silent fallback，多 fail fast。
