# Issue: GraphSession 中 X 轴圆柱端面 center 偏移导致 connector/FreeCAD Joint 引用不稳定

## 摘要

在为液压杆装配体创建 `prismatic` 滑动约束时，正确建模方式应参考 `examples/10_part_assembly.py`：从真实零件实体上选择轴向平面端面，用 `make_face_connector_rconnector(...)` 创建 connector，再用 `add_prismatic_constraint_rassembly(...)` 和 `solve_assembly_constraints_rassembly(...)`。

排查过程中发现一个更底层的问题：在 `GraphSession` 内创建 X 轴圆柱后，轴向平面端面的 `Face.get_center()` 会返回带有径向偏移的点。例如半径 `7.15` 的端面中心从期望的 `z=0.0` 变成 `z=1.7875`，即 `radius / 4`。这个错误 center 会进入 connector 的 `geo_selector`，随后在 `replay_model_json(...)` 或 FreeCAD translator 中匹配同一 face 时失败，或导致 FreeCAD Slider Joint 引用为空。

## 环境

- Repo: `SimpleCADAPI`
- 工作目录: `/Users/lildino/Project/ocws/SimpleCADAPI`
- 日期: 2026-06-26
- FreeCADCmd: `/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd`
- Python entrypoint used: `uv run python`

当前工作树存在其它未提交改动，本文只描述本次排查结论；不要把这些无关改动混入本 issue 的判断。

## 背景

液压杆装配体需要两个部件：

- `outer_sleeve`
- `piston_rod`

滑动约束应沿液压杆轴向，也就是 X 轴。`make_face_connector_rconnector(...)` 的语义是：

- connector 的 Z 轴跟随 face normal。
- `prismatic` 约束沿 connector 的 Z 轴滑动。
- 因此表达 X 轴滑动时，应选择真实零件上的轴向端面，端面 normal 为 `+X` 或 `-X`。
- 如果两个端面 normal 方向相反，rod connector 应使用 `flip=True`。

`examples/10_part_assembly.py` 正是这样做的。

## 正确参考：example 10 的做法

`examples/10_part_assembly.py` 的 connector 选择逻辑如下：

```python
sleeve_faces = ql.faces().resolve(sleeve_solid)
sleeve_end_face = None
for f in sleeve_faces:
    n = f.get_normal_at()
    if abs(abs(n.x) - 1.0) < 0.01 and f.get_area() < 1000.0:
        sleeve_end_face = f
        break
sleeve_connector = scad.make_face_connector_rconnector("slide_axis", sleeve_end_face)
```

```python
rod_faces = ql.faces().resolve(piston_rod_solid)
rod_end_face = None
for f in rod_faces:
    n = f.get_normal_at()
    if abs(abs(n.x) - 1.0) < 0.01 and f.get_area() < 1000.0:
        rod_end_face = f
        break

sleeve_normal = sleeve_end_face.get_normal_at()
rod_normal = rod_end_face.get_normal_at()
rod_flip = (sleeve_normal.x * rod_normal.x) < 0
rod_connector = scad.make_face_connector_rconnector("slide_axis", rod_end_face, flip=rod_flip)
```

已检查现有 `examples/out/hydraulic_rod_assembly/hydraulic_rod_assembly.FCStd`，其中 FreeCAD Slider Joint 是有效引用：

```text
joint make_prismatic_constraint_rassembly_node_2531eaea rod_slide
ref1 (<App::Link object>, ['Face16', 'Face16'])
ref2 (<App::Link object>, ['Face24', 'Face24'])
status native_equivalent
distance 0.0 mm
```

这说明 `example 10` 的“真实轴向端面 + flip + solve”建模方式是正确方向。

## 错误路径和原因

排查过程中曾尝试过两种错误做法：

1. 使用合成 datum face 作为 connector。
2. 使用圆柱侧面作为 connector。

这两种都不应采用。

合成 datum face 不属于零件 body 的真实子面。FreeCAD translator 会尝试把 connector 的 `geometry_ref` 解析成零件 link 上的 `FaceN` 或 `EdgeN`，但合成 datum 不在 body 上，因此 Joint 引用会为空：

```text
Reference1 (<App::Link object>, ['', ''])
Reference2 (<App::Link object>, ['', ''])
```

圆柱侧面也不适合 `make_face_connector_rconnector(...)` 的当前语义，因为 connector Z 轴来自 face normal。圆柱侧面的 normal 是径向方向，不是轴向方向。表达轴向滑动应使用轴向端面，而不是圆柱侧面。

## 最小复现

下面的最小例子复现了当前核心异常：同一个 X 轴圆柱端面，在 `GraphSession` 外 center 正确，在 `GraphSession` 内 center 出现径向偏移。

```bash
uv run python - <<'PY'
import simplecadapi as scad
from simplecadapi import ql

solid = scad.make_cylinder_rsolid(
    7.15,
    4.5,
    bottom_face_center=(-108.0, 0.0, 0.0),
    axis=(1.0, 0.0, 0.0),
)

for face in ql.faces().where(ql.surface_type('plane')).resolve(solid):
    n = face.get_normal_at()
    if abs(abs(n.x) - 1.0) < 0.01:
        c = face.get_center()
        print('outside_graph', round(c.x, 6), round(c.y, 6), round(c.z, 6), round(n.x, 6), round(face.get_area(), 6))

with scad.GraphSession():
    solid = scad.make_cylinder_rsolid(
        7.15,
        4.5,
        bottom_face_center=(-108.0, 0.0, 0.0),
        axis=(1.0, 0.0, 0.0),
    )
    for face in ql.faces().where(ql.surface_type('plane')).resolve(solid):
        n = face.get_normal_at()
        if abs(abs(n.x) - 1.0) < 0.01:
            c = face.get_center()
            print('inside_graph', round(c.x, 6), round(c.y, 6), round(c.z, 6), round(n.x, 6), round(face.get_area(), 6))
PY
```

实际输出：

```text
outside_graph -103.5 -0.0 0.0 1.0 160.60607
outside_graph -108.0 -0.0 0.0 -1.0 160.60607
inside_graph -108.0 -0.0 1.7875 -1.0 160.60607
inside_graph -103.5 -0.0 1.7875 1.0 160.60607
```

期望输出：

```text
inside_graph -108.0 0.0 0.0 -1.0 160.60607
inside_graph -103.5 0.0 0.0 1.0 160.60607
```

`1.7875` 等于 `7.15 / 4`，明显不是圆柱端面中心。

## 影响

这个偏移会进入 `make_face_connector_rconnector(...)` 的 `geometry_ref.geo_selector.center`。

后续 replay 或 FreeCAD translator 会用 `geo_selector` 在重建的 shape 上寻找同一 face。如果 selector 中的 center 已经偏移，就会出现匹配失败，例如：

```text
geo selector did not match a stable face candidate; best score=17.875
```

`17.875` 与 `1.7875 * 10` 对应，符合当前 face selector scoring 中 center 距离权重的量级。

如果 FreeCAD translator 没有成功解析到 `FaceN`，FreeCAD Slider Joint 可能出现空引用，进而在 GUI 中表现为沿默认方向或径向方向移动，而不是沿液压杆轴向移动。

## 已验证事实

1. `example 10` 的既有 `.FCStd` 中 `rod_slide` Joint 引用有效：`Face16` 和 `Face24`。
2. `example 10` 的建模策略是正确的：真实轴向端面、normal 检查、必要时 `flip=True`。
3. 合成 datum face 会导致 FreeCAD Joint 引用为空，因为它不是零件 body 上的真实子面。
4. 圆柱侧面不适合 `make_face_connector_rconnector(...)` 的轴向滑动语义，因为其 normal 是径向。
5. 最小复现显示 `GraphSession` 内 X 轴圆柱端面的 `get_center()` 存在偏移。

## 不应采用的 workaround

不要使用 index select，例如 `solid.get_faces(17)`。

原因：

- boolean 后 face 顺序不稳定。
- 改孔、改 union 顺序、换 OCC/FreeCAD 版本都可能改变 index。
- index select 不能表达“这是液压杆轴向端面”的设计意图。
- 本问题是 face center / geo selector 稳定性问题，应修 selector 或 topology/geometry wrapper，而不是绕过语义选择。

## 建议调查方向

优先调查最小复现，而不是继续改液压杆模型。

建议检查：

1. `Face.get_center()` 在 `GraphSession` 内外为何不同。
2. `GraphSession` 是否改变了 face wrapper、topology cache、metadata 或 selection wrapper 行为。
3. `center_of_mass(face.wrapped)` 对同一个 `TopoDS_Face` 是否在 GraphSession 内外拿到不同 underlying face。
4. `_make_geo_selector(...)` 是否应该对平面 face 使用更稳定的几何中心，例如 bbox center 或解析平面边界中心。
5. `serializer._geo_selector_score(...)` 和 FreeCAD translator 的 selector matching 是否应避免过度依赖 face `get_center()`，或者对 planar circular faces 使用 bbox center。
6. 是否需要为 connector 添加显式 frame/axis API，避免把装配轴线完全依赖在拓扑子面匹配上。

## 期望修复标准

修复后应满足：

1. 最小复现中 `inside_graph` 的 X 轴圆柱端面 center 回到轴心：`z=0.0`。
2. 用 `example 10` 风格选择真实轴向端面创建 connector 时，`replay_model_json(...)` 成功。
3. `translate_model_json_to_fcstd(...)` 成功生成 `.FCStd`。
4. FreeCAD 中 Slider Joint 的引用不是空字符串，而是类似：

```text
Reference1 = (<App::Link object>, ['FaceN', 'FaceN'])
Reference2 = (<App::Link object>, ['FaceM', 'FaceM'])
SimpleCADConstraintTranslationStatus = native_equivalent
```

5. FreeCAD 中拖动/编辑 Slider Joint 时，活塞杆沿 X 轴滑动，而不是径向移动。

## 当前结论

液压杆模型本身应继续采用 `example 10` 的真实轴向端面 connector 方案。当前阻塞点是 `GraphSession`/geo selector 对 X 轴圆柱端面 center 的记录不稳定，导致 replay 和 FreeCAD translator 无法可靠解析 connector face。

在修复该最小问题前，不应继续通过合成 datum、圆柱侧面或 index select 规避。
