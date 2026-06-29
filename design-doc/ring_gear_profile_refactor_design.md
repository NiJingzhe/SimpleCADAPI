# Ring Gear Profile Refactor Design

本文定义齿轮环建模重构方案。目标是让齿轮环和外齿轮一样，先构造正确的 2D 齿形轮廓，再由轮廓生成实体；直齿齿轮环不再通过 `outer disc - inner cutout` 的 2D boolean 得到。

## 背景问题

当前齿轮环实现有两个核心问题：

- 直齿齿轮环通过 `make_2d_cut_rface(outer_face, inner_gear_face)` 得到，建模方式是 boolean cut，不是直接 profile extrude。
- 当前 `_build_internal_gear_cutout_face(...)` 仍复用 `_build_gear_profile_face(...)`，只是替换了内齿轮半径；这会把外齿轮式 profile 套到齿轮环内孔上，不能保证内齿边界是正确的“向内齿形轮廓”。

用户要求的目标建模方式是：

```text
外齿轮:
    正确外齿形 wire/profile -> face -> extrude

齿轮环:
    外圆 wire + 正确内齿形 inner wire -> face with inner loop -> extrude
```

也就是说，直齿齿轮环的截面应该直接是一个带内环的 face：

```text
ring_face = Face(outer_circle_wire, inner_internal_gear_wire)
ring_solid = extrude(ring_face)
```

不是：

```text
ring_face = 2d_cut(outer_disc_face, inner_cutout_face)
```

## 设计目标

- 新增直接构造带 inner loop face 的能力。
- 直齿齿轮环改成 direct profile extrude。
- 内齿边界用专门的 internal gear profile wire builder，不再调用外齿轮 `_build_gear_profile_face(...)`。
- 斜齿/人字齿齿轮环短期允许使用 `outer_solid - inner_loft`，但 inner loft 必须来自正确内齿 profile wire。
- 长期扩展 `loft_rsolid(...)` 支持带 inner loops 的 section face，最终让斜齿/人字齿也可以从 multi-loop sections 直接 loft。

## 非目标

- 本阶段不引入外部依赖。
- 本阶段不要求一次性实现 full rack-cutter trochoid root fillet，但设计上必须为后续替换成 true generated fillet 留接口。
- 本阶段不重写所有 gear public API 参数。

## 术语

- `outer_wire`: 齿轮环外圆边界。
- `inner_wire`: 齿轮环内齿形边界，即孔的边界。
- `internal tooth tip radius`: 内齿齿顶半径，通常 `pitch_radius - module`。
- `internal tooth root radius`: 内齿齿根/齿槽底半径，通常 `pitch_radius + 1.25 * module`。
- `ring_face`: 一个 face，outer boundary 是外圆，inner boundary 是内齿轮边界。

## 新增 API: make_face_from_wires_rface

### Public API

新增：

```python
def make_face_from_wires_rface(
    outer_wire: Wire,
    inner_wires: Sequence[Wire],
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    ...
```

规则：

- `outer_wire` 必须闭合。
- 每个 `inner_wire` 必须闭合。
- `inner_wires` 可以为空；为空时行为等价于 `make_face_from_wire_rface(outer_wire, normal)`。
- 返回的 `Face` 必须保留 inner wires，可通过 `face.get_inner_wires()` 查询。
- Public API 签名不使用裸 `*`。

### Kernel 伪代码

文件：`src/simplecadapi/kernel/ocp_features.py`

```python
def make_face_from_wires(outer_wire, inner_wires):
    builder = BRepBuilderAPI_MakeFace(outer_wire, True)
    if not builder.IsDone():
        raise ValueError("failed to initialize face from outer wire")

    for inner in inner_wires:
        builder.Add(inner)
        if not builder.IsDone():
            raise ValueError("failed to add inner wire to face")

    return builder.Face()
```

### Operations 伪代码

文件：`src/simplecadapi/operations.py`

```python
_OP_MAKE_FACE_FROM_WIRES_RFACE = "make_face_from_wires_rface"

def make_face_from_wires_rface(outer_wire, inner_wires, normal=(0, 0, 1)):
    if not isinstance(outer_wire, Wire):
        raise ValueError("outer_wire must be a Wire")
    if not outer_wire.is_closed():
        raise ValueError("outer_wire must be closed")

    inner_list = list(inner_wires or [])
    for inner in inner_list:
        if not isinstance(inner, Wire):
            raise ValueError("inner_wires must contain Wire objects")
        if not inner.is_closed():
            raise ValueError("inner wire must be closed")

    face_shape = make_face_from_wires_ocp(
        outer_wire.wrapped,
        [inner.wrapped for inner in inner_list],
    )
    face = Face(face_shape)

    return _finalize_derived_shape(
        face,
        op=_OP_MAKE_FACE_FROM_WIRES_RFACE,
        params={"inner_wire_count": len(inner_list), "normal": normal},
        input_shapes=[outer_wire, *inner_list],
        tags={"derived", "face"},
    )
```

### Serializer / Replay

更新：

- `serializer.py` canonical op allowlist。
- replay 分支。
- import/export model JSON。

伪代码：

```python
if op_name == "make_face_from_wires_rface":
    wire_outputs = _all_input_outputs(ctx, outputs, node)
    outer = cast(Wire, wire_outputs[0])
    inners = [cast(Wire, item) for item in wire_outputs[1:]]
    result = ops.make_face_from_wires_rface(outer, inners, normal=params.get("normal", (0, 0, 1)))
    _store_outputs(node, result)
```

### FreeCAD Translator

生成脚本需要支持 `Part.Face([outer_wire, inner_wire_0, ...])` 或等价构造。

伪代码：

```python
def _face_shape_from_wires(outer_obj, inner_objs):
    outer_shape = _shape_from_object(outer_obj)
    outer_wire = outer_shape.Wires[0] if outer_shape.ShapeType != "Wire" else outer_shape

    wires = [outer_wire]
    for inner_obj in inner_objs:
        inner_shape = _shape_from_object(inner_obj)
        inner_wire = inner_shape.Wires[0] if inner_shape.ShapeType != "Wire" else inner_shape
        wires.append(inner_wire)

    face = Part.Face(wires)
    if not face.isValid():
        raise RuntimeError("multi-loop face is invalid")
    return face
```

Translator node 伪代码：

```python
if node.op == "make_face_from_wires_rface":
    outer_id = inputs[0]
    inner_ids = inputs[1:]
    return [
        f"{var_name} = _make_feature(..., _face_shape_from_wires(GRAPH_NODES[outer_id], [GRAPH_NODES[i] for i in inner_ids]), ...)"
    ]
```

需要用 FreeCAD 实测 `Part.Face([outer, inner])` 的 orientation 要求。如果 orientation 不对，translator 层应 reverse inner wire，而不是依赖用户。

## 内齿轮 profile wire builder

新增或重构：

```python
def _build_internal_gear_profile_wire(
    n_teeth: int,
    module: float,
    pressure_angle: float,
) -> Wire:
    ...
```

这个函数返回的是齿轮环的内边界 wire，不返回 face，不做 cut。

### 几何约定

```python
pitch_radius = module * n_teeth / 2.0
base_radius = pitch_radius * cos(pressure_angle)
tooth_tip_radius = pitch_radius - module
tooth_root_radius = pitch_radius + 1.25 * module
tooth_angle = 2*pi / n_teeth
```

内齿轮内边界是“齿向内”的完整边界。单齿边界顺序建议为：

```text
tooth root / tooth-space bottom arc
internal involute flank
internal tooth tip arc
opposite internal involute flank
root transition / next root arc
```

注意：这里的 `root` 和 `tip` 是内齿材料的 root/tip，而不是外齿轮 profile builder 的 root/tip。

### 伪代码

```python
def _build_internal_gear_profile_wire(n_teeth, module, pressure_angle):
    geo = _compute_internal_gear_geometry(n_teeth, module, pressure_angle)
    sketch = make_sketch_rsketch(name=f"internal_gear_{n_teeth}t_m{module}", plane="XY")
    sketch = add_point_rsketch(sketch, "center", 0.0, 0.0)
    sketch = constrain_fix_rsketch(sketch, "center")

    sketch = add_circle_rsketch(sketch, "pitch_circle", "center", geo.pitch_radius, construction=True)
    sketch = add_circle_rsketch(sketch, "base_circle", "center", geo.base_radius, construction=True)
    sketch = add_circle_rsketch(sketch, "tip_circle", "center", geo.tooth_tip_radius, construction=True)
    sketch = add_circle_rsketch(sketch, "root_circle", "center", geo.tooth_root_radius, construction=True)

    for i in range(n_teeth):
        offset = i * geo.tooth_angle

        # Points on the inner tooth tip circle, root/tooth-space bottom circle,
        # and visible involute start/end positions.
        p_root_a = point_on_radius(geo.tooth_root_radius, geo.root_start_angle + offset)
        p_flank_a = internal_involute_point(..., side="left", offset=offset)
        p_tip_a = point_on_radius(geo.tooth_tip_radius, geo.tip_start_angle + offset)
        p_tip_b = point_on_radius(geo.tooth_tip_radius, geo.tip_end_angle + offset)
        p_flank_b = internal_involute_point(..., side="right", offset=offset)
        p_root_b = point_on_radius(geo.tooth_root_radius, geo.root_end_angle + offset)

        add fixed points to sketch

    for i in range(n_teeth):
        add root/tooth-space bottom arc
        add left internal involute B-spline
        add tooth tip arc
        add right internal involute B-spline
        add root transition if needed

    return make_wire_from_sketch_rwire(sketch)
```

### Internal involute function

不要复用 `_build_gear_profile_face(...)`。

建议新增：

```python
def _internal_involute_bspline_control_points(
    base_radius: float,
    start_radius: float,
    end_radius: float,
    start_angle: float,
    side: Literal["left", "right"],
    reverse: bool = False,
) -> tuple[list[list[float]], int, list[float], list[int]]:
    ...
```

它可以复用低层 `_involute_point(...)`，但要明确内部齿轮的半径方向和 flank orientation，不要通过“外齿轮 profile + swapped radii”间接得到。

## 直齿齿轮环重构

当前：

```python
outer_face = make_circle_rface(center=(0, 0, 0), radius=outer_radius)
inner_gear_face = _build_internal_gear_cutout_face(...)
ring_face = make_2d_cut_rface(outer_face, inner_gear_face)
return extrude_rsolid(ring_face, direction=(0, 0, 1), distance=gear_height)
```

目标：

```python
def _build_ring_gear_face(n_teeth, module, pressure_angle, rim_thickness):
    _pitch, _tip, internal_root_radius, outer_radius = _internal_ring_radii(
        n_teeth, module, rim_thickness,
    )
    outer_wire = make_circle_rwire(center=(0.0, 0.0, 0.0), radius=outer_radius)
    inner_wire = _build_internal_gear_profile_wire(n_teeth, module, pressure_angle)
    return make_face_from_wires_rface(outer_wire, [inner_wire])

def make_spur_ring_gear_rsolid(...):
    face = _build_ring_gear_face(...)
    return extrude_rsolid(face, direction=(0.0, 0.0, 1.0), distance=gear_height)
```

直齿齿轮环的 graph 中不应再出现 `make_2d_cut_rface`。

## 斜齿 / 人字齿齿轮环阶段方案

短期可接受方案：

```text
outer_solid = extrude outer circle / loft outer circle sections
inner_void_loft = loft internal gear profile wires along helix/herringbone twist
ring_solid = cut(outer_solid, inner_void_loft)
```

注意：这里的 cut 是 3D 去料路径，inner void 必须来自正确的 internal gear profile wire。这个方案仍然可接受，因为斜齿/人字齿本质上需要沿轴向生成扭转齿槽体。

伪代码：

```python
def make_helical_ring_gear_rsolid(...):
    outer_wire = make_circle_rwire(center=(0, 0, 0), radius=outer_radius)
    inner_wire = _build_internal_gear_profile_wire(n_teeth, module, pressure_angle)

    outer_solid = extrude_rsolid(
        make_face_from_wire_rface(outer_wire),
        direction=(0, 0, 1),
        distance=gear_height,
    )

    inner_sections = []
    for i in range(n_sections + 1):
        frac = i / n_sections
        z = gear_height * frac
        twist = twist_total * frac
        inner_sections.append(_rotate_profile_wire_3d(inner_wire, twist, z))

    inner_void = loft_rsolid(inner_sections, ruled=False)
    return cut_rsolid(outer_solid, inner_void)
```

人字齿类似，只是 twist 先增加再回到中心或反向。

## 长期方案: loft 支持 inner loops

最终目标：

```python
sections = []
for i in range(n_sections + 1):
    outer_wire_i = rotate/translate outer circle wire
    inner_wire_i = rotate/translate internal gear wire
    section_face_i = make_face_from_wires_rface(outer_wire_i, [inner_wire_i])
    sections.append(section_face_i)

ring_solid = loft_rsolid(sections, ruled=False)
```

需要扩展 `loft_rsolid(...)`：

- 当前主要接收 `Wire` sections。
- 新增支持 `Face` sections，其中 face 可以有 inner wires。
- 如果 OCP `BRepOffsetAPI_ThruSections` 不能直接处理 multi-loop face sections，需要实现自定义策略：
  - outer wires loft 成 outer shell。
  - 每组 inner wires loft 成 inner shell。
  - cap top/bottom multi-loop faces。
  - sew shell -> solid。

伪代码：

```python
def loft_rsolid(sections, ruled=False):
    if all(isinstance(section, Wire) for section in sections):
        return _loft_wire_sections(sections, ruled=ruled)

    if all(isinstance(section, Face) for section in sections):
        if all(len(section.get_inner_wires()) == 0 for section in sections):
            return _loft_wire_sections([section.get_outer_wire() for section in sections], ruled=ruled)

        return _loft_multi_loop_face_sections(sections, ruled=ruled)

    raise ValueError("loft sections must be all Wire or all Face")

def _loft_multi_loop_face_sections(sections, ruled=False):
    outer_wires = [face.get_outer_wire() for face in sections]
    inner_wire_groups = transpose([face.get_inner_wires() for face in sections])

    outer_shell = loft_shell(outer_wires, ruled=ruled)
    inner_shells = [loft_shell(group, ruled=ruled) for group in inner_wire_groups]
    bottom_cap = sections[0]
    top_cap = sections[-1]

    shell = sew([outer_shell, *inner_shells, bottom_cap, top_cap])
    return make_solid_from_shell(shell)
```

这部分是后续阶段，不阻塞直齿齿轮环修复。

## 测试计划

### API 测试

```python
def test_make_face_from_wires_creates_inner_wire():
    outer = make_circle_rwire(center=(0,0,0), radius=10)
    inner = make_circle_rwire(center=(0,0,0), radius=4)
    face = make_face_from_wires_rface(outer, [inner])
    assert len(face.get_inner_wires()) == 1
    assert face.get_area() == approx(pi * (10**2 - 4**2))
```

### Serializer / Replay

```python
def test_make_face_from_wires_replays():
    with GraphSession() as session:
        outer = make_circle_rwire(...)
        inner = make_circle_rwire(...)
        face = make_face_from_wires_rface(outer, [inner])
    payload = export_model_json(session)
    replayed = replay_model_json(payload)
    assert replayed[-1].get_area() == approx(face.get_area())
```

### Spur ring graph 测试

```python
def test_spur_ring_gear_uses_direct_multi_loop_face_not_2d_cut():
    with GraphSession() as session:
        ring = make_spur_ring_gear_rsolid(...)
    payload = export_model_json(session)
    ops = [node["op"] for node in payload["graph"]["nodes"]]
    assert "make_face_from_wires_rface" in ops
    assert "make_2d_cut_rface" not in ops
```

### Spur ring geometry 测试

```python
def test_spur_ring_gear_face_has_internal_tooth_boundary():
    face = _build_ring_gear_face(...)
    assert len(face.get_inner_wires()) == 1
    assert min_radius(face.get_inner_wires()[0]) == approx(pitch_radius - module)
    assert max_radius(face.get_inner_wires()[0]) == approx(pitch_radius + 1.25 * module)
```

### FreeCAD Translator 测试

```python
def test_fcstd_multi_loop_face_extrudes_as_ring_not_disk():
    with GraphSession() as session:
        outer = make_circle_rwire(...)
        inner = make_circle_rwire(...)
        face = make_face_from_wires_rface(outer, [inner])
        solid = extrude_rsolid(face, ...)
    fcstd = translate_model_json_to_fcstd(export_model_json(session), ...)
    assert opened_fcstd_solid_volume == approx(expected_ring_volume)
```

## Implementation Order

1. Add kernel `make_face_from_wires(...)`.
2. Add public `make_face_from_wires_rface(...)` in `operations.py` and export in `__init__.py`.
3. Add serializer canonical/replay support.
4. Add FreeCAD translator support for multi-loop face.
5. Add API/serialization/FreeCAD tests for multi-loop face.
6. Rename/rewrite `_build_internal_gear_cutout_face(...)` into `_build_internal_gear_profile_wire(...)`.
7. Rewrite `_build_ring_gear_face(...)` to use `make_face_from_wires_rface(...)`.
8. Update `make_spur_ring_gear_rsolid(...)` and tests to ensure no `make_2d_cut_rface` appears.
9. Update helical/herringbone ring to use `_build_internal_gear_profile_wire(...)` for inner loft.
10. Regenerate `examples/11_stdlib_gears.py` outputs.
11. Run affected suites with `uv run python -m pytest ...`.

## Open Questions

- FreeCAD `Part.Face([outer_wire, inner_wire])` orientation behavior must be verified. If needed, translator should reverse inner wires automatically.
- Exact internal gear flank formula should be implemented directly and tested independently; do not derive it by calling external gear profile builder with swapped radii.
- Full generated root fillet for gears should eventually be rack-cutter/trochoid based. The current tangent root transition can remain a controlled intermediate only if documented as such.
- Multi-loop loft is desirable but can be deferred until straight ring gears are direct-profile extruded.
