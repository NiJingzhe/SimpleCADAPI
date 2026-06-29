# Assembly Constraint API Design

本文定义 SimpleCADAPI 的装配体约束 lake。这里使用 `Constraint`，不使用 `Mate` 作为核心术语。

核心定义：

- `Connector` 是固定在 `Part` 或 `Assembly` 定义上的语义坐标系。
- `ConnectorRef` 是某个 component instance 上的某个 connector 引用。
- `Constraint` 描述两个 connector refs 之间必须满足的数学关系。
- Solver 决定哪个 component 移动；constraint 本身不表达 parent 或 child。
- Public API 签名禁止裸星号参数、可变位置参数、可变关键字参数。

## Lake 边界

当前版本的 implemented lake 完整覆盖 connector-frame based assembly constraints 的前三类：

- fixed constraint。
- revolute constraint。
- prismatic constraint。
- grounding、solving、residual inspection、strict replay、model JSON、FreeCAD translation。

后续版本再扩展以下 constraint，不混进当前实现版本：

- cylindrical constraint。
- planar constraint。
- spherical constraint。
- cylindrical、planar、spherical 的 drive scalar 和 scalar limit。

本 lake 不直接做任意 geometry contact mate，例如 tangent surface、arbitrary face coincidence、拖拽式未知量闭环求解。这些可以通过后续 geometry-to-connector layer 或 nonlinear mate solver lake 实现。

## Connector

Connector 不是 geometry instance。Connector 是 owner-local 坐标中的 datum frame。

```python
Connector(
    connector_id: str,
    placement: Placement,
    name: str | None = None,
)
```

字段：

| 字段 | 类型 | 意义 |
| --- | --- | --- |
| `connector_id` | `str` | 在 owner 内唯一的 connector id。 |
| `placement` | `Placement` | connector-local 到 owner-local 的变换。 |
| `name` | `str | None` | 人类可读名称，不参与求解。 |

解释：

- 如果 owner 是 `Part`，connector 固定在 part-local 坐标中。
- 如果 owner 是 `Assembly`，connector 固定在 assembly-local 坐标中，用于子装配对外暴露连接点。
- 同一个 Part 被实例化多次时，connector definition 只有一份，但每个 component 都会解析出自己的 connector instance。

计算：

```text
connector_instance_frame = component_placement · connector_placement
```

## ConnectorRef

```python
ConnectorRef(
    component_id: str,
    connector_id: str,
)
```

字段：

| 字段 | 类型 | 意义 |
| --- | --- | --- |
| `component_id` | `str` | Assembly 内的 component id。 |
| `connector_id` | `str` | 该 component 引用 item 上的 connector id。 |

解释：

- `ConnectorRef` 不直接保存 geometry。
- `ConnectorRef` 通过 `component_id` 找到 component，再通过 `connector_id` 在 component item 的 Part 或 Assembly 上解析 connector。

## ScalarLimit

```python
ScalarLimit(
    lower_value: float,
    upper_value: float,
)
```

字段：

| 字段 | 类型 | 意义 |
| --- | --- | --- |
| `lower_value` | `float` | 允许的最小 scalar 值。 |
| `upper_value` | `float` | 允许的最大 scalar 值。 |

规则：

- 角度 scalar 使用 degrees。
- 距离 scalar 使用模型长度单位。
- `lower_value` 和 `upper_value` 必须是 finite number。
- `lower_value` 必须小于或等于 `upper_value`。
- drive value 如果存在，必须落在 limit 闭区间内。

## Relative Frame Coordinates

所有 constraint 都先解析两个 connector instance frames：

```text
A = placement(component_a) · placement(connector_a)
B = placement(component_b) · placement(connector_b)
D = inverse(A) · B
```

`D` 是 connector B 相对于 connector A 的坐标。各种 constraint 的 scalar 参数都基于 `D` 定义。

常用 scalar：

| Scalar | 单位 | 含义 |
| --- | --- | --- |
| `x_distance` | length | `D.origin.x`。 |
| `y_distance` | length | `D.origin.y`。 |
| `z_distance` | length | `D.origin.z`。 |
| `angle_degrees` | degrees | connector B 绕 connector A 的正 Z 轴相对旋转角。 |
| `swing_angle_degrees` | degrees | connector B 的 Z 轴偏离 connector A 正 Z 轴的夹角。 |
| `swing_direction_degrees` | degrees | connector B 的 Z 轴投影到 connector A XY 平面后的方位角。 |
| `twist_degrees` | degrees | 完成 swing 后，connector B 绕自身正 Z 轴的相对 twist。 |

## Rotation Scalar Rule

公开 API 不暴露 Euler angle 三元组，也不暴露 raw rotation vector 分量。

规则：

- 一维自然转轴使用 signed `angle_degrees`。
- `angle_degrees` 总是绕 connector A 的正 Z 轴，符合右手定则。
- planar、revolute、cylindrical 都使用同一种 `angle_degrees`。
- spherical 没有单一自然转轴，使用 swing-twist scalars。
- `swing_angle_degrees` 是非负 cone angle，范围是 `0.0` 到 `180.0`。
- `swing_direction_degrees` 是 connector A XY 平面内的 signed azimuth。
- `twist_degrees` 是 swing 后绕 connector B 正 Z 轴的 signed twist。
- 当 `swing_angle_degrees` 为 `0.0` 时，`swing_direction_degrees` 几何上无意义；实现应保留输入值但 residual 不依赖它。
- 任意完整 orientation drive 后续应使用显式 orientation value，不使用 Euler 三元组。

Angular scalar 规范：

- signed angular scalars 归一化到 `[-180.0, 180.0)`。
- `swing_angle_degrees` 不归一化为 signed angle，它是 `0.0` 到 `180.0` 的 magnitude。
- `ScalarLimit` 对 signed angular scalars 使用非 wrapping 区间。
- 如果用户需要跨越 `180/-180` 的 wrapping 区间，后续应引入专门的 angular range type，而不是让 `ScalarLimit` 暗含 wrapping 语义。

## Constraint Kinds And Scalars

### fixed

关系：

```text
D == identity
```

自由度：

| Scalar | 状态 |
| --- | --- |
| `x_distance` | fixed at `0.0` |
| `y_distance` | fixed at `0.0` |
| `z_distance` | fixed at `0.0` |
| `orientation` | fixed at identity |

fixed 没有 drive 参数，也没有 limit 参数。

### revolute

关系：

```text
D.origin == (0, 0, 0)
D.z_axis == connector A positive Z axis
rotation about Z is free unless driven
```

自由度：

| Scalar | 状态 |
| --- | --- |
| `angle_degrees` | free, driven, or limited |

API scalar 参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_angle_degrees` | `float | None` | 如果不是 `None`，固定 revolute 角度。 |
| `angle_limit` | `ScalarLimit | None` | 可选角度范围，单位 degrees。 |

### prismatic

关系：

```text
D.x_distance == 0
D.y_distance == 0
D.rotation == identity
translation along Z is free unless driven
```

自由度：

| Scalar | 状态 |
| --- | --- |
| `z_distance` | free, driven, or limited |

API scalar 参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_distance` | `float | None` | 如果不是 `None`，固定沿 Z 轴滑动距离。 |
| `distance_limit` | `ScalarLimit | None` | 可选距离范围，单位模型长度。 |

### cylindrical

关系：

```text
D.x_distance == 0
D.y_distance == 0
D.z_axis == connector A positive Z axis
translation along Z is free unless driven
rotation about Z is free unless driven
```

自由度：

| Scalar | 状态 |
| --- | --- |
| `z_distance` | free, driven, or limited |
| `angle_degrees` | free, driven, or limited |

API scalar 参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_distance` | `float | None` | 如果不是 `None`，固定沿 Z 轴距离。 |
| `distance_limit` | `ScalarLimit | None` | 可选距离范围，单位模型长度。 |
| `drive_angle_degrees` | `float | None` | 如果不是 `None`，固定绕 Z 轴角度。 |
| `angle_limit` | `ScalarLimit | None` | 可选角度范围，单位 degrees。 |

解释：

- 只给 `drive_distance` 时，仍可绕轴旋转。
- 只给 `drive_angle_degrees` 时，仍可沿轴滑动。
- 两个 drive 都给时，cylindrical 退化成确定 pose 的轴系约束。

### planar

关系：

```text
D.z_distance == 0
D.z_axis == connector A positive Z axis
translation in X and Y is free unless driven
rotation about Z is free unless driven
```

自由度：

| Scalar | 状态 |
| --- | --- |
| `x_distance` | free, driven, or limited |
| `y_distance` | free, driven, or limited |
| `angle_degrees` | free, driven, or limited |

API scalar 参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_x_distance` | `float | None` | 如果不是 `None`，固定平面内 X 方向距离。 |
| `x_distance_limit` | `ScalarLimit | None` | 可选 X 距离范围，单位模型长度。 |
| `drive_y_distance` | `float | None` | 如果不是 `None`，固定平面内 Y 方向距离。 |
| `y_distance_limit` | `ScalarLimit | None` | 可选 Y 距离范围，单位模型长度。 |
| `drive_angle_degrees` | `float | None` | 如果不是 `None`，固定平面内绕 Z 轴角度。 |
| `angle_limit` | `ScalarLimit | None` | 可选角度范围，单位 degrees。 |

解释：

- 不给任何 drive 时，B 在 A 的 XY 平面内自由平移和旋转。
- 给 `drive_x_distance` 和 `drive_y_distance` 后，B 的平面内位置固定，但仍可绕 Z 旋转。
- 再给 `drive_angle_degrees` 后，planar 退化成确定 pose 的平面约束。

### spherical

关系：

```text
D.origin == (0, 0, 0)
relative orientation is free unless swing or twist scalars are driven or limited
```

自由度：

| Scalar | 状态 |
| --- | --- |
| `swing_direction_degrees` | free, driven, or limited |
| `swing_angle_degrees` | free, driven, or limited |
| `twist_degrees` | free, driven, or limited |

API scalar 参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_swing_direction_degrees` | `float | None` | 如果不是 `None`，固定 swing 方位角。 |
| `swing_direction_limit` | `ScalarLimit | None` | 可选 swing 方位角范围，单位 degrees。 |
| `drive_swing_angle_degrees` | `float | None` | 如果不是 `None`，固定 swing cone angle。 |
| `swing_angle_limit` | `ScalarLimit | None` | 可选 swing cone angle 范围，单位 degrees。 |
| `drive_twist_degrees` | `float | None` | 如果不是 `None`，固定 twist angle。 |
| `twist_limit` | `ScalarLimit | None` | 可选 twist 范围，单位 degrees。 |

解释：

- 不给任何 drive 时，就是纯 ball joint，只要求两个 connector origins 重合。
- 给一个或多个 drive 时，会锁定对应 swing-twist scalar。
- 三个 drive 都给时，spherical 退化成确定 orientation 的点重合约束。
- spherical 不使用 Euler angle，也不使用 rotation vector 分量。

## Public APIs

### make_connector_rconnector

```python
make_connector_rconnector(connector_id, placement, name=None) -> Connector
```

创建显式 connector。`placement` 是 connector-local 到 owner-local 的变换。

### make_axis_connector_rconnector

```python
make_axis_connector_rconnector(connector_id, origin, axis, x_hint=(1.0, 0.0, 0.0), name=None) -> Connector
```

用 origin 和 axis 创建 connector。`axis` 成为 connector 正 Z 轴。`x_hint` 投影到垂直于 axis 的平面后成为 connector X 轴。

计算：

```text
z_axis = normalize(axis)
x_raw = x_hint - dot(x_hint, z_axis) · z_axis
x_axis = normalize(x_raw)
y_axis = z_axis cross x_axis
placement = Placement(origin, x_axis, y_axis)
```

### add_connector_rpart

```python
add_connector_rpart(part, connector) -> Part
```

把 connector 添加到 Part。connector placement 按 part-local 坐标解释。

### add_connector_rassembly

```python
add_connector_rassembly(assembly, connector) -> Assembly
```

把 connector 添加到 Assembly。connector placement 按 assembly-local 坐标解释。

### make_connector_ref_rconnectorref

```python
make_connector_ref_rconnectorref(component_id, connector_id) -> ConnectorRef
```

创建 connector ref。connector ref 只是引用，不解析 geometry。

### make_scalar_limit_rscalarlimit

```python
make_scalar_limit_rscalarlimit(lower_value, upper_value) -> ScalarLimit
```

创建 scalar limit。单位由使用它的 constraint scalar 决定。

### ground_component_rassembly

```python
ground_component_rassembly(assembly, component_id) -> Assembly
```

把 component 的当前 placement 作为 solver 固定边界。

### unground_component_rassembly

```python
unground_component_rassembly(assembly, component_id) -> Assembly
```

移除 component 的 ground 状态。

### add_fixed_constraint_rassembly

```python
add_fixed_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    name=None,
) -> Assembly
```

参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `assembly` | `Assembly` | constraint 所属 Assembly。 |
| `constraint_id` | `str` | Assembly 内唯一 constraint id。 |
| `connector_a` | `ConnectorRef` | 第一个 connector ref。 |
| `connector_b` | `ConnectorRef` | 第二个 connector ref。 |
| `name` | `str | None` | 人类可读名称。 |

计算：

```text
D = inverse(A) · B
require D == identity
```

### add_revolute_constraint_rassembly

```python
add_revolute_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    drive_angle_degrees=None,
    angle_limit=None,
    name=None,
) -> Assembly
```

参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_angle_degrees` | `float | None` | 固定 revolute 角度；`None` 表示角度自由。 |
| `angle_limit` | `ScalarLimit | None` | 角度范围，单位 degrees。 |

### add_prismatic_constraint_rassembly

```python
add_prismatic_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    drive_distance=None,
    distance_limit=None,
    name=None,
) -> Assembly
```

参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_distance` | `float | None` | 固定沿 Z 轴距离；`None` 表示滑动自由。 |
| `distance_limit` | `ScalarLimit | None` | 距离范围，单位模型长度。 |

### add_cylindrical_constraint_rassembly

```python
add_cylindrical_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    drive_distance=None,
    distance_limit=None,
    drive_angle_degrees=None,
    angle_limit=None,
    name=None,
) -> Assembly
```

参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_distance` | `float | None` | 固定 `z_distance`；`None` 表示沿轴平移自由。 |
| `distance_limit` | `ScalarLimit | None` | `z_distance` 范围。 |
| `drive_angle_degrees` | `float | None` | 固定 `angle_degrees`；`None` 表示绕轴旋转自由。 |
| `angle_limit` | `ScalarLimit | None` | `angle_degrees` 范围。 |

### add_planar_constraint_rassembly

```python
add_planar_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    drive_x_distance=None,
    x_distance_limit=None,
    drive_y_distance=None,
    y_distance_limit=None,
    drive_angle_degrees=None,
    angle_limit=None,
    name=None,
) -> Assembly
```

参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_x_distance` | `float | None` | 固定 `x_distance`；`None` 表示 X 平移自由。 |
| `x_distance_limit` | `ScalarLimit | None` | `x_distance` 范围。 |
| `drive_y_distance` | `float | None` | 固定 `y_distance`；`None` 表示 Y 平移自由。 |
| `y_distance_limit` | `ScalarLimit | None` | `y_distance` 范围。 |
| `drive_angle_degrees` | `float | None` | 固定平面内 `angle_degrees`；`None` 表示绕 Z 旋转自由。 |
| `angle_limit` | `ScalarLimit | None` | `angle_degrees` 范围。 |

### add_spherical_constraint_rassembly

```python
add_spherical_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    drive_swing_direction_degrees=None,
    swing_direction_limit=None,
    drive_swing_angle_degrees=None,
    swing_angle_limit=None,
    drive_twist_degrees=None,
    twist_limit=None,
    name=None,
) -> Assembly
```

参数：

| 参数 | 类型 | 意义 |
| --- | --- | --- |
| `drive_swing_direction_degrees` | `float | None` | 固定 swing 方位角；`None` 表示该方位自由。 |
| `swing_direction_limit` | `ScalarLimit | None` | swing 方位角范围，单位 degrees。 |
| `drive_swing_angle_degrees` | `float | None` | 固定 swing cone angle；`None` 表示 cone angle 自由。 |
| `swing_angle_limit` | `ScalarLimit | None` | swing cone angle 范围，单位 degrees。 |
| `drive_twist_degrees` | `float | None` | 固定 twist angle；`None` 表示 twist 自由。 |
| `twist_limit` | `ScalarLimit | None` | twist 范围，单位 degrees。 |

### solve_assembly_constraints_rassembly

```python
solve_assembly_constraints_rassembly(assembly, strict=True) -> Assembly
```

根据 ground、connectors、constraints、drive scalars 和 limits 求解 component placements。

当前 implementation 可以先支持树状和可解析 constraint graph，但 public data model 必须保持无向 connector-ref constraint 语义。后续升级到 nonlinear mate solver 时，不需要改变 connector 或 constraint JSON。

### measure_constraint_residual_rconstraintresidual

```python
measure_constraint_residual_rconstraintresidual(assembly, constraint_id) -> ConstraintResidual
```

测量当前 placements 下某个 constraint 的 residual。

### inspect_assembly_constraints_rconstraintreport

```python
inspect_assembly_constraints_rconstraintreport(assembly) -> ConstraintReport
```

检查 Assembly 当前约束状态，包括 grounded components、solved components、unsolved components、free scalar coordinates、limit violations、residuals。

## Validation Rules

- `constraint_id` 在 Assembly 内必须唯一。
- `connector_a` 和 `connector_b` 必须引用同一个 Assembly 内存在的 components。
- connector ref 指向的 connector 必须存在于 component item 的 Part 或 Assembly 上。
- 同一个 constraint 不能连接完全相同的 connector ref。
- drive scalar 必须是 finite number 或 `None`。
- limit 必须是 `ScalarLimit` 或 `None`。
- drive scalar 如果存在，必须落在对应 limit 内。
- `swing_angle_degrees` 必须在 `0.0` 到 `180.0` 之间。
- `swing_angle_degrees` 为 `0.0` 时，`drive_swing_direction_degrees` 不影响 residual。
- `strict=True` 时，unsolved components、inconsistent residuals、limit violations 必须报错。

## Model JSON And Replay

每个 public mutation API 都必须记录显式 typed op：

| API | op 名 |
| --- | --- |
| `make_connector_rconnector` | `make_connector_rconnector` |
| `make_axis_connector_rconnector` | `make_axis_connector_rconnector` |
| `add_connector_rpart` | `add_connector_rpart` |
| `add_connector_rassembly` | `add_connector_rassembly` |
| `make_connector_ref_rconnectorref` | `make_connector_ref_rconnectorref` |
| `make_scalar_limit_rscalarlimit` | `make_scalar_limit_rscalarlimit` |
| `ground_component_rassembly` | `ground_component_rassembly` |
| `unground_component_rassembly` | `unground_component_rassembly` |
| `add_fixed_constraint_rassembly` | `add_fixed_constraint_rassembly` |
| `add_revolute_constraint_rassembly` | `add_revolute_constraint_rassembly` |
| `add_prismatic_constraint_rassembly` | `add_prismatic_constraint_rassembly` |
| `add_cylindrical_constraint_rassembly` | `add_cylindrical_constraint_rassembly` |
| `add_planar_constraint_rassembly` | `add_planar_constraint_rassembly` |
| `add_spherical_constraint_rassembly` | `add_spherical_constraint_rassembly` |
| `solve_assembly_constraints_rassembly` | `solve_assembly_constraints_rassembly` |

Replay 要求：

- model JSON 保存 constraint semantics，不只保存最终 placements。
- replay 后 connector definitions、connector refs、constraints、drive scalars、limits、grounding 必须一致。
- solved placements 可以作为 solve op 输出保存，但不能替代 constraints。
- strict replay 必须重新验证 residuals。

## FreeCAD Translation

FreeCAD translator 行为：

- 输出 native `Assembly::AssemblyObject`。
- component instance 继续用 `App::Link` 或 `Assembly::AssemblyLink`。
- link placement 使用 SimpleCAD solver 后的 placement。
- connector 和 constraint semantics 写入 metadata 或 custom properties。
- 不依赖 FreeCAD solver 才能打开正确姿态。
- 如果 Assembly 有 constraints 但未 solve，translator 执行 strict solve。
- 如果 solve 失败，translation 失败并报告 constraint id 和 residual。

## Examples

Door hinge：

- base grounded。
- door 和 base 之间添加 revolute constraint。
- `drive_angle_degrees=90.0` 展示开门姿态。

Hydraulic actuator：

- cylinder body grounded。
- rod 和 cylinder 之间添加 prismatic constraint。
- `drive_distance=80.0` 展示伸出姿态。

Shaft in bushing：

- bushing grounded。
- shaft 和 bushing 之间添加 cylindrical constraint。
- 同时设置 `drive_distance` 和 `drive_angle_degrees` 展示轴向移动加旋转。

Slider on plate：

- plate grounded。
- slider 和 plate 之间添加 planar constraint。
- 设置 `drive_x_distance`、`drive_y_distance`、`drive_angle_degrees` 展示平面内位置和角度。

Ball joint：

- socket grounded。
- ball stud 和 socket 之间添加 spherical constraint。
- 可只约束 origin，也可设置 swing-twist drives 或 limits。

## Implementation Order

1. Add `Connector`、`ConnectorRef`、`ScalarLimit`、`Constraint`、`ConstraintResidual`、`ConstraintReport` types。
2. Add placement inverse、relative frame、swing-twist extraction helpers。
3. Add connector APIs and validation tests。
4. Add connector ref and scalar limit APIs。
5. Add fixed、revolute、prismatic constraint APIs。
6. Add cylindrical、planar、spherical constraint APIs with scalar drive and limit tests。
7. Add solver and residual inspection。
8. Add serializer and strict replay。
9. Add FreeCAD translator metadata and solved placement tests。
10. Add examples and generated API docs。
11. Run full tests, compile, whitespace checks, examples, FreeCAD checks。
