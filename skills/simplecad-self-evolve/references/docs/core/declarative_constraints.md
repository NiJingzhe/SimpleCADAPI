# 声明式约束布局（Declarative Constraints）设计草案

## 背景与目标

当前 SimpleCADAPI 主要是命令式建模：开发者需要手动给出具体坐标、旋转角度和偏移量。对于装配体来说，这种方式在以下场景下成本较高：

1. 几何关系稳定但尺寸会频繁变化（改参数后需要反复重算位置）。
2. 多零件之间依赖复杂（一个零件变化会连锁影响多个零件）。
3. 需要表达“关系”而不是“数值”（例如同轴、贴合、等间距分布）。

Web 布局（如 HTML/CSS 的 Flexbox）证明了一个有效方向：

- 用户声明约束（对齐、分布、间距）。
- 求解器在布局树中传播约束并计算最终几何值。

本提案希望把这一思路迁移到 CAD SDK：

- 保留现有命令式 API；
- 增加一个可选的声明式装配层；
- 让用户描述装配关系，由 SDK 计算每个零件的最终位姿。

## 当前实现状态（feat/declarative-constraints-layout）

当前分支已提供一个可运行的 MVP，核心能力如下：

- 新增模块：`simplecadapi.constraints`
- 新增对象：`Assembly`、`PartHandle`、`PointAnchor`、`AxisAnchor`、`AssemblyResult`
- 支持混合范式：
  - 先命令式预定位（`translate_part` / `rotate_part`）
  - 再声明式约束求解（`coincident` / `concentric` / `offset` / `distance`）
- 支持一维容器语法糖：`stack(...)`
- `stack(...)` 新增主轴分布参数：`justify=start|center|end|space-between`
- 当需要 `justify=center/end/space-between` 时，可通过 `bounds=(start_anchor, end_anchor)`
  指定容器主轴边界。

当前布局实现采用 **BBox-first** 策略：

- 对齐与分布主要基于 `bbox.*` 锚点（AABB）。
- 这与 Flexbox 的盒模型思想一致，但在 3D 下是近似语义：
  当零件发生旋转时，AABB 会变化，布局结果会随之变化。
- 后续可在此基础上增加 OBB/特征面锚点，降低旋转带来的近似误差。
- 支持装配树父子关系与局部/世界变换传播

框架风格约束（函数式）已经被显式化为两类映射：

1. **Type-1 提升映射**（参数空间 -> CAD对象空间）
   - 例如：`make_*_rsolid`、`make_assembly_rassembly`
2. **Type-2 代数变换映射**（CAD对象空间 -> CAD对象空间/结果空间）
   - 例如：`translate_part_rassembly`、`constrain_offset_rassembly`、`stack_rassembly`
   - 求解使用 `solve_assembly_rresult`，保证不修改输入装配对象

对应的函数式 API（不修改输入）包括：

- `make_assembly_rassembly`
- `clone_assembly_rassembly`
- `add_part_rassembly`
- `translate_part_rassembly` / `rotate_part_rassembly`
- `constrain_coincident_rassembly` / `constrain_concentric_rassembly`
- `constrain_offset_rassembly` / `constrain_distance_rassembly`
- `stack_rassembly`
- `solve_assembly_rresult`

函数式管线示例：

```python
import simplecadapi as scad

asm0 = scad.make_assembly_rassembly([
    ("sleeve", sleeve_solid),
    ("rod", rod_solid),
])

asm1 = scad.translate_part_rassembly(asm0, "rod", (3.0, -2.0, 4.0))
asm2 = scad.constrain_concentric_rassembly(
    asm1,
    asm1.part("sleeve").axis("z"),
    asm1.part("rod").axis("z"),
)
asm3 = scad.constrain_offset_rassembly(
    asm2,
    asm2.part("sleeve").anchor("bbox.bottom"),
    asm2.part("rod").anchor("bbox.bottom"),
    3.0,
    axis="z",
)

result = scad.solve_assembly_rresult(asm3)
```

示例（混合使用）：

```python
import simplecadapi as scad

asm = scad.Assembly("demo")
sleeve = asm.add_part("sleeve", sleeve_solid)
rod = asm.add_part("rod", rod_solid)

# 命令式预定位
asm.translate_part("rod", (3.0, -2.0, 4.0), frame="world")

# 声明式约束
asm.concentric(sleeve.axis("z"), rod.axis("z"))
asm.offset(sleeve.anchor("bbox.bottom"), rod.anchor("bbox.bottom"), 3.0, axis="z")

result = asm.solve()
scad.export_step(result.solids(), "assembly.step")
```

## 范围（Scope）

### In Scope（第一阶段）

- 面向装配体的位姿求解（刚体 6DOF，不改零件拓扑）。
- 基础约束类型：
  - `coincident`（点/面/轴重合）
  - `concentric`（同轴）
  - `parallel` / `perpendicular`（方向关系）
  - `distance`（间距）
  - `offset`（沿法向或轴向偏移）
- “Flex-like” 一维布局容器：
  - `stack(axis="x|y|z")`
  - `gap`
  - `justify`（start/center/end/space-between）
  - `align`（start/center/end/stretch*）

`stretch` 在 CAD 中不做几何拉伸，仅表示按对齐基准贴齐。

### Out of Scope（第一阶段）

- 参数驱动的拓扑重建（例如自动改孔径、重生成倒角）。
- 通用非线性符号求解器（CAS 级别）。
- 完整草图约束系统（2D sketch solver）。

## 核心抽象

### 1) 装配节点（Assembly Node）

每个节点包含：

- `name`
- `solid`
- `local frame`（节点本地坐标系）
- `current transform`（待求解变量）
- `anchors`（可被约束引用的锚点）

### 2) 锚点（Anchor）

锚点用于从几何体提取可约束对象：

- `point`: 3D 点
- `axis`: 有向直线（点 + 方向）
- `plane`: 平面（点 + 法向）
- `frame`: 局部坐标系

建议内置锚点来源：

- 包围盒：`bbox.min/max/center`
- 主轴：`axis.x/y/z`
- 命名面：`face("top")`、`face("bottom")`（复用现有标签机制）

### 3) 约束（Constraint）

约束由下列信息组成：

- `type`
- `lhs anchor` / `rhs anchor`
- `value`（可选，例如距离）
- `priority`（hard/soft）
- `weight`（软约束权重）

### 4) 布局容器（Layout Container）

容器是约束语法糖，编译为一组基础约束：

- 例如 `stack([A,B,C], axis="z", gap=8)`
  - `B.min_z = A.max_z + 8`
  - `C.min_z = B.max_z + 8`
  - 再附加对齐约束（如 XY 居中）

## API 草案

```python
import simplecadapi as scad
from simplecadapi.constraints import Assembly, stack

asm = Assembly(name="shock_absorber")

sleeve = asm.add_part("sleeve", sleeve_solid)
rod = asm.add_part("rod", rod_solid)
spring = asm.add_part("spring", spring_solid)

asm.concentric(rod.axis("z"), sleeve.axis("z"))
asm.offset(rod.anchor("bottom"), sleeve.anchor("bottom"), 10.0)
asm.distance(rod.anchor("top"), sleeve.anchor("top"), min_value=5.0)

stack(
    asm,
    parts=[spring],
    axis="z",
    relative_to=sleeve,
    align="center",
    justify="start",
    gap=8.0,
)

result = asm.solve()
solids = result.solids()
scad.export_step(solids, "shock_absorber_assembly.step")
```

## 求解策略（分层）

### Layer A: 解析与规范化

- 把约束和容器规则统一转换为残差方程（residuals）。
- 把锚点引用映射为实时几何查询函数。

### Layer B: 图约束传播（快速路径）

- 对可直接传播的刚性约束先做拓扑求解：
  - 同轴 + 偏移 + 对齐可直接推导部分位姿。
- 构建依赖图并做增量更新（dirty propagation）。

### Layer C: 数值求解（兜底）

- 对剩余自由度采用最小二乘求解（hard 约束优先级最高）。
- 对过约束、矛盾约束输出诊断报告：
  - 冲突约束对
  - 残差最高的约束
  - 推荐放松项（从 hard 降 soft）

## 结果模型

`solve()` 返回对象建议包含：

- `transforms`: 每个零件最终位姿
- `solids()`: 应用位姿后的实体列表
- `report`: 求解信息
  - 是否收敛
  - 迭代次数
  - 最大残差
  - 冲突/过约束说明

## 与现有 API 的兼容策略

1. 不改动现有 `operations.py` 的命令式接口。
2. 新增独立模块（建议 `simplecadapi.constraints`）。
3. 导出仍复用 `export_step` / `export_stl`，可直接导出 `result.solids()`。

## 里程碑计划

### M0 - 设计与可行性验证（当前阶段）

- 输出本设计文档。
- 定义最小 API 面。
- 选定第一批约束类型与诊断格式。

### M1 - 最小可用原型（MVP）

- `Assembly.add_part()`
- 锚点：`bbox` + `axis` + `face tag`
- 约束：`concentric` + `offset` + `distance`
- 求解：支持单链装配（无回环）

### M2 - Flex-like 布局容器

- `stack(axis, gap, align, justify)`
- 把容器规则编译为约束
- 支持简单增量更新

### M3 - 诊断与工程化

- 冲突定位与可解释报错
- 求解日志与可视化输出（文本报告）
- 单元测试覆盖典型装配场景

### M4 - 进阶能力

- 软约束权重系统
- 复杂约束回环
- 性能优化（缓存、分区求解）

## 测试建议

至少覆盖以下场景：

1. **基础收敛**：同轴 + 偏移 + 对齐，结果唯一。
2. **欠约束**：自由度未锁定时返回明确告警。
3. **过约束**：矛盾约束时给出冲突诊断。
4. **增量更新**：修改单参数仅触发局部重算。
5. **导出一致性**：`result.solids()` 可直接导出 STEP/STL。

## 风险与应对

- **风险：** 约束语义过于抽象导致 API 难用。  
  **应对：** 先从装配高频场景切入，只提供少量强语义约束。

- **风险：** 数值求解不稳定。  
  **应对：** 先做图传播快速路径，数值求解仅处理剩余自由度。

- **风险：** 与现有用户代码冲突。  
  **应对：** 新模块隔离、默认不启用、严格保持向后兼容。

## 结论

把 Flexbox 式“声明关系 -> 求解几何”的范式迁移到 CAD SDK 是可行的，且能明显提升装配建模效率与可维护性。建议以“装配位姿约束 + 一维容器布局”作为第一阶段切入点，先交付 MVP，再逐步增强求解能力和诊断体验。
