# STEP BREP 逆向工程方法

该方法论是 SimpleCAD skill 的任务专用参考，规范版本位于：

```text
skills/simplecadapi/references/inverse_engineer/brep-reverse-engineering.md
```

正式检查工具位于：

```text
src/simplecadapi/inverse_engineer/brep/
```

Python API：

```python
from simplecadapi.inverse_engineer import brep

report = brep.inspect_step(path="part.step")
summary = brep.get_model_summary(path="part.step")
face = brep.inspect_entity(path="part.step", entity_id="face:0")
neighborhood = brep.get_topology_neighborhood("part.step", "face:0", depth=2)
section = brep.make_section(
    "part.step",
    origin=[0, 0, 10],
    normal=[0, 0, 1],
)
comparison = brep.compare_global_properties("target.step", "candidate.step")
evaluation = brep.evaluate_result(
    "target.step",
    "candidate.step",
    replay_succeeded=True,
)
```

`get_model_summary` 返回实体数量、包围盒、材料体积/面积、质心和曲面/曲线类型统计。
`inspect_entity` 使用稳定的零基 ID（`body:0`、`face:0`、`edge:0`、`vertex:0`），
返回几何类型、解析参数、测量值和邻接关系。需要在多次查询间复用索引时，可先加载模型：

```python
model = brep.load_step_model("part.step")
summary = model.summary()
face = model.describe_entity("face:0")
neighbors = model.adjacency_details("face:0")
```

这些 ID 对同一未修改 BREP 的重复加载保持确定性，但不代表两个不同模型之间的语义对应关系。
退化边统一报告为 `DEGENERATE`，并通过 `underlying_curve_type` 保留底层曲线载体类型。

面向多轮 Agent 的通用工具集不依赖 LangChain 或 OpenAI SDK：

```python
schemas = brep.agent_tool_schemas()
result = brep.call_agent_tool(
    "inspect_entity",
    {"model_path": "part.step", "entity_id": "face:0"},
)
```

已注册的工具覆盖：

| 调查 | 比较与验收 |
|---|---|
| `get_model_summary` | `compare_global_properties` |
| `inspect_entity` | `compare_boundary_distance` |
| `get_topology_neighborhood` | `compute_material_difference` |
| `measure_relation` | `compare_sections` |
| `make_section` | `build_difference_regions` |
| `extract_face_boundaries` | `find_nearby_entities` |
| `probe_point` | `compare_entities` |
| `render_region` | `evaluate_result` |
|  | `compare_brep_strict` |

`inspect_step()` 的完整报告会保留 B-spline 曲线/曲面的 knot、
multiplicity、control point 和 rational weight。自由曲面转录或拟合时应使用完整报告；
`inspect_entity()` 默认用于低延迟局部调查，只返回 degree 和数量摘要；对曲线实体可设置
`include_curve_definition=True` 获取完整控制点、节点和权重。曲面定义仍应读取完整报告。

初步清点时可调用 `get_model_summary(..., include_parameter_groups=True)`，取得按
解析半径或 B-spline 阶次分组的有界多重度和少量稳定实体 ID。该分组只描述
相同 carrier 参数，不推断阵列、对称或重复特征。必须再用空间位置、方向、
邻接签名和间距验证 pattern 假设。

大轮廓优先使用 `extract_face_boundaries(..., compact=True)`。紧凑模式保留
coedge 顺序、方向、类型、长度、端点和关键参数，不返回 3D/UV 采样数组；只有
拟合或误差测量确实需要时再请求详细模式。

渲染和图片截面功能需要可选依赖：

```bash
uv sync --extra inverse-engineer
```

CLI：

```powershell
uv run simplecad-brep inspect part.step -o part-report.json
uv run simplecad-brep compare target.step candidate.step -o comparison.json
uv run simplecad-brep render candidate.step candidate-views.png
uv run simplecad-brep slices target.step candidate.step slice-overlay.png
uv run simplecad-brep tools
uv run simplecad-brep tool get_model_summary --arguments '{"model_path":"part.step"}' -o summary.json
```

性能原则：闭合实体的迭代验收优先使用有效性、全局属性和双向材料差。
有效布尔结果证明材料一致时即可判定几何等价；拓扑只在明确要求 exact BREP
时检查。`evaluate_result()` 是包含全局边界采样的综合验收接口，不属于低成本迭代路径。
`compare_boundary_distance`、`compare_sections`、
`build_difference_regions` 和局部渲染属于按需诊断，
应在材料不一致后由 Agent 针对可疑区域调用，不应默认对每个候选执行高密度
全局匹配。

`compare_boundary_distance` 默认最多使用 200 个样本，并支持
`target_face_ids`/`current_face_ids` 局部范围。需要将结果交给
`build_difference_regions` 时显式设置 `include_records=true`；随后把该结果和
已计算的材料差作为 `boundary_result`/`material_result` 传入，避免重复计算。
`build_difference_regions` 默认只排序 Boolean 材料差组件；只有
`include_boundary=true` 才增加边界聚类。中心切片仍可通过 Python API 或
`simplecad-brep slices` 使用，但不再暴露为默认 Agent 工具。
