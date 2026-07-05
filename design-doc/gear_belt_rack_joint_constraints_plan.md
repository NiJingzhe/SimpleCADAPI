# Gear, Belt, And Rack-Pinion Constraint API Plan

本文计划在 SimpleCADAPI 中新增三类 FreeCAD Assembly 对应的运动耦合约束：gear joint、belt joint、rack-pinion joint。目标不是照搬 FreeCAD GUI，而是先理解 FreeCAD 的 solver 语义，再映射成与 SimpleCAD SDK 当前 connector-frame assembly API 一致的 public API、model JSON、replay、inspection、FreeCAD translation。

## Scope

本轮实现范围：

| Constraint | SimpleCAD kind | FreeCAD joint type | 语义 |
| --- | --- | --- | --- |
| Gear joint | `gear` | `Gears` | 两个 revolute DOF 按半径比反向转动。 |
| Belt joint | `belt` | `Belt` | 两个 revolute DOF 按半径比同向转动。 |
| Rack-pinion joint | `rack_pinion` | `RackPinion` | 一个 prismatic DOF 与一个 revolute DOF 按 pitch radius 耦合。 |

非目标：

| Out of scope | 原因 |
| --- | --- |
| 任意齿面接触求解 | 当前 assembly layer 是 connector-frame constraint，不是 contact solver。 |
| 自动识别齿轮几何齿数/module | std gear 可以提供辅助值，但 assembly constraint 不应依赖具体几何类型。 |
| 动力学仿真、速度/加速度输出 | 当前 SDK solver 是 placement/replay/translation-oriented。 |
| GUI task panel | SimpleCAD 是 Python SDK；FreeCAD GUI 只作为语义参考。 |

## FreeCAD Algorithm Reference

FreeCAD 源码版本：`1ad23bce66833eb6f995c5c954a8f443ffa7b4fd`。

关键事实：

| FreeCAD source | 行为 |
| --- | --- |
| [`AssemblyObject.cpp#L968-L977`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L968-L977) | `RackPinion`、`Screw`、`Gears`、`Belt` 不算连接图中的 connecting joint；它们不会单独把部件连到 ground。 |
| [`AssemblyObject.cpp#L1209-L1213`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1209-L1213) | `RackPinion` 创建 `ASMTRackPinionJoint`，`Distance` 写入 `pitchRadius`。 |
| [`AssemblyObject.cpp#L1230-L1235`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1230-L1235) | `Gears` 创建 `ASMTGearJoint`，`Distance` 为 `radiusI`，`Distance2` 为 `radiusJ`。 |
| [`AssemblyObject.cpp#L1237-L1241`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1237-L1241) | `Belt` 也创建 `ASMTGearJoint`，但 `radiusJ = -Distance2`，用负半径表达同向转动。 |
| [`AssemblyObject.cpp#L1421-L1428`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1421-L1428) | `RackPinion` 不走普通 `handleOneSideOfJoint`，而是走专门的 `getRackPinionMarkers(...)`。 |
| [`AssemblyObject.cpp#L1698-L1717`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1698-L1717) | rack-pinion 必须把 rack 作为 marker I，pinion 作为 marker J；如果检测到滑动端不是 Reference1，会 swap JCS。 |
| [`AssemblyObject.cpp#L1731-L1788`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1731-L1788) | pinion marker 普通处理；rack marker 要重建 orientation：Z 平行 pinion Z，X 平行 slider axis。 |
| [`AssemblyObject.cpp#L1791-L1833`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/App/AssemblyObject.cpp#L1791-L1833) | FreeCAD 通过扫描已有 `Slider` joint 且比较 JCS pitch/roll 来判断 rack 哪一侧是 sliding side。 |
| [`JointObject.py#L85-L101`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/JointObject.py#L85-L101) | `RackPinion`、`Gears`、`Belt` 使用 `Distance`；`Gears`、`Belt` 额外使用 `Distance2`；gear/belt 半径不允许负数。 |
| [`JointObject.py#L1891-L1908`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/JointObject.py#L1891-L1908) | GUI label：gear/belt 的 `Distance` 显示为 `Radius 1`，rack-pinion 显示为 `Pitch radius`。 |
| [`CommandCreateJoint.py#L285-L308`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/CommandCreateJoint.py#L285-L308) | rack-pinion GUI 语义：连接一个 slider part 和一个 revolute part；选择与 slider/revolute joints 相同的 coordinate systems。 |
| [`CommandCreateJoint.py#L335-L380`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/CommandCreateJoint.py#L335-L380) | gear GUI 语义为两个 rotating gears 反向，belt GUI 语义为两个 rotating objects 同向。 |
| [`InitGui.py#L93-L110`](https://github.com/FreeCAD/FreeCAD/blob/1ad23bce66833eb6f995c5c954a8f443ffa7b4fd/src/Mod/Assembly/InitGui.py#L93-L110) | FreeCAD 在 Assembly Joints toolbar 中暴露 `RackPinion` 和 gear/belt command group。 |

从 FreeCAD 得出的实现规则：

| Rule | SimpleCAD interpretation |
| --- | --- |
| Gear/Belt/RackPinion 是运动耦合，不是连接约束。 | SimpleCAD 中这些 constraints 不应让一个 disconnected component 仅靠耦合变成 solved/reachable。它们需要已有 fixed/revolute/prismatic 等 support constraints 建立拓扑连接。 |
| Gear 与 Belt 都映射到同一个 solver primitive，差别只有半径符号。 | SimpleCAD API 应保留两个语义函数，但内部可用同一 coupling equation，`belt` 改变 sign convention。 |
| Gear/Belt 半径必须为正。 | `pitch_radius_a` / `pitch_radius_b` 或 `pulley_radius_*` 必须 finite 且 `> 0.0`。 |
| Rack-pinion 的 rack marker 不是用户直接选出的 slider marker，而是转换后的 marker。 | SimpleCAD API 应让 rack connector 沿 SDK 的 prismatic +Z 表达滑动方向，FreeCAD translator 负责按 FreeCAD 要求构造 Reference1/Reference2，并依赖 FreeCAD `getRackPinionMarkers` 完成 marker orientation。 |
| FreeCAD GUI 通过扫描已有 Slider 判断 rack side。 | SimpleCAD SDK 不应隐藏这种不确定性；API 固定 rack 参数在前、pinion 参数在后，validation 检查 support constraints。 |

## SDK Semantics

### Constraint Kind Model

当前 `Constraint.constraint_kind` 只允许 `fixed`、`revolute`、`prismatic`。本轮扩展为：

```text
fixed | revolute | prismatic | gear | belt | rack_pinion
```

三类新 constraint 是 kinematic coupling constraint：

| Kind | Connects component graph | Requires existing support DOF |
| --- | --- | --- |
| `gear` | no | two revolute axes |
| `belt` | no | two revolute axes |
| `rack_pinion` | no | one prismatic axis and one revolute axis |

Reachability and strict solve behavior should match FreeCAD's `isJointTypeConnecting(...)` rule: these constraints are ignored when determining whether components are connected to ground. They only validate and couple scalars after the support constraints exist.

### Natural Coordinates

Existing SimpleCAD constraints already define natural scalars:

| Existing support kind | Natural scalar | Unit |
| --- | --- | --- |
| `revolute` | `angle_degrees` around connector A +Z | degrees |
| `prismatic` | `z_distance` along connector A +Z | length |

New coupling constraints reference those natural scalars conceptually:

| Coupling kind | Equation with zero phase |
| --- | --- |
| `gear` | `r_a * theta_a_rad + r_b * theta_b_rad = 0` |
| `belt` | `r_a * theta_a_rad - r_b * theta_b_rad = 0` |
| `rack_pinion` | `rack_distance + pitch_radius * pinion_theta_rad = 0` |

Notes:

| Topic | Decision |
| --- | --- |
| Angle unit inside equations | Convert public degrees to radians before multiplying by radius, because arc length is `radius * radians`. |
| Sign control | Gear/belt type controls the default sign. Users can flip connector axes to reverse physical direction. |
| Phase | Store an explicit scalar phase offset, default derived from current placements at constraint creation time. This keeps replay deterministic and avoids hidden solver state. |
| Residual unit | Coupling scalar residual is a length-like arc residual for all three kinds. For report compatibility, map it to `translation_error`; optionally add richer scalar fields in a later API revision. |

## Public API Plan

All examples and docs should call these with keyword arguments, matching the skill requirement. Function signatures should still avoid bare `*`, consistent with current product API tests.

### Gear Joint

```python
add_gear_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    pitch_radius_a,
    pitch_radius_b,
    phase_offset=None,
    name=None,
) -> Assembly
```

Parameters:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `connector_a` | `ConnectorRef` | First revolute axis connector, normally the same connector used by support revolute A. |
| `connector_b` | `ConnectorRef` | Second revolute axis connector, normally the same connector used by support revolute B. |
| `pitch_radius_a` | `float` | First gear pitch radius; finite and positive. |
| `pitch_radius_b` | `float` | Second gear pitch radius; finite and positive. |
| `phase_offset` | `float | None` | Arc-length equation offset. `None` derives and stores current offset. |
| `name` | `str | None` | Human-readable label. |

Equation:

```text
pitch_radius_a * theta_a_rad + pitch_radius_b * theta_b_rad = phase_offset
```

### Belt Joint

```python
add_belt_constraint_rassembly(
    assembly,
    constraint_id,
    connector_a,
    connector_b,
    pulley_radius_a,
    pulley_radius_b,
    phase_offset=None,
    name=None,
) -> Assembly
```

Parameters:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `pulley_radius_a` | `float` | First pulley radius; finite and positive. |
| `pulley_radius_b` | `float` | Second pulley radius; finite and positive. |

Equation:

```text
pulley_radius_a * theta_a_rad - pulley_radius_b * theta_b_rad = phase_offset
```

FreeCAD export rule:

```text
Distance  = pulley_radius_a
Distance2 = pulley_radius_b
FreeCAD AssemblyObject internally uses radiusJ = -Distance2 for Belt.
```

### Rack-Pinion Joint

```python
add_rack_pinion_constraint_rassembly(
    assembly,
    constraint_id,
    rack_connector,
    pinion_connector,
    pitch_radius,
    phase_offset=None,
    name=None,
) -> Assembly
```

Parameters:

| Parameter | Type | Meaning |
| --- | --- | --- |
| `rack_connector` | `ConnectorRef` | Connector whose +Z is the rack sliding direction in SimpleCAD prismatic semantics. |
| `pinion_connector` | `ConnectorRef` | Connector whose +Z is the pinion rotation axis in SimpleCAD revolute semantics. |
| `pitch_radius` | `float` | Pinion pitch radius; finite and positive. |
| `phase_offset` | `float | None` | Length equation offset. `None` derives and stores current offset. |

Equation:

```text
rack_distance + pitch_radius * pinion_theta_rad = phase_offset
```

FreeCAD export rule:

```text
JointType = RackPinion
Reference1 = rack_connector
Reference2 = pinion_connector
Distance = pitch_radius
```

The FreeCAD translator must keep rack first and pinion second so FreeCAD's `getRackPinionMarkers(...)` receives marker I as rack and marker J as pinion. The support Slider joint should exist in the same assembly so FreeCAD's `slidingPartIndex(...)` can validate the rack side.

## Data Model Plan

Extend `Constraint` fields without changing existing fixed/revolute/prismatic behavior.

Proposed new fields:

| Field | Applies to | Type | Validation |
| --- | --- | --- | --- |
| `pitch_radius_a` | `gear` | `float | None` | required, finite, `> 0.0` |
| `pitch_radius_b` | `gear` | `float | None` | required, finite, `> 0.0` |
| `pulley_radius_a` | `belt` | `float | None` | required, finite, `> 0.0` |
| `pulley_radius_b` | `belt` | `float | None` | required, finite, `> 0.0` |
| `pitch_radius` | `rack_pinion` | `float | None` | required, finite, `> 0.0` |
| `phase_offset` | new coupling kinds | `float | None` | `None` allowed at API boundary, stored as finite float after creation |

Alternative considered: reuse `drive_distance` and `distance_limit` for radii because FreeCAD calls them `Distance` and `Distance2`. Rejected because in SimpleCAD `drive_distance` already means a driven prismatic scalar; radii are not drive values and should be named physically.

Serialization requirements:

| Area | Required change |
| --- | --- |
| `Constraint.to_dict()` | Include new radius and phase fields with `None` for unrelated kinds. |
| `serializer.py` strict replay | Add operation names and replay branches for all three APIs. |
| `operations.py` graph recording | Add `_OP_MAKE_*` constants and include radius/phase fields in recorded params. |
| `__init__.py` | Export the three public functions. |
| auto docs / make export | Pick up public functions and generated API pages. |

## Solver And Inspection Plan

### Support Constraint Validation

Validation should not infer arbitrary geometry. It should check the assembly graph:

| Coupling kind | Validation |
| --- | --- |
| `gear` | Each connector should participate in a revolute support constraint, or strict solving reports unsupported coupling. |
| `belt` | Same as `gear`. |
| `rack_pinion` | `rack_connector` should participate in a prismatic support constraint; `pinion_connector` should participate in a revolute support constraint. |

For first implementation, support detection can be conservative:

```text
support exists if a fixed/revolute/prismatic constraint contains the same ConnectorRef on either side.
```

This mirrors FreeCAD's expectation that users choose the same coordinate systems as the supporting revolute/slider joints, while avoiding FreeCAD's GUI-only implicit guessing.

### Phase Derivation

When `phase_offset is None`, derive it when adding the constraint from current assembly placements:

| Kind | Derived phase |
| --- | --- |
| `gear` | `r_a * theta_a_rad + r_b * theta_b_rad` |
| `belt` | `r_a * theta_a_rad - r_b * theta_b_rad` |
| `rack_pinion` | `rack_distance + pitch_radius * pinion_theta_rad` |

The challenge is computing `theta_a` and `theta_b` consistently. Implementation plan:

| Step | Description |
| --- | --- |
| 1 | Locate the support constraint for each coupling connector. |
| 2 | Use the support constraint's relative frame scalar as the natural coordinate. |
| 3 | Use the current assembly placements if the support scalar is not explicitly driven. |
| 4 | Store the computed finite `phase_offset` in the coupling constraint. |

This avoids trying to infer a wheel's absolute angle only from the two gear connector frames, which is underdetermined for a pairwise connector relation.

### Solving

The existing solver propagates placements along connecting constraints. New coupling constraints should run after the base propagation pass.

Minimum solver behavior:

| Case | Behavior |
| --- | --- |
| Both coupled support scalars already satisfy equation | Report residual within tolerance. |
| One side has an explicit drive scalar and the other support constraint is free | Project the free scalar to satisfy the coupling equation, then update that component placement through the support constraint. |
| Both sides have explicit drive scalars that conflict | Strict solve fails with a coupling residual. |
| Neither side has explicit drive scalar | Preserve current phase-derived relationship; no arbitrary motion is introduced. |
| Coupling references disconnected components | Do not mark components solved; strict solve reports unsupported/disconnected coupling. |

Equations for dependent scalar:

```text
gear:        theta_b = (phase_offset - r_a * theta_a) / r_b
belt:        theta_b = (r_a * theta_a - phase_offset) / r_b
rack_pinion: rack_distance = phase_offset - pitch_radius * pinion_theta
```

If solving the opposite side, invert the equation algebraically.

### Inspection

`inspect_assembly_constraints_rconstraintreport(...)` should include residuals for new coupling constraints.

Compatibility plan:

| Field | Meaning for coupling constraints |
| --- | --- |
| `translation_error` | Absolute arc/linear residual in model length units. |
| `angular_error_degrees` | Equivalent angular residual on the second rotational side when available; otherwise `0.0`. |
| `within_tolerance` | `translation_error <= placement_tolerance` or a scale-aware coupling tolerance. |

Potential later enhancement:

```python
ConstraintResidual(
    constraint_id=...,
    translation_error=...,
    angular_error_degrees=...,
    within_tolerance=...,
    scalar_error=...,
    scalar_unit="length",
)
```

Do not add this richer residual shape in the first pass unless tests show the current two-error report is too ambiguous.

## FreeCAD Translator Plan

Extend `_make_simplecad_joint(...)` in `freecad_translator.py`.

Mapping:

| SimpleCAD kind | FreeCAD JointType | type index | Properties |
| --- | --- | --- | --- |
| `gear` | `Gears` | `11` | `Distance = pitch_radius_a`, `Distance2 = pitch_radius_b` |
| `belt` | `Belt` | `12` | `Distance = pulley_radius_a`, `Distance2 = pulley_radius_b` |
| `rack_pinion` | `RackPinion` | `9` | `Distance = pitch_radius` |

Reference mapping:

| Kind | Reference1 | Reference2 |
| --- | --- | --- |
| `gear` | `connector_a` | `connector_b` |
| `belt` | `connector_a` | `connector_b` |
| `rack_pinion` | `rack_connector` / `connector_a` | `pinion_connector` / `connector_b` |

Important translator details:

| Detail | Plan |
| --- | --- |
| Native creation | Use `JointObject.Joint(joint, type_index)` when available, as current fixed/revolute/prismatic translation does. |
| Radius properties | Assign `joint.Distance` and `joint.Distance2` after references are set. |
| Phase offset | FreeCAD JointObject has no direct phase field. Preserve `phase_offset` in `SimpleCADConstraint` metadata. Native FreeCAD solve will use current placements/solver state for phase behavior. |
| Rack marker orientation | Keep API rack first. Let FreeCAD `AssemblyObject::getRackPinionMarkers(...)` transform rack marker X to slider axis and Z to pinion axis. |
| Native status | If references or radius assignment fail, set `SimpleCADConstraintTranslationStatus = native_partial`; otherwise `native_equivalent` for property-level mapping. |

## Test Plan

Unit tests:

| File | Coverage |
| --- | --- |
| `test/test_product_assembly.py` | New public APIs in signature test; validation for positive radii; coupling constraints do not connect graph; phase default is stored finite. |
| `test/test_product_assembly.py` | Gear and belt residual signs: equal radii gear expects opposite angles, belt expects same angles. |
| `test/test_product_assembly.py` | Rack-pinion residual: `rack_distance = -pitch_radius * theta_rad` under zero phase. |
| `test/test_serialization.py` | GraphSession export/replay for all three new constraints. |
| `test/test_make_export.py` | Public API export list includes new functions. |
| `test/test_freecad_translator.py` | Generated FCStd contains native `Gears`, `Belt`, and `RackPinion` JointObjects with correct `Distance`/`Distance2` properties. |

Integration/example tests:

| Example | Expected update |
| --- | --- |
| `examples/12_herringbone_planetary_gears.py` | Add optional gear constraints between sun/planets/ring/carrier only after the fixed-ring assembly already has support revolute joints. |
| New small example if needed | Two pulleys connected by belt, one driven revolute angle, second solved to same-direction angle. |
| New small example if needed | Rack and pinion with slider rack and revolute pinion. |

FreeCAD-specific tests should create the support joints first:

| Native joint | Required support setup |
| --- | --- |
| `Gears` | two revolute joints for both rotating components. |
| `Belt` | two revolute joints for both pulleys. |
| `RackPinion` | one slider joint for rack and one revolute joint for pinion; rack/pinion coupling references the same coordinate systems. |

## Implementation Order

1. Extend `Constraint` data model and validation for new kinds and radius/phase fields.
2. Add operation constants and public API functions in `operations.py`.
3. Add serializer/replay support for the three new operations.
4. Add residual measurement for gear, belt, and rack-pinion without changing existing fixed/revolute/prismatic residual semantics.
5. Add conservative solver participation for one-driven-side coupling.
6. Extend FreeCAD translator joint-kind mapping and radius property assignment.
7. Add focused unit tests for validation, residual signs, and replay.
8. Add FCStd translation tests using support joints.
9. Update docs/auto-docs/skill generation outputs.
10. Optionally update `examples/12_herringbone_planetary_gears.py` after core tests pass.

## Open Decisions

These should be resolved before implementation starts:

| Decision | Recommended answer |
| --- | --- |
| Public radius names for gear | Use `pitch_radius_a` and `pitch_radius_b`, not FreeCAD's `Distance` names. |
| Public radius names for belt | Use `pulley_radius_a` and `pulley_radius_b`. |
| Rack connector axis in SimpleCAD | Keep +Z as rack sliding axis, consistent with current prismatic semantics; translator handles FreeCAD rack marker X conversion. |
| Phase parameter name | Use `phase_offset`, because the equation is length-valued. Avoid `phase_angle_degrees` for gear/belt because radius-weighted coupling is arc length. |
| Support inference | First pass infers support constraints by exact `ConnectorRef` participation. Later versions can allow explicit support constraint ids if ambiguity appears. |
| Whether coupling constraints connect graph | No; match FreeCAD. |

## Risks

| Risk | Mitigation |
| --- | --- |
| Natural angle is underdetermined without support constraints. | Require/support-detect revolute or prismatic constraints and derive scalars from those support constraints. |
| FreeCAD native rack-pinion may fail if no Slider support exists. | Tests and docs must state support Slider is required before rack-pinion coupling. |
| Phase behavior differs between SimpleCAD and FreeCAD native solve. | Store phase in `SimpleCADConstraint` metadata; verify exported placement before solve; document that FreeCAD native UI has no explicit phase property. |
| Existing solver is not a general nonlinear solver. | Limit first pass to one-driven-side propagation and residual reporting; do not promise arbitrary closed-loop kinematics. |
| Adding fields to `Constraint` could destabilize serialization. | Keep unrelated fields `None`, update strict replay tests, and preserve existing dict keys. |
