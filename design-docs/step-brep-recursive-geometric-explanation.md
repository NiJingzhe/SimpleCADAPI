# STEP B-Rep 基础几何解释与残差递归算法规范

## 文档状态

- 状态：Proposed
- 规范版本：0.2
- 目标项目：SimpleCADAPI 2.x
- 输入：STEP 导入后得到的 B-Rep snapshot
- 输出：可重放的几何程序、有限解释证据、评分分量和最终验证指标
- v0.2 实体基础单元：Box、Cylinder、Cone、Sphere、Torus、RawBRep
- v0.2 组合操作：Union、Subtract
- v0.2 NURBS 能力：解析曲面约化、NURBS 面证据匹配、RawBRep 兜底；不从开放 NURBS 面猜测实体
- 非目标：证明原始 CAD feature history、识别 NACA 等领域参数族、保证全局最优、从 mesh 恢复解析 B-Rep

## 1. 摘要

STEP B-Rep 提供有限数量的 Face、Edge、Vertex、支撑几何及 topology，但通常不提供原始 primitive、Boolean 和 feature tree。本规范把逆向定义为以下有限搜索：

1. 将输入 B-Rep 转换为有限的面、边和邻接证据原子。
2. 只从输入中出现的有限几何事件枚举 Box、Cylinder、Cone、Sphere 和 Torus 候选。
3. 用显式谓词计算每个候选解释的证据原子 bitset。
4. 用版本化数值代价表达基础单元常见性和参数复杂度。
5. 对候选计算 `R+ = T - H` 和 `R- = H - T`，再递归解释每个 residual solid。
6. 用有硬预算的 Beam Search 枚举有限个完整程序。
7. 从头重放完整程序，并用 symmetric-difference、双向边界距离和法向误差判定几何等价。
8. 在验证通过且所有目标 SurfaceAtom 都有归属的程序中选择总代价最低者。

本文的规范性术语均映射到有限集合、公式、确定排序或返回 `OK | FAILED | TIMEOUT | BUDGET_EXHAUSTED` 的 kernel 调用。说明性文字不创建额外算法分支。

## 2. 输入、程序和总函数

### 2.1 输入

输入实体记为：

\[
T=(V,E,F,A)
\]

其中 `V`、`E`、`F` 和 topology relation 集合 `A` 均为有限集合。

### 2.2 输出程序

```text
Program := Box(parameters)
         | Cylinder(parameters)
         | Cone(parameters)
         | Sphere(parameters)
         | Torus(parameters)
         | RawBRep(snapshot, byte_length, raw_stats)
         | Union(Program, Program)
         | Subtract(Program, Program)
```

内部搜索额外使用占位节点：

```text
Template := Program | Slot(slot_id)
```

完成程序不允许包含 `Slot`。

`RawBRep` 的参数不是 process-local kernel object。它是以下总函数的结果：

```text
SnapshotOf(shape, context) -> KernelResult[BRepSnapshot]

BRepSnapshot
  profile = "simplecad-brep-snapshot-0.2"
  bytes
  sha256 = SHA256(bytes)
```

该 profile 的 encoder 必须保存重放 shape 所需的 Vertex、Edge curve、Face surface、trim、orientation、tolerance 和 topology relation，并对相同 evaluated B-Rep 和 profile 产生相同 bytes。若 backend 不提供该 profile，`SnapshotOf` 返回 `FAILED(UNSUPPORTED_SNAPSHOT_PROFILE)`。`RawBRepKey = snapshot.sha256`，`byte_length = len(snapshot.bytes)`；反序列化时必须重新计算 SHA-256 和 byte length 并相等。

`raw_stats` 是从 snapshot 解码结果重新枚举得到的 closed record：

```text
RawStats
  analytic_face_count
  nurbs_face_records     # 每项含 NurbsCost 所需全部整数
  edge_count
  vertex_count
```

创建节点时从 `ResidualAnalysis` 复制；反序列化时从 snapshot 重算并要求相等。

### 2.3 Kernel 调用总类型

所有可能失败的 kernel 操作统一返回：

```text
KernelResult[T] :=
  OK(value: T)
  | FAILED(code: FailureCode)
  | TIMEOUT
  | BUDGET_EXHAUSTED
```

每次调用前执行：

```text
KernelContext.try_reserve(kind) :=
  if monotonic_clock() >= deadline: TIMEOUT
  elif total_calls + 1 > max_total_calls: BUDGET_EXHAUSTED
  elif kind == BOOLEAN and boolean_calls + 1 > max_boolean_calls: BUDGET_EXHAUSTED
  else increment counters and OK
```

所有 kernel API 都接收 `deadline`。分析阶段调用失败时，整个输入降级为 `RawBRep`；候选阶段调用失败时丢弃该候选；最终验证阶段调用失败时，该程序验证失败。

本规范的调用计数单位是本节列出的逻辑 kernel API 调用，不是 CAD kernel 内部函数调用次数。调用包装器必须在进入 backend 前执行一次 `try_reserve`。纯 CPU 循环每处理 1024 个元素检查一次 deadline；到期后返回 `TIMEOUT`。

特殊失败动作只有以下四类，后文不得隐式覆盖：

```text
initial/residual analysis failure -> 当前 task 只允许 RawExpansion
candidate construction/measurement failure -> 丢弃当前 candidate
residual generation failure -> 丢弃当前 candidate
validation failure -> 当前 program 的 ValidProgram = false
```

初始输入 analysis 失败时，只有 `SnapshotOf(target)` 成功才能返回 RawBRep；否则返回 `ANALYSIS_FAILED` 且 `program = null`。

### 2.4 空 shape

Boolean 结果类型为：

```text
BooleanShape := EMPTY | NONEMPTY(shape)
```

定义：

```text
volume(EMPTY) = 0
surface_area(EMPTY) = 0
components(EMPTY) = []
ValidSolid(EMPTY) = false
```

`EMPTY` 没有 bbox、Face、Edge 或 Vertex，不能成为 Program 叶节点。它只允许出现在 residual 和程序简化过程中。

### 2.5 几何程序执行

```text
Render(Box/Cylinder/Cone/Sphere/Torus) := kernel_construct_primitive(parameters)
Render(RawBRep(snapshot,byte_length,raw_stats)) := kernel_copy(snapshot)
Render(Union(A,B)) := kernel_regularized_union(Render(A), Render(B))
Render(Subtract(A,B)) := kernel_regularized_cut(Render(A), Render(B))
```

任一子调用不是 `OK` 时，父调用返回相同失败状态。

内部验证允许程序简化常量 `EMPTY`：

```text
Union(EMPTY,X) = X
Union(X,EMPTY) = X
Subtract(EMPTY,X) = EMPTY
Subtract(X,EMPTY) = X
```

完成输出程序执行常量折叠后不得含 `EMPTY`。

## 3. 完整配置

### 3.1 配置结构

```text
ReverseConfig
  tolerance:
    eps_linear
    eps_angular
    eps_radius
    eps_surface
    eps_normal
    eps_volume
    eps_area
    eps_length
  discretization:
    face_deflection
    face_angular_deflection
    edge_step
    nurbs_u_samples
    nurbs_v_samples
    max_mesh_area_relative_error
  analysis:
    max_analysis_entities
    max_analysis_total_kernel_calls
    max_event_records
    analysis_timeout_seconds
  candidates:
    max_direction_clusters
    max_extent_pairs_per_axis
    max_box_frames
    max_box_candidates_per_frame
    max_candidates_per_type
    boolean_prefilter_top_m
    min_trigger_entities
    min_support_coverage
    max_candidate_attempts_per_task
    max_candidate_kernel_calls_per_task
  score:
    reward_support
    reward_boundary
    reward_edge
    reward_adjacency
    penalty_leaf_cost
    unmatched_support_penalty
    unmatched_boundary_penalty
    unmatched_edge_penalty
    expansion_margin
  cost:
    type_cost_box
    type_cost_cylinder
    type_cost_cone
    type_cost_sphere
    type_cost_torus
    type_cost_nurbs_face
    type_cost_raw_brep
    operation_cost_union
    operation_cost_subtract
    scalar_parameter_cost
  search:
    beam_width
    max_task_depth
    max_expanded_states
    max_search_total_kernel_calls
    max_search_boolean_calls
    search_timeout_seconds
    max_completed_programs_to_validate
    max_pending_tasks_per_state
  validation:
    max_validation_total_kernel_calls
    max_validation_boolean_calls
    validation_timeout_seconds
```

### 3.2 默认容差

令输入 bbox 对角线为 `D`，STEP entity tolerance 最大值为 `t_step`：

\[
\epsilon_{linear}=\max(t_{step},10^{-9}D)
\]

\[
\epsilon_{surface}=2\epsilon_{linear}
\]

\[
\epsilon_{radius}=2\epsilon_{linear}
\]

\[
\epsilon_{angular}=10^{-7}
\]

\[
\epsilon_{normal}=10^{-6}
\]

\[
\epsilon_{volume}=\max(10^{-12}D^3,10\epsilon_{linear}^3)
\]

\[
\epsilon_{area}=\max(10^{-12}D^2,10\epsilon_{linear}^2)
\]

\[
\epsilon_{length}=\epsilon_{linear}
\]

角度单位为 radian，长度单位采用导入后统一的模型单位。

### 3.3 默认离散化与预算

```text
face_deflection = max(eps_surface / 2, 1e-6 * D)
face_angular_deflection = eps_normal / 2
edge_step = max(eps_length, 1e-4 * D)
nurbs_u_samples = 9
nurbs_v_samples = 9
max_mesh_area_relative_error = 1e-3

max_analysis_entities = 1000000
max_analysis_total_kernel_calls = 1000000
max_event_records = 1000000
analysis_timeout_seconds = 120

max_direction_clusters = 12
max_extent_pairs_per_axis = 8
max_box_frames = 64
max_box_candidates_per_frame = 16
max_candidates_per_type = 24
boolean_prefilter_top_m = 16
min_trigger_entities = 1
min_support_coverage = 0.01
max_candidate_attempts_per_task = 10000
max_candidate_kernel_calls_per_task = 100000

reward_support = 10.0
reward_boundary = 5.0
reward_edge = 2.0
reward_adjacency = 1.0
penalty_leaf_cost = 1.0
unmatched_support_penalty = 5.0
unmatched_boundary_penalty = 2.0
unmatched_edge_penalty = 1.0
expansion_margin = 2.0

type_cost_box = 1.0
type_cost_cylinder = 1.0
type_cost_cone = 1.5
type_cost_sphere = 1.5
type_cost_torus = 2.0
type_cost_nurbs_face = 4.0
type_cost_raw_brep = 8.0
operation_cost_union = 0.5
operation_cost_subtract = 0.5
scalar_parameter_cost = 0.05

beam_width = 8
max_task_depth = 10
max_expanded_states = 1000
max_search_total_kernel_calls = 1000000
max_search_boolean_calls = 500
search_timeout_seconds = 120
max_completed_programs_to_validate = 32
max_pending_tasks_per_state = 256

max_validation_total_kernel_calls = 1000000
max_validation_boolean_calls = 500
validation_timeout_seconds = 120
```

### 3.4 配置合法性

`ConfigValid(config)` 当且仅当：

- 所有浮点配置均为 finite。
- 所有 `eps_*`、`face_deflection`、`face_angular_deflection`、`edge_step` 和 timeout 严格大于 `0`。
- `0 < eps_angular < pi/2` 且 `0 < eps_normal < pi/2`。
- `nurbs_u_samples >= 3` 且 `nurbs_v_samples >= 3`。
- `0 <= max_mesh_area_relative_error < 1`。
- 所有 `max_*`、`beam_width` 和 `boolean_prefilter_top_m` 是有限正整数。
- `min_trigger_entities` 是有限非负整数。
- `0 <= min_support_coverage <= 1`。
- 所有 reward、penalty 和 cost 是 finite 且大于等于 `0`。

输入数值合法性：

```text
FiniteBRep(T) :=
  every bbox coordinate, Vertex coordinate, curve parameter,
  surface parameter, knot, weight and tolerance used by this algorithm is finite
  and every radius used by an analytic record is > 0
  and every direction consumed by normalize has norm > eps_linear
```

`t_step` 为所有 finite entity tolerance 的最大值；没有 entity tolerance 时取 `0`。`FiniteBRep == false` 时返回 `INVALID_INPUT`。

`ConfigValid == false` 时返回 `INVALID_CONFIG`，不调用 kernel。

## 4. 量化与确定顺序

### 4.1 量化

定义半数向正无穷舍入：

\[
Q(x,\epsilon)=\lfloor x/\epsilon+1/2\rfloor
\]

\[
Q_3(p,\epsilon)=(Q(p_x,\epsilon),Q(p_y,\epsilon),Q(p_z,\epsilon))
\]

单位方向 `d` 的规范符号：找到绝对值最大的分量；多个分量同大时按 `x,y,z` 选择第一个；若该分量小于 `0`，令 `d := -d`。

\[
Q_d(d)=Q_3(d,\sin(\epsilon_{angular}))
\]

### 4.2 基本方向谓词

定义有向夹角：

\[
angle(a,b)=acos(clamp(dot(a/\|a\|,b/\|b\|),-1,1))
\]

只有 `norm(a) > eps_linear` 且 `norm(b) > eps_linear` 时定义；否则调用该谓词的 match 结果为 `false`。

\[
parallel(a,b):=angleAbs(a,b)\leq\epsilon_{angular}
\]

其中：

\[
angleAbs(a,b)=acos(clamp(|dot(a,b)|,-1,1))
\]

\[
perpendicular(a,b):=|dot(a,b)|\leq\sin(\epsilon_{angular})
\]

两轴线 `(q1,d1)`、`(q2,d2)` 共轴：

```text
coaxial := parallel(d1,d2)
           and norm((q2-q1) - d1*dot(d1,q2-q1)) <= eps_linear
```

### 4.3 Bbox 相交

闭区间 bbox `A`、`B` 相交当且仅当每个轴 `k` 满足：

\[
A_{min,k}\leq B_{max,k}\land B_{min,k}\leq A_{max,k}
\]

`expand(B, e)` 将每个最小坐标减 `e`，每个最大坐标加 `e`。

### 4.4 Canonical serialization

所有 canonical record 使用 UTF-8 JSON，object key 按 UTF-8 byte order 排序，禁止 NaN 和 Infinity，浮点参数先替换为本文定义的量化整数。

```text
CandidateKey = canonical_json({type, quantized_parameters})
RawBRepKey = snapshot.sha256
ProgramKey = canonical_json(program tree with CandidateKey or RawBRepKey leaves)
```

程序树不做交换律重排；`FoldUnion` 的输入排序在第 15 节定义。

## 5. 输入分析

### 5.1 初始化顺序

1. 从导入 shape 计算 bbox；失败返回 `ANALYSIS_FAILED` 和 `RawBRep`。
2. 计算 `D`；若 `D <= 0` 返回 `INVALID_INPUT`。
3. 若 bbox 坐标或 `D` 非 finite，返回 `INVALID_INPUT`。
4. 计算默认配置或读取覆盖配置。
5. 若 `ConfigValid == false` 返回 `INVALID_CONFIG`。
6. 创建独立 analysis context，其 deadline 和调用上限来自 `analysis.*`。
7. 若实体总数超过 `max_analysis_entities`，返回 `ANALYSIS_FAILED`。
8. 检查 `FiniteBRep`。
9. 执行本节其余步骤。

### 5.2 Solid 有效性

```text
ValidSolid(T) :=
  kernel_is_valid(T) == OK(true)
  and solid_count(T) == 1
  and open_shell_count(T) == 0
  and closed_shell_count(T) >= 1
  and non_manifold_edge_count(T) == 0
  and abs(volume(T)) > eps_volume
```

任一测量调用失败，`ValidSolid` 为 `false`。若为 `false`，返回 `RawBRep(T)` 和 `INVALID_SOLID`。v0.2 不隐式 repair。

## 6. 有限证据原子

### 6.1 SurfaceAtom

对每张 Face 调用固定参数三角化。调用失败时分析失败。对每个面积严格大于 `0` 的三角形 `(a,b,c)` 生成：

```text
SurfaceAtom
  atom_id
  source_face_id
  point = (a+b+c)/3
  oriented_normal
  area = norm(cross(b-a,c-a))/2
```

`oriented_normal` 按 Face orientation 修正。`atom_id` 按 `(source_face_key, Q3(point), Q(area, eps_area), local_triangle_key)` 排序后编号。`local_triangle_key` 是三角形三个量化顶点排序后的 tuple。

记集合为 `SA(T)`：

\[
W_S(T)=\sum_{a\in SA(T)}a.area
\]

调用 kernel 计算真实表面积 `A_kernel`。只有满足：

\[
W_S(T)>0
\]

且：

\[
|W_S(T)-A_{kernel}|\leq\max(\epsilon_{area},
maxMeshAreaRelativeError\cdot A_{kernel})
\]

分析才继续，否则返回 `MESH_COVERAGE_FAILED` 和 `RawBRep`。

### 6.2 EdgeAtom

跳过 kernel 标记为 degenerated 或 seam 的 Edge。对其余 Edge 计算弧长 `L`。失败时跳过该 Edge 并记录 diagnostic。若 `L <= eps_length`，跳过。

\[
n=\max(1,\lceil L/edgeStep\rceil)
\]

按等弧长区间取中点和单位切向，生成：

```text
EdgeAtom
  atom_id
  source_edge_id
  point
  unit_tangent
  length_weight = L/n
```

任一中点求值失败时跳过整条 Edge。记集合为 `EA(T)`：

\[
W_E(T)=\sum_{e\in EA(T)}e.lengthWeight
\]

### 6.3 AdjacencyAtom

对每条非 seam、非 degenerated Edge，取得 incident oriented Face uses。若恰有两个不同 Face，生成：

```text
AdjacencyAtom
  atom_id
  source_edge_id
  face_a_id = min(face keys)
  face_b_id = max(face keys)
  weight = edge_length
```

Edge 长度失败或小于等于 `eps_length` 时不生成。集合记为 `AA(T)`：

\[
W_A(T)=\sum_{r\in AA(T)}r.weight
\]

## 7. 支撑几何 key

### 7.1 Plane

Plane 用单位法向 `n` 和 `h = dot(n,origin)` 表示。按第 4.1 节规范 `n` 符号；若翻转 `n`，同时翻转 `h`。

```text
PlaneKey = (Q_d(n), Q(h, eps_linear))
```

### 7.2 Axis

轴线 `(p,d)` 转换为距原点最近点：

\[
q=p-d\cdot dot(d,p)
\]

规范 `d` 符号后：

```text
AxisKey = (Q_d(d), Q3(q, eps_linear))
```

### 7.3 解析 support

```text
CylinderKey = (AxisKey, Q(radius, eps_radius))
ConeKey = (AxisKey, Q3(apex, eps_linear), Q(semi_angle, eps_angular))
SphereKey = (Q3(center, eps_linear), Q(radius, eps_radius))
TorusKey = (AxisKey, Q(major_radius, eps_radius), Q(minor_radius, eps_radius))
LineKey = (AxisKey)
CircleKey = (AxisKey, Q3(center, eps_linear), Q(radius, eps_radius))
```

### 7.4 NURBS exact key

v0.2 的 exact key 不试图消除参数反转或重参数化。使用 STEP/kernel 提供的参数化顺序，并将控制点转换到 world coordinates：

```text
NurbsExactKey = SHA256(
  degree_u,
  degree_v,
  periodic_u,
  periodic_v,
  Q(knots_u, 1e-12),
  Q(knots_v, 1e-12),
  multiplicities_u,
  multiplicities_v,
  Q(weights, 1e-12),
  Q3(world_control_points, eps_linear)
)
```

### 7.5 NURBS 解析约化

```text
RecognizeAnalytic(surface, eps_surface) :=
  OK(CertifiedAnalytic(PlaneParameters, max_error))
  | OK(CertifiedAnalytic(CylinderParameters, max_error))
  | OK(CertifiedAnalytic(ConeParameters, max_error))
  | OK(CertifiedAnalytic(SphereParameters, max_error))
  | OK(CertifiedAnalytic(TorusParameters, max_error))
  | OK(NONE)
  | FAILED
  | TIMEOUT
  | BUDGET_EXHAUSTED
```

只有 backend 能认证整个输入 support surface 在其完整参数域内与返回解析曲面的最大距离不超过 `eps_surface`，并返回 `max_error <= eps_surface` 时才允许 `CertifiedAnalytic`。参数 record 必须包含第 7.1 到 7.3 节 key 所需的全部数值。固定采样只能产生第 12.5 节的近似 evidence，不能把 `NONE` 升级为解析类型。没有认证接口的 backend 必须返回 `OK(NONE)`。

## 8. EvidenceGroup 与有限事件

### 8.1 Group 代表值

每个原始几何 record 为：

```text
EvidenceRecord
  canonical_bucket_key
  exact_parameters
  weight
  source_entity_key
  provenance
```

`provenance` 是有限的 source entity key 集合。按 `canonical_bucket_key` 分组。对同一 source entity 只保留排序键最小的 record；组权重是剩余 record weight 之和；组 provenance 是 record provenance 的并集。代表 record 按以下键取最小：

```text
(-weight, source_entity_key, canonical_json(exact_parameters))
```

候选实际参数只取代表 record 的 `exact_parameters`；bucket 中其他 record 只增加 trigger provenance 和 group weight。

Face record 的 `source_entity_key` 和单元素 provenance 为 Face key，weight 为 Face area；Edge 对应 Edge key 和 Edge length；Vertex 对应 Vertex key 和 `eps_area`；bbox corner 对应 `bbox.corner.<0..7>` 和 `0`；world axis 对应 `world.x/y/z` 和 `0`。事件的 `exact_parameters` 包含实际 `value` 或 direction。事件 group 输出显式字段：

```text
EventGroup
  bucket_key
  representative_value_or_direction
  group_weight
  provenance
```

### 8.2 DirectionEvent

来源：

- Plane Face normal，权重为 Face area。
- Cylinder/Cone/Torus axis，权重为 Face area。
- LINE Edge direction，权重为 Edge length。
- world axes，权重为 `0`，source key 固定为 `world.x/y/z`。

按 `Q_d` 分组。若组总正权重 `W > 0`：

\[
d=normalize(\sum_i w_i d_i)
\]

所有 `d_i` 先规范符号。若 `W = 0`，代表方向取 source key 最小 record 的 exact direction。按 `(-group_weight, Q_d(d))` 排序，保留前 `max_direction_clusters` 个。

### 8.3 PositionEvent

给定单位方向 `d`，产生 record：

- 每个 Vertex：`value = dot(d,p)`。
- 每个 normal 与 `d` 满足 `parallel` 的 Plane：`value = dot(d,origin)`。
- bbox 八个 corner：`value = dot(d,corner)`。

每个来源按第 8.1 节生成完整 EvidenceRecord；`canonical_bucket_key = Q(value,eps_linear)`。按第 8.1 节分组并选择 exact representative value。

### 8.4 AxialEvent

给定轴 `(q,d)`，产生 record：

- 每个 Vertex：`value = dot(d,p-q)`。
- 每个与该轴满足 `coaxial` 的 CIRCLE Edge：`value = dot(d,center-q)`，weight 为 Edge length。
- 每个 normal 与 `d` 满足 `parallel` 的 Plane：`value = dot(d,origin-q)`。
- bbox corner：`value = dot(d,corner-q)`。

每个来源按第 8.1 节生成完整 EvidenceRecord；`canonical_bucket_key = Q(value,eps_linear)`。按第 8.1 节分组。

DirectionEvent、PositionEvent、AxialEvent 生成 record 时，每增加一个 record 都递增当前 analysis/task 的 `event_record_count`。达到 `max_event_records` 时停止生成更多 record，并返回 `BUDGET_EXHAUSTED`；初始 analysis 因此降级 RawBRep，residual task 因此只允许 RawExpansion。

### 8.5 ExtentPair

对排序后的不同 event `i < j` 生成：

```text
ExtentPair
  low = min(event_i.value, event_j.value)
  high = max(event_i.value, event_j.value)
  weight = event_i.group_weight + event_j.group_weight
  provenance = union(event_i.provenance, event_j.provenance)
```

只保留 `high-low > eps_linear`。按：

```text
(-weight, -(high-low), Q(low,eps_linear), Q(high,eps_linear))
```

排序，保留前 `max_extent_pairs_per_axis` 个。

## 9. 有限候选枚举

### 9.0 Primitive 参数 record

所有方向均为 world-coordinate unit vector，所有 frame 均为右手正交 frame，所有 extent 满足 `high-low > eps_linear`：

```text
BoxParameters
  frame_origin
  x_axis
  y_axis
  z_axis = cross(x_axis,y_axis)
  x_low, x_high
  y_low, y_high
  z_low, z_high

CylinderParameters
  axis_point                    # 距 world origin 最近点 q
  axis_direction
  radius > eps_radius
  axial_low, axial_high

ConeParameters
  axis_point                    # 距 world origin 最近点 q
  axis_direction
  apex_axial_coordinate
  semi_angle in (eps_angular, pi/2-eps_angular)
  axial_low, axial_high

SphereParameters
  center
  radius > eps_radius

TorusParameters
  axis_point
  axis_direction
  major_radius
  minor_radius
```

Box 的 world point 为：

\[
frameOrigin+x\cdot xAxis+y\cdot yAxis+z\cdot zAxis
\]

Cylinder/Cone 的 world axial point 为 `axis_point + z*axis_direction`。Cone 在轴坐标 `z` 的半径为：

\[
r(z)=|z-apexAxialCoordinate|\tan(semiAngle)
\]

候选只允许 `r(axial_low)` 或 `r(axial_high)` 至少一个大于 `eps_radius`。这些 record 的字段顺序就是 CandidateKey 的字段顺序。`kernel_construct_primitive` 只接受这些 record。

### 9.1 CandidateValid

```text
CandidateValid(H,T) :=
  construction returned OK
  and kernel_is_valid(H) == OK(true)
  and solid_count(H) == 1
  and volume(H) > eps_volume
  and BBox(H) intersects expand(BBox(T), eps_linear)
  and TriggerEntityCount(H) >= min_trigger_entities
```

其中每个 kernel 测量按第 2.3 节执行；任一不是 `OK` 时结果为 `false`。

`TriggerEntityCount` 是候选使用的 extent、direction、axis、radius 等 event provenance 中不同 Face/Edge/Vertex key 的数量；`world.*` 和 bbox provenance 不计数。

### 9.2 Box

1. 从 DirectionEvent 枚举无序三元组，三元组内部按 `Q_d` 排序。
2. 只保留三对方向均满足 `perpendicular` 的三元组。
3. 令第一个方向为 `x0`，从第二个方向减去在 `x0` 上的投影后规范化为 `y0`，令 `z0 = normalize(cross(x0,y0))`。
4. 若 `angleAbs(z0, third_direction) > eps_angular`，丢弃。
5. frame 固定为右手系 `(x0,y0,z0)`。
6. frame 按三个 direction group weight 总和降序、frame key 升序排序，只保留前 `max_box_frames` 个。
7. 对每个 frame axis 生成 PositionEvent 和 ExtentPair。
8. `frame_origin = (0,0,0)`，三个 extent 均为 world origin 在对应 frame axis 上的投影坐标；枚举三个 ExtentPair 集合的笛卡尔积并构造 oriented Box。
9. 每个 frame 内按 `(-trigger_weight,-volume,CandidateKey)` 排序，保留前 `max_box_candidates_per_frame` 个。

`trigger_weight` 是所有 trigger provenance 对应 record weight 的去重和。

### 9.3 Cylinder

候选轴和半径来源：

- 每个 CylinderKey Face group 的代表参数。
- 每个 CircleKey group；同一 AxisKey 和 radius bucket 下至少存在两个不同 Circle center axial bucket。

对每个 `(axis,radius)` 生成 AxialEvent 和 ExtentPair。Cylinder Face group 只提供 axis/radius，有限 axial extent 一律来自 ExtentPair。每个 pair 构造 `CylinderParameters` 并按 `CandidateValid` 过滤。

### 9.4 Cone

来源一：每个 ConeKey Face group 的代表参数。

来源二：同一 AxisKey 的两个 Circle group `(z1,r1)`、`(z2,r2)`，要求：

\[
|z_1-z_2|>\epsilon_{linear}
\]

且：

\[
|r_1-r_2|>\epsilon_{radius}
\]

计算：

\[
k=(r_2-r_1)/(z_2-z_1)
\]

\[
z_{apex}=z_1-r_1/k
\]

\[
semiAngle=atan(|k|)
\]

Cone Face group 只提供 axis/apex/semi-angle，有限 extent 一律来自 AxialEvent 的 ExtentPair。来源二的 `apex_axial_coordinate = z_apex`。截面半径小于 `eps_radius` 时置为 `0`。构造 `ConeParameters` 后按 `CandidateValid` 过滤。

### 9.5 Sphere

每个 SphereKey Face group 的代表参数生成一个完整 Sphere。v0.2 不从任意圆环拟合 Sphere。

### 9.6 Torus

每个 TorusKey Face group 的代表参数生成一个完整 Torus，且要求：

```text
major_radius > minor_radius > eps_radius
```

v0.2 不生成 horn torus 或 spindle torus，不从曲率样本拟合 Torus。

### 9.7 NURBS 证据记录，不是实体候选

NURBS 不进入本节的实体候选列表，不参与 `PrimitiveCost`、signed residual 或 Beam Search。分析阶段只生成：

```text
NurbsEvidenceRecord
  face_ids sharing the same NurbsExactKey
  NurbsCost
```

v0.2 只按 `NurbsExactKey` 分组，不计算一般 NURBS 的 pairwise 等价关系。

### 9.8 去重和预算

候选只按 `CandidateKey` 去重。相同 key 合并 trigger provenance。v0.2 不调用 Boolean 做候选几何去重。

每种类型按第 13.3 节排序后保留前 `max_candidates_per_type` 个。

每个 task 在尝试构造候选前递增 `candidate_attempt_count`；在候选专属 kernel 调用前递增 `candidate_kernel_call_count`。达到 `max_candidate_attempts_per_task` 或 `max_candidate_kernel_calls_per_task` 后，停止该 task 的候选枚举，并继续保留其无条件 RawExpansion。该规则同时限制 Circle pair、Cone pair 和 Box extent 笛卡尔积的实际尝试数。

## 10. 先验与描述代价

### 10.1 PrimitiveCost

```text
ParameterCodeUnits(Box) = 9
ParameterCodeUnits(Cylinder) = 8
ParameterCodeUnits(Cone) = 9
ParameterCodeUnits(Sphere) = 4
ParameterCodeUnits(Torus) = 9
```

```text
PrimitiveCost(H) =
  configured_type_cost(H.type)
  + scalar_parameter_cost * ParameterCodeUnits(H.type)
```

`ParameterCodeUnits` 是 v0.2 先验表中的版本化整数，不声称等于参数 record 字段数或最小几何自由度。

### 10.2 NurbsCost

```text
NurbsCost(face) =
  type_cost_nurbs_face
  + 0.02 * control_point_count
  + 0.01 * (knot_u_count + knot_v_count)
  + 0.01 * non_unit_weight_count
  + 0.02 * degree_u * degree_v
  + 0.05 * trim_edge_count
```

同一 `NurbsExactKey` group 的代价为一张 support 的 `NurbsCost` 加 `0.1 * (face_count-1)`。

### 10.3 RawBRepCost

```text
RawBRepCost(analysis_or_raw_stats) =
  type_cost_raw_brep
  + sum(NurbsCost(record) for nurbs_face_records)
  + 0.20 * analytic_face_count
  + 0.05 * edge_count
  + 0.01 * vertex_count
```

### 10.4 LeafCost

```text
LeafCost(primitive) = PrimitiveCost(primitive)
LeafCost(RawBRep(...,raw_stats)) = RawBRepCost(raw_stats)
```

这些代价是“常见性”的唯一规范表示。数值越低，先验偏好越高。

## 11. 点、法向和 Edge 投影谓词

### 11.1 ProjectFace

```text
ProjectFace(point, face) := kernel_nearest_point_on_trimmed_face(point, face)
```

成功值包含：

```text
distance
projected_point
all_outward_normals_at_projection
```

投影位于 smooth interior 时 normal 集合大小为 `1`；位于 Edge/Vertex 时包含所有 incident Face outward normals；无法取得 normal 时调用失败。

### 11.2 BoundaryExplainsOnFace

```text
BoundaryExplainsOnFace(atom, face) :=
  ProjectFace(atom.point, face) == OK(p)
  and p.distance <= eps_surface
  and exists n in p.all_outward_normals_at_projection:
        angle(atom.oriented_normal, n) <= eps_normal
```

### 11.3 ProjectEdge

```text
EdgeExplainsOnEdge(atom, edge) :=
  kernel_nearest_point_on_edge(atom.point, edge) == OK(p)
  and p.distance <= eps_surface
  and angleAbs(atom.unit_tangent, p.unit_tangent) <= eps_normal
```

## 12. 支撑面匹配

### 12.1 无向 support 匹配

`SupportExplains` 故意忽略材料方向，因为同一个 Cylinder support 可以是凸台外壁，也可以在 `Subtract` 后成为孔壁。方向只在候选实际边界和最终 leaf ownership 中检查。

Plane：

\[
|dot(n,a.point)-h|\leq\epsilon_{surface}
\]

且 `angleAbs(n,a.oriented_normal) <= eps_normal`。

Cylinder：令：

\[
v=a.point-q-d\cdot dot(d,a.point-q)
\]

要求：

\[
|\|v\|-r|\leq\epsilon_{surface}
\]

且 `norm(v) > eps_linear`，并满足 `angleAbs(v/norm(v),a.oriented_normal) <= eps_normal`。

Cone、Sphere、Torus：调用无限支撑面的 kernel projection，要求 distance 不超过 `eps_surface`，且 projected normal 与 atom normal 的 `angleAbs` 不超过 `eps_normal`。

```text
SupportExplains(H,a) :=
  exists support s of primitive H: support_match(s,a)
```

### 12.2 实际边界匹配

```text
BoundaryExplains(H,a) :=
  exists boundary Face f of H: BoundaryExplainsOnFace(a,f)
```

### 12.3 Edge 匹配

`NaturalEdges(H)` 是 primitive 构造结果中排除 seam 和 degenerated Edge 后的有限 Edge 集合。

```text
EdgeExplains(H,e) :=
  exists g in NaturalEdges(H): EdgeExplainsOnEdge(e,g)
```

### 12.4 FaceMap

对目标 Face `f` 和候选边界 Face `b`：

\[
M(f,b)=\sum_{a\in SA(T),a.sourceFace=f}
a.area\cdot I[BoundaryExplainsOnFace(a,b)]
\]

`FaceMap(f,H)` 取 `M(f,b)` 最大的候选 Face；最大值小于 `eps_area` 时为 `NONE`。同分时按：

```text
BoundaryFaceKey = (support_key,
                   Q3(face_centroid, eps_linear),
                   Q(face_area, eps_area),
                   construction_local_face_id)
```

取 key 最小者。`construction_local_face_id` 由 primitive builder 按固定面角色分配，不使用 kernel 枚举序号。

## 13. 候选解释与局部分数

### 13.1 Bitset

```text
CandidateExplanation
  support_surface_atom_bits[a] = SupportExplains(H,a)
  boundary_surface_atom_bits[a] = BoundaryExplains(H,a)
  edge_atom_bits[e] = EdgeExplains(H,e)
  adjacency_atom_bits[r] = AdjacencyExplains(H,r)
```

`AdjacencyExplains(H,r)` 当且仅当：

- `FaceMap(r.face_a,H)` 和 `FaceMap(r.face_b,H)` 均不是 `NONE`。
- 两个映射结果不同。
- 两个候选 Face 在候选 B-Rep 中共享至少一条非 degenerated Edge。

### 13.2 覆盖率

\[
C_S=\frac{\sum_a a.area\cdot I[supportBits[a]]}{W_S(T)}
\]

\[
C_B=\frac{\sum_a a.area\cdot I[boundaryBits[a]]}{W_S(T)}
\]

若 `W_E(T)>0`：

\[
C_E=\frac{\sum_e e.lengthWeight\cdot I[edgeBits[e]]}{W_E(T)}
\]

否则 `C_E=0` 且局部分数中的 Edge reward 置 `0`。

若 `W_A(T)>0`：

\[
C_A=\frac{\sum_r r.weight\cdot I[adjacencyBits[r]]}{W_A(T)}
\]

否则 `C_A=0` 且局部分数中的 adjacency reward 置 `0`。

### 13.3 LocalScore

\[
LocalScore(H,T)=
rewardSupport\cdot C_S+
rewardBoundary\cdot C_B+
rewardEdge'\cdot C_E+
rewardAdjacency'\cdot C_A-
penaltyLeafCost\cdot PrimitiveCost(H)
\]

候选只在 `C_S >= min_support_coverage` 时保留。排序键：

```text
(-LocalScore, -C_S, -C_B, PrimitiveCost, CandidateKey)
```

每种类型保留前 `max_candidates_per_type` 个，合并后保留前 `boolean_prefilter_top_m` 个。

## 14. Signed residual

对当前任务 solid `S` 和候选 `H`，连续执行两个 kernel Boolean：

```text
RplusResult: BooleanShape = regularized_cut(S,H)
RminusResult: BooleanShape = regularized_cut(H,S)
```

调用前必须为两个 Boolean 分别成功 reserve budget。任一结果失败时淘汰候选。

对 `EMPTY` 使用空 component list；对 `NONEMPTY(shape)` 调用 `components(shape)`。调用失败时淘汰候选。每个非空 component 必须满足 `ValidSolid`。体积小于等于 `eps_volume` 的 component 不进入列表，删除体积累加为 `discardedVolume`。若：

\[
discardedVolume>\epsilon_{volume}
\]

则淘汰候选。

剩余 component 分别记为：

```text
P = sorted components of Rplus
M = sorted components of Rminus
```

每个剩余 component 立即执行第 15.1 节 `AnalyzeResidual`。任一分析失败时淘汰候选。排序键为 analysis 中的 `snapshot.sha256`。

## 15. 程序模板状态转移

### 15.1 ResidualAnalysis

```text
ResidualAnalysis
  shape                         # 只在当前进程计算期间使用
  snapshot: BRepSnapshot        # 可序列化、可重放
  surface_atoms
  edge_atoms
  adjacency_atoms
  support_groups
  direction_events
  face_count
  edge_count
  vertex_count
  analytic_face_count
  nurbs_face_count
  raw_stats
  volume
  surface_area
```

```text
AnalyzeResidual(S,config,context) :=
  ValidSolid(S)
  + SnapshotOf(S)
  + 第 6 至 8 节全部分析
```

结果是 `KernelResult[ResidualAnalysis]`。所有测量只在这里执行并缓存；候选排序、cost、proxy、task 选择和 StateKey 不允许再次隐式调用 kernel。初始 target 也产生相同结构的 `ResidualAnalysis`。

### 15.2 FoldUnion

统一排序函数：

```text
UnionOrderKey(primitive leaf) = (0, CandidateKey)
UnionOrderKey(RawBRep leaf) = (1, RawBRepKey)
UnionOrderKey(Slot) = (2, slot_id)
UnionOrderKey(composite Program) = (3, ProgramKey)
```

输入按 `UnionOrderKey` 排序。

```text
FoldUnion([]) = EMPTY
FoldUnion([x]) = x
FoldUnion([x1,...,xn]) = Union(...Union(Union(x1,x2),x3)...,xn)
```

`EMPTY` 只用于构造规则，不是 `Program` 节点。

### 15.3 CandidateExpansion

设 `P` 有 `p` 个 components，`M` 有 `m` 个 components。为每个 component 创建唯一 Slot，ID 为：

```text
SHA256(parent_slot_id, sign, component_analysis.snapshot.sha256,
       same_fingerprint_ordinal)
```

其中 `sign` 只用于 ID，取 `PLUS` 或 `MINUS`；ordinal 是排序后同 fingerprint 的从零计数。

```text
base = FoldUnion([H] + plus_slots)
replacement = base                         if m == 0
replacement = Subtract(base,
                       FoldUnion(minus_slots)) if m > 0
```

将当前 `Slot` 替换为 `replacement`。每个新 Slot 对应：

```text
ResidualTask
  slot_id
  analysis: ResidualAnalysis
  depth = parent.depth + 1
```

若新 task 数使状态的 `pending_task_count > max_pending_tasks_per_state`，丢弃该 CandidateExpansion，只保留父 task 的 RawExpansion。

新插入 Boolean 节点数：

```text
union_count = p + max(m-1, 0)
subtract_count = 1 if m > 0 else 0
```

立即增加的 committed cost：

```text
PrimitiveCost(H)
+ union_count * operation_cost_union
+ subtract_count * operation_cost_subtract
```

### 15.4 RawExpansion

`task.analysis` 已含 `SnapshotOf(task.analysis.shape)` 的结果。将当前 `Slot` 替换为 `RawBRep(task.analysis.snapshot, len(snapshot.bytes), task.analysis.raw_stats)`，删除该 task，立即增加：

```text
RawBRepCost(task.analysis)
```

### 15.5 成本不变量

对任一搜索状态：

```text
committed_cost =
  sum(cost of every committed leaf)
  + sum(cost of every committed Boolean node)
```

当没有 Slot 时：

```text
committed_cost == ProgramCost(completed_program)
```

## 16. Residual 代理代价和展开门槛

### 16.1 ResidualProxyCost

```text
ResidualProxyCost(analysis) =
  1.00 * solid_count
  + 0.20 * analytic_face_count
  + 0.50 * nurbs_face_count
  + 0.02 * edge_count
  + 0.01 * vertex_count
```

component list 的 proxy 是每个 component proxy 之和。

### 16.2 ExpansionEstimate

\[
ExpansionEstimate=
PrimitiveCost(H)+
unionCount\cdot operationCostUnion+
subtractCount\cdot operationCostSubtract+
Proxy(P)+Proxy(M)+
unmatchedSupportPenalty\cdot(1-C_S)+
unmatchedBoundaryPenalty\cdot(1-C_B)+
unmatchedEdgePenalty'\cdot(1-C_E)
\]

若 `W_E=0`，最后一项为 `0`。

只有满足：

\[
ExpansionEstimate\leq RawBRepCost(currentTask.analysis)+expansionMargin
\]

的候选才执行第 15.3 节状态转移。

## 17. 有界 Beam Search

### 17.1 SearchState

```text
SearchState
  template
  tasks_by_slot_id
  committed_cost
  estimated_remaining_cost
  state_key
```

```text
estimated_remaining_cost =
  sum(MinLeafCost for each pending task)
```

```text
MinLeafCost = min(
  type_cost_box + 9*scalar_parameter_cost,
  type_cost_cylinder + 8*scalar_parameter_cost,
  type_cost_cone + 9*scalar_parameter_cost,
  type_cost_sphere + 4*scalar_parameter_cost,
  type_cost_torus + 9*scalar_parameter_cost,
  type_cost_raw_brep
)
```

该值只用于排序；不声称是包含 Boolean 操作的严格数学下界。

### 17.2 StateKey

```text
state_key = SHA256(
  canonical serialization of template,
  sorted tuples(slot_id, task.depth, task.analysis.snapshot.sha256)
)
```

同一 `state_key` 只保留 `committed_cost` 最小者；同分保留 template serialization 字典序最小者。

### 17.3 任务选择

从 pending task 中按以下键取最小：

```text
(-RawBRepCost(task.analysis),
 -task.analysis.volume,
 task.analysis.snapshot.sha256,
 slot_id)
```

### 17.4 单状态展开

```text
if task.depth >= max_task_depth:
    children = [RawExpansion(state, task)]
else:
    children = every accepted CandidateExpansion
               plus one unconditional RawExpansion
```

展开一个状态前检查 `expanded_states + 1 <= max_expanded_states`。每个 kernel 调用由 `KernelContext.try_reserve` 单独检查，因此 Boolean 和总调用硬上限不会超出。

### 17.5 Frontier

算法每次从 frontier 取排序键最小的一个状态展开，再将 children 放回 frontier。排序键：

```text
(
  committed_cost + estimated_remaining_cost,
  sum(RawBRepCost(task.analysis) for pending tasks),
  pending_task_count,
  state_key
)
```

插入 children、去重、排序后只保留前 `beam_width` 个状态。

### 17.6 搜索终止

搜索上下文保存唯一 `termination_reason`：

```text
FRONTIER_EMPTY
STATE_LIMIT
BOOLEAN_LIMIT
KERNEL_CALL_LIMIT
SEARCH_TIMEOUT
ENOUGH_COMPLETED_PROGRAMS
```

循环开始及每次 kernel reserve 前更新该值。达到任何预算后不再生成候选。若一个状态已从 frontier 弹出但尚未完成展开，将该未修改状态加入 `fallbackStates`；已经完整生成的 children 保留在 frontier。把 `frontier union fallbackStates` 中每个状态的全部 pending Slot 按 slot ID 升序执行 RawExpansion，得到完整程序。若 frontier 正常变空且 termination reason 尚未设置，则设置为 `FRONTIER_EMPTY`。

完成程序按 `(ProgramCost,ProgramKey)` 去重，只保留前 `max_completed_programs_to_validate` 个。

### 17.7 显式调用上界

若实际展开状态数为 `S <= max_expanded_states`，每状态经过预筛选的候选数为 `P <= boolean_prefilter_top_m`，signed residual 最多调用：

\[
2SP
\]

次 Boolean。实际数量同时受 `max_search_boolean_calls` 限制。候选构造、投影和测量计入 `max_search_total_kernel_calls`。最终程序重放和验证使用独立 validation context，不消费搜索预算。

## 18. 完整程序代价

```text
ProgramCost(primitive) = PrimitiveCost(primitive)
ProgramCost(RawBRep(...,raw_stats)) = RawBRepCost(raw_stats)
ProgramCost(Union(A,B)) = ProgramCost(A)+ProgramCost(B)+operation_cost_union
ProgramCost(Subtract(A,B)) = ProgramCost(A)+ProgramCost(B)+operation_cost_subtract
```

## 19. 完整程序验证

### 19.1 重放

整个 validation 阶段创建一个共享 `validationContext`；所有完成程序和最终 RawBRep fallback 共用它的 deadline 和调用计数。依次执行按 `(ProgramCost,ProgramKey)` 排序的程序；context 到期或预算耗尽后不再验证后续程序。

对一个程序只执行一次 `Render(P)` 并保存 `ReplayResult = R`。失败时：

```text
ValidProgram(P,T) = false
```

### 19.2 Symmetric difference

成功重放结果为 `R`：

```text
D1: BooleanShape = regularized_cut(T,R)
D2: BooleanShape = regularized_cut(R,T)
symdiff_volume = volume(D1)+volume(D2)  # volume(EMPTY)=0
```

任一调用失败则验证失败。

```text
VolumeEquivalent := symdiff_volume <= eps_volume
```

### 19.3 双向边界距离和法向

用第 6.1 节相同配置生成 `SA(R)`，并对 mesh area 执行相同覆盖检查。对 `SA(T)` 中每个 atom 投影到 `boundary(R)`，对 `SA(R)` 中每个 atom 投影到 `boundary(T)`。

每次 projection 必须成功。距离集合 `Dists` 和最小有向法向误差集合 `Angles`：

```text
distance = nearest boundary distance
angle = min(angle(atom.oriented_normal,n)
            for n in all outward normals at projection)
```

两个 atom 集合都非空，因此：

\[
maxBoundaryDistance=\max(Dists)
\]

\[
rmsBoundaryDistance=\sqrt{
\frac{\sum_i area_i\cdot distance_i^2}{\sum_i area_i}}
\]

\[
maxNormalError=\max(Angles)
\]

```text
BoundaryEquivalent := maxBoundaryDistance <= eps_surface
NormalEquivalent := maxNormalError <= eps_normal
```

`rmsBoundaryDistance` 只作为输出指标，不参与 v0.2 acceptance。

### 19.4 可计算 topology signature

v0.2 不用原始 `V-E+F` 计算 Euler characteristic。定义：

```text
TopologySignature(S) = (
  solid_count(S),
  closed_shell_count(S),
  open_shell_count(S),
  non_manifold_edge_count(S)
)
```

任一计数调用失败则验证失败。

```text
TopologySignatureMatches := TopologySignature(T) == TopologySignature(R)
```

### 19.5 ValidProgram

```text
ValidProgram(P,T) :=
  ReplayResult R exists
  and kernel_is_valid(R) == OK(true)
  and VolumeEquivalent
  and BoundaryEquivalent
  and NormalEquivalent
  and TopologySignatureMatches
```

`ValidProgram` 是 acceptance profile 名称，含义仅为本节 finite tests 在给定配置下通过，不表示符号等价或完整 Hausdorff/topology 证明。

## 20. SurfaceAtom 归属与有效解释

### 20.1 Leaf polarity

从程序根向叶递归：

```text
polarity(root) = +1
polarity(Union.left/right) = polarity(parent)
polarity(Subtract.left) = polarity(parent)
polarity(Subtract.right) = -polarity(parent)
```

### 20.2 LeafSupportEvidence

对 primitive 或 RawBRep 叶节点 `L`，将其支撑面投影法向乘 `polarity(L)`：

```text
LeafSupportEvidence(L,a) :=
  exists support face f of L:
    projection of a.point to support(f) succeeds
    and distance <= eps_surface
    and exists normal n at projection:
        angle(a.oriented_normal, polarity(L)*n) <= eps_normal
```

支撑面使用未裁剪 support，因此 Boolean 改变 trim 后仍可产生解释证据。这个 predicate 不声称该叶节点是原始历史来源，也不证明该 support 在 Boolean 中对最终边界有唯一贡献。

### 20.3 唯一 owner

对每个目标 SurfaceAtom 枚举有限叶节点集合。满足 `LeafSupportEvidence` 的叶节点按：

```text
(
  0 if primitive else 1,
  LeafCost,
  -leaf_depth,
  leaf_program_key
)
```

取最小者。输出字段名为 `support_evidence_owner`；没有匹配者时为 `NONE`。

### 20.4 ValidExplanation

```text
ValidExplanation(P,T) :=
  ValidProgram(P,T)
  and every a in SA(T) has support_evidence_owner != NONE
```

本文中的“100% 解释”严格指：第 6.1 节有限 SurfaceAtom 集合全部有 support evidence，并且第 19 节 acceptance profile 通过；不表示连续曲面上的数学全称命题。第 6.1 节同时限制离散 surface area 与 kernel surface area 的差值。

## 21. Edge 和 adjacency 节点归属

Edge 和 adjacency 可能由 Boolean 生成，因此不强制归属到叶节点。

### 21.1 节点重放缓存

完整程序验证时缓存每个语法树节点的 `Render(node)`。节点深度从根为 `0` 向下递增。

### 21.2 EdgeOwner

```text
NodeExplainsEdge(node,e) :=
  exists non-seam, non-degenerated Edge g in Render(node):
    EdgeExplainsOnEdge(e,g)
```

候选 node 按 `(-node_depth,node_program_key)` 取最小。最终 root 若仍不能解释，则 owner 为 `UNATTRIBUTED`。

### 21.3 AdjacencyOwner

对每个 node 的 rendered shape，用第 12.4 节方式把目标两个 Face 映射到 node result Face：

```text
NodeExplainsAdjacency(node,r) :=
  both FaceMap values exist and differ
  and the mapped result Faces share a non-degenerated Edge
```

按 `(-node_depth,node_program_key)` 选择 owner。失败时为 `UNATTRIBUTED`。

Edge 或 adjacency 的 `UNATTRIBUTED` 数量进入输出，但 v0.2 不把它们加入 `ValidExplanation`；几何正确性由第 19 节约束。

## 22. 最终选择

先对最多 `max_completed_programs_to_validate` 个完成程序执行第 19、20 节。令：

```text
VP = finite set of programs with ValidExplanation == true
```

若 `VP` 非空，排序键为：

```text
(
  ProgramCost,
  RawBRep_leaf_count,
  total_NURBS_face_count_inside_RawBRep,
  Boolean_node_count,
  ProgramKey
)
```

返回最小者，status 为 `VALID_EXPLANATION`。

若 `VP` 为空，验证 `RawBRep(T)`。若其 `ValidExplanation` 为 true，返回它，status 为 `RAW_BREP_ONLY`；否则返回 `FINAL_VALIDATION_FAILED`。

## 23. 主算法伪代码

```python
def reverse_step(target, overrides=None):
    bbox = kernel_bbox(target)
    if not bbox.ok:
        return snapshot_or_failure(target, "ANALYSIS_FAILED")
    if not bbox.finite or bbox.diagonal <= 0:
        return snapshot_or_failure(target, "INVALID_INPUT")

    config = resolve_config(target, bbox, overrides)
    if not config_valid(config):
        return failure("INVALID_CONFIG")

    analysis_ctx = KernelContext.for_analysis(config)
    analysis = analyze_residual(target, config, analysis_ctx)
    if not analysis.ok:
        return snapshot_or_failure(target, analysis.status)

    search_ctx = KernelContext.for_search(config)
    initial_slot = Slot(id=sha256("root"))
    initial_task = ResidualTask(
        slot_id=initial_slot.id,
        analysis=analysis.value,
        depth=0,
    )
    frontier = [SearchState(
        template=initial_slot,
        tasks={initial_slot.id: initial_task},
        committed_cost=0,
    )]
    completed = []
    fallback_states = []
    expanded_states = 0

    while frontier and not search_ctx.stopped:
        state = pop_min(frontier, key=frontier_sort_key)

        if not state.tasks:
            completed.append(state.template)
            if len(completed) >= config.search.max_completed_programs_to_validate:
                search_ctx.stop("ENOUGH_COMPLETED_PROGRAMS")
            continue

        if expanded_states >= config.search.max_expanded_states:
            search_ctx.stop("STATE_LIMIT")
            fallback_states.append(state)
            break

        task = select_task(state.tasks)
        expanded_states += 1
        children = []

        if task.depth < config.search.max_task_depth:
            candidates = enumerate_candidates(task.analysis, config, search_ctx)
            explanations = compute_explanations(candidates, task.analysis, config, search_ctx)
            ranked = rank_and_limit(explanations, config)

            for candidate, explanation in ranked:
                residuals = signed_residuals(task.analysis, candidate, config, search_ctx)
                if not residuals.ok:
                    if search_ctx.stopped:
                        break
                    continue
                if expansion_estimate(candidate, explanation, residuals, config) \
                        > raw_brep_cost(task.analysis, config) + config.score.expansion_margin:
                    continue
                children.append(candidate_expansion(
                    state, task, candidate, residuals, config
                ))

        if search_ctx.stopped:
            fallback_states.append(state)
            break

        children.append(raw_expansion(state, task, config))
        frontier = deduplicate(frontier + children)
        frontier.sort(key=frontier_sort_key)
        frontier = frontier[:config.search.beam_width]

    if not search_ctx.termination_reason:
        search_ctx.stop("FRONTIER_EMPTY")

    completed.extend(materialize_all_slots_as_raw(
        deduplicate(frontier + fallback_states), config
    ))
    completed = deduplicate_and_sort_programs(completed, config)
    completed = completed[:config.search.max_completed_programs_to_validate]

    valid = []
    validation_ctx = KernelContext.for_validation(config)
    for program in completed:
        if validation_ctx.stopped:
            break
        metrics = validate_program_and_assign_atoms(
            program, target, analysis, config, validation_ctx
        )
        if metrics.valid_explanation:
            valid.append((final_program_sort_key(program, metrics), program, metrics))

    if valid:
        valid.sort(key=lambda x: x[0])
        return result(valid[0], search_ctx.termination_reason)

    return validate_and_return_raw_brep(
        target, analysis, config, validation_ctx
    )
```

`snapshot_or_failure` 创建一个独立、只允许一次 `SnapshotOf` 的 emergency context；成功时返回 `RawBRep`，失败时 `program = null`。这条 emergency 调用及其 deadline 单独写入结果，不能复用已经耗尽的阶段 context。

## 24. 状态与诊断枚举

```text
INVALID_CONFIG
INVALID_INPUT
ANALYSIS_FAILED
INVALID_SOLID
MESH_COVERAGE_FAILED
CANDIDATE_CONSTRUCTION_FAILED
BOOLEAN_FAILED
BOOLEAN_TIMEOUT
NUMERICALLY_UNSTABLE
STATE_LIMIT
BOOLEAN_LIMIT
KERNEL_CALL_LIMIT
SEARCH_TIMEOUT
FRONTIER_EMPTY
ENOUGH_COMPLETED_PROGRAMS
RAW_BREP_ONLY
FINAL_VALIDATION_FAILED
VALID_EXPLANATION
```

自由文本 diagnostic 不参与控制流。

## 25. 输出结构

```text
ExplanationResult
  status
  search_termination_reason
  input_fingerprint
  config
  program
  program_key
  program_cost
  candidate_records
  surface_atom_owners
  edge_atom_owners
  adjacency_atom_owners
  validation_metrics
  kernel_call_counts
  diagnostics
```

`validation_metrics` 至少包含：

```text
symdiff_volume
max_boundary_distance
rms_boundary_distance
max_normal_error
topology_signature_input
topology_signature_result
surface_atom_count
owned_surface_atom_count
unattributed_edge_atom_count
unattributed_adjacency_atom_count
valid_program
valid_explanation
```

## 26. MVP 模块

实现模块和唯一输入输出如下：

| 模块 | 输入 | 输出 |
| --- | --- | --- |
| `BRepAnalyzer` | B-Rep、Config、KernelContext | descriptors、SA、EA、AA、support groups |
| `CandidateEnumerator` | analysis、Config | finite primitive candidates |
| `CandidateScorer` | candidate、current residual analysis | bitsets、coverage、LocalScore |
| `ResidualEngine` | residual、candidate、KernelContext | sorted Rplus/Rminus components |
| `ProgramSearch` | root residual、Config | finite completed programs |
| `ProgramValidator` | program、target atoms、Config | validation metrics、atom owners |

## 27. 测试要求

### 27.1 确定性

对相同 STEP bytes、backend version 和 config 重复运行两次，以下 bytes 必须相同：

- atom records canonical JSON。
- event records canonical JSON。
- CandidateKey 序列。
- ProgramKey。
- 非 timeout 情况下的最终 ExplanationResult canonical JSON；运行时间字段除外。

### 27.2 单 primitive

对 Box、Cylinder、Cone、Sphere 和 ring Torus fixture：

```text
ValidExplanation(expected_primitive_program, fixture) == true
ProgramCost(expected_primitive_program) < RawBRepCost(fixture)
```

### 27.3 Boolean

对 Box 减 Cylinder、Box 加 Cylinder、同轴 Cylinder 相减 fixture：

- 返回 `VALID_EXPLANATION`。
- `symdiff_volume <= eps_volume`。
- `max_boundary_distance <= eps_surface`。
- `max_normal_error <= eps_normal`。
- `owned_surface_atom_count == surface_atom_count`。

### 27.4 Face split

对几何相同但 Face split 不同的两个 STEP：

- 最优程序的 `ProgramKey` 相同。
- 最优程序的 `ProgramCost` 相同。
- 两者各自 `ValidExplanation == true`。

不比较 atom 数量，因为三角化可能跟随输入 Face split 变化。

### 27.5 NURBS

- 可约化 NURBS Cylinder：`RecognizeAnalytic` 返回完整 Cylinder 参数且通过采样验证。
- exact-key 相同的 NURBS Face：产生同一个 exact group。
- pairwise sampled match 不取传递闭包。
- 全自由曲面 closed solid：在预算内返回 `RawBRep` 或包含 RawBRep residual 的有效程序。

### 27.6 硬预算

每次测试断言：

```text
search_boolean_calls <= max_search_boolean_calls
search_total_kernel_calls <= max_search_total_kernel_calls
expanded_states <= max_expanded_states
each_task_depth <= max_task_depth
validation_boolean_calls <= max_validation_boolean_calls
validation_total_kernel_calls <= max_validation_total_kernel_calls
```

## 28. 算法总流程

```text
STEP B-Rep
  |
  v
解析并验证 Config
  |
  v
ValidSolid + 固定参数三角化/边离散
  |
  v
构造有限 SA / EA / AA 和 support groups
  |
  v
从有限 Direction/Position/Axial/Extent 事件枚举 primitive candidates
  |
  v
计算 explanation bitsets、coverage 和 LocalScore
  |
  v
Top-M 候选计算 R+ 与 R-
  |
  v
ExpansionEstimate 门槛
  |
  v
固定模板替换规则 + 有界 Beam Search
  |                              \
  |                               +--> 每个 Slot 无条件可替换为 RawBRep
  v
有限个完成 Program
  |
  v
Render + symmetric difference + 双向边界/法向 + topology signature
  |
  v
SurfaceAtom polarity owner
  |
  v
在 ValidExplanation 集合中最小化 ProgramCost
```

## 29. 结论

v0.2 将原始设想翻译为以下有限优化问题。给定输入 `T`、固定配置 `C` 和搜索实际枚举到的有限程序集合 `Programs(T,C)`：

\[
P^*=argmin_{P\in Programs(T,C)} ProgramCost(P)
\]

约束：

\[
ValidExplanation(P,T)=true
\]

基础单元常见性由 `PrimitiveCost`、`NurbsCost` 和 `RawBRepCost` 表示；解释多少边和面由 `CandidateExplanation` bitset 及加权覆盖率表示；“基础几何元素 + 剩余部分”由两个 regularized cut 和第 15.3 节固定程序模板表示；递归由有限事件、候选上限、Beam Width、任务深度、状态数、kernel 调用数、Boolean 调用数和 deadline 限制。

因此该规范不需要枚举任意空间中的全部几何体，也不需要对一般 NURBS 求不可控的全局拟合；在所有搜索路径失败或预算耗尽时，`RawBRep` 分支给出有限、可重放的兜底程序。
