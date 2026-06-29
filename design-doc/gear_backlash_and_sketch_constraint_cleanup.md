# Gear Backlash And Sketch Constraint Cleanup

本文定义下一步齿轮标准件修正计划：先移除齿轮 profile builder 中多余的逐点 `fix` 约束，再给 internal ring gear 增加 `backlash`，最后保证 FreeCAD 导出的 FCStd 中仍保留可检查的 Sketcher profile。

## 实施状态

已完成：

- 外齿轮、内齿轮环、rack profile 不再给每个解析 profile 点添加 `fix` 约束。
- 外齿轮和内齿轮环仍保留 center point 的单个 `fix` 约束。
- 连接关系继续通过 shared point id 表达，FreeCAD translator 仍生成必要 coincident constraints。
- `make_spur_ring_gear_rsolid(...)`、`make_helical_ring_gear_rsolid(...)`、`make_herringbone_ring_gear_rsolid(...)` 已新增 `backlash` 参数。
- internal ring gear geometry 已使用 `backlash_half_angle = backlash / (2.0 * pitch_radius)` 缩小 ring material tooth half-angle。
- `backlash` 当前要求是 finite 且 non-negative。
- FreeCAD translator 已删除 large sketch -> `Part::Feature` fallback，large sketch promotion 会继续导出 `Sketcher::SketchObject`。
- `examples/11_stdlib_gears.py` 已使用 `BACKLASH = 0.08 * MODULE` 并重新生成 ring gear JSON/STEP/FCStd 输出。
- 测试已覆盖 fix constraint cleanup、backlash tooth-space increase、large sketch Sketcher export。

验证结果：

```bash
uv run python -m pytest test/test_stdlib_gear.py -q
# 35 passed

uv run python -m pytest test/test_freecad_translator.py -q
# 58 passed

uv run python -m pytest test/test_serialization.py -q
# 54 passed

uv run python -m pytest -q
# 537 passed

uv run python examples/11_stdlib_gears.py
# regenerated examples/out/ring_gears/*.model.json, *.step, *.FCStd
```

## 背景

当前 `std.gear` 的外齿轮、内齿轮环、rack profile 都使用 constrained sketch 生成 profile。为了让已解析出来的 profile 点稳定，代码曾对每个点调用：

```python
constrain_fix_rsketch(sketch, point_id)
```

这导致 66 齿 ring gear 的内部齿形 sketch 产生数百个 `fix` constraints：

```text
每齿 7 个点 * 66 = 462 个点
center point = 1 个点
fix constraints ~= 463
再加 radius/concentric 等约束
```

这些 per-point `fix` 对 gear profile 是多余的，因为这些点本来就是解析计算结果，edge/arc/bspline 直接引用同一个 point id 就已经表达了 profile 的连接关系。

同时，当前 internal ring gear 是理论零背隙齿形。与 planet gear 啮合时，pitch 附近有效裕量非常小，视觉上和数值上都容易表现为 overlap。因此需要给 ring gear 增加 `backlash`，扩大 ring tooth space。

## 目标

- 删除 gear/ring/rack profile 中大量 per-point `fix` constraints。
- 保留必要的 construction geometry 约束，例如 radius/concentric。
- 保留 shared endpoint 连接关系，依靠相同 point id 表达相邻曲线端点重合。
- FreeCAD translator 仍然导出真实 `Sketcher::SketchObject`，不要因为 sketch 大而退化成 `Part::Feature`。
- 给 internal ring gear API 增加 `backlash` 参数。
- standalone ring gear example 使用非零 backlash，并导出新的 FCStd。

## 非目标

- 本阶段不重写外齿轮齿根为真正 rack-cutter trochoid。
- 本阶段不把所有 gear profile 参数完全表达成 FreeCAD Sketcher 可求解约束。
- 本阶段不做完整齿轮啮合仿真或碰撞检测。

## Fix Constraint Cleanup

### 当前问题位置

外齿轮 profile：

```python
# src/simplecadapi/std/gear.py
sketch = add_point_rsketch(sketch, "center", 0.0, 0.0)
sketch = constrain_fix_rsketch(sketch, "center")

for i, td in enumerate(tooth_data):
    for key, (px, py) in ...:
        pid = f"t{i}_{key}"
        sketch = add_point_rsketch(sketch, pid, px, py)
        sketch = constrain_fix_rsketch(sketch, pid)
```

内齿轮环 profile：

```python
sketch = add_point_rsketch(sketch, "center", 0.0, 0.0)
sketch = constrain_fix_rsketch(sketch, "center")

for i, td in enumerate(tooth_data):
    for key in point_keys:
        pid = f"t{i}_{key}"
        sketch = add_point_rsketch(sketch, pid, px, py)
        sketch = constrain_fix_rsketch(sketch, pid)
```

rack profile：

```python
sketch = constrain_fix_rsketch(sketch, f"p{idx}")
```

### 修改方案

删除 profile 点的 `constrain_fix_rsketch(...)`：

```python
for i, td in enumerate(tooth_data):
    for key, (px, py) in ...:
        pid = f"t{i}_{key}"
        sketch = add_point_rsketch(sketch, pid, px, py)
```

center 点可以保留 `fix`，因为它只有一个约束，不是性能瓶颈，并且 construction circles 以它为中心。

### 为什么连接不会丢

相邻 profile 曲线共享同一个 point id，例如：

```python
add_arc_rsketch(..., rs_id, re_id, "center")
add_bspline_rsketch(..., re_id, lb_id, ...)
```

这里 arc end 和 bspline start 都引用 `re_id`。SimpleCAD sketch promotion 能直接使用这个 shared endpoint。FreeCAD translator 也会根据相同 point id 自动生成 synthetic coincident constraints。

### 预期结果

66 齿 ring gear 内部 sketch 的 constraints 数量会大幅减少：

```text
删除前：463+ fix constraints + radius/concentric + synthetic coincident
删除后：center fix + radius/concentric + synthetic coincident
```

这样 FreeCAD Sketcher 导出和打开速度会明显改善。

## Backlash

### 问题

当前 internal ring gear 是理论零背隙。对于 `module=1.5, planet_z=24, ring_z=66`，正确坐标变换后，pitch 附近 ring tooth space 对 planet tooth 的有效 clearance 只有约 `0.009 mm`。

这对 CAD 视觉检查、B-spline 拟合误差和实际制造都太紧。

### 新增参数

给 internal ring gear API 增加：

```python
backlash: float = 0.0
```

受影响函数：

```python
_compute_internal_tooth_geometry(..., backlash=0.0)
_build_internal_gear_profile_wire(..., backlash=0.0)
_build_ring_gear_face(..., backlash=0.0)
make_spur_ring_gear_rsolid(..., backlash=0.0)
make_helical_ring_gear_rsolid(..., backlash=0.0)
make_herringbone_ring_gear_rsolid(..., backlash=0.0)
```

### 几何公式

当前 internal material tooth half-angle：

```python
internal_half_angle = pitch_half_angle - inv_alpha + inv_r
```

加入 backlash 后：

```python
backlash_half_angle = backlash / (2.0 * pitch_radius)
internal_half_angle = pitch_half_angle - inv_alpha + inv_r - backlash_half_angle
```

解释：

```text
减小 internal ring material tooth thickness
= 扩大 internal tooth space
= 给 planet tooth flank 留出 backlash
```

### 参数校验

```python
if not math.isfinite(backlash):
    raise ValueError("backlash must be finite")
if backlash < 0:
    raise ValueError("backlash must be non-negative")
```

可以先不设置上限，但测试里应覆盖负数报错。

### Example 默认值

standalone ring gear example 使用：

```python
BACKLASH = 0.08 * MODULE
```

对于 `MODULE = 1.5`：

```text
BACKLASH = 0.12 mm
```

## FreeCAD Sketch Export

### 当前问题

FreeCAD translator 当前有 large sketch fallback：

```python
if len(entities_preview) > 50:
    obj = doc.addObject('Part::Feature', name)
    obj.Shape = _sketch_wire_shape_from_promotion(params)
```

这会导致 FCStd 中看不到内部齿形 `Sketcher::SketchObject`，只能看到 materialized wire/face。

### 修改方案

删除 large sketch -> `Part::Feature` fallback。

所有 sketch promotion 都导出为：

```python
obj = doc.addObject('Sketcher::SketchObject', name)
```

为了避免 FreeCAD 被大量 solver constraints 卡死：

- 几何全部导出成 Sketcher geometry。
- 删除 per-point fix 后 constraints 已大幅减少。
- 如果后续仍慢，再只跳过 constraint materialization，但不退化为 `Part::Feature`。

本阶段先删除 per-point fix，并保留 Sketcher constraint materialization。

## Tests

### Constraint Cleanup Tests

新增或更新测试：

```python
def test_internal_profile_does_not_fix_every_profile_point():
    _wire, sketch = _build_internal_gear_profile_wire(..., return_sketch=True)
    fix_constraints = [c for c in sketch.constraints if c.kind == "fix"]
    assert len(fix_constraints) <= 1
```

外齿轮同理：

```python
def test_external_profile_does_not_fix_every_profile_point():
    _face, sketch = _build_gear_profile_face(..., return_sketch=True)
    fix_constraints = [c for c in sketch.constraints if c.kind == "fix"]
    assert len(fix_constraints) <= 1
```

### Backlash Tests

```python
def test_ring_backlash_increases_tooth_space():
    no_backlash = _build_internal_gear_profile_wire(..., backlash=0.0)
    with_backlash = _build_internal_gear_profile_wire(..., backlash=0.12)
    assert with_backlash has wider tooth-space angle than no_backlash
```

Graph/API test：

```python
make_spur_ring_gear_rsolid(..., backlash=0.12)
```

Negative backlash test：

```python
with pytest.raises(Exception):
    make_spur_ring_gear_rsolid(..., backlash=-0.1)
```

### FreeCAD Translator Tests

更新 translator 测试，确保 large sketch promotion 不再生成 bridge `Part::Feature`：

```python
assert sketch.TypeId == "Sketcher::SketchObject"
assert sketch.SimpleCADOp == "make_wire_from_sketch_rwire"
```

Standalone ring gear FCStd probe：

```text
spur_ring_gear.FCStd contains internal Sketcher::SketchObject
internal Sketcher geometry includes BSpline entities
make_2d_cut_rface count == 0
final solid count == 1
```

## Implementation Order

1. Remove per-point `constrain_fix_rsketch(...)` in external gear, internal ring gear, and rack builders.
2. Add backlash parameter through internal ring gear helpers and public APIs.
3. Update standalone ring gear example with `BACKLASH = 0.08 * MODULE`.
4. Remove large sketch -> `Part::Feature` fallback from FreeCAD translator.
5. Update tests for fix constraint count and backlash.
6. Run:
   ```bash
   uv run python -m pytest test/test_stdlib_gear.py -q
   uv run python -m pytest test/test_freecad_translator.py -q
   uv run python examples/11_stdlib_gears.py
   ```
7. Probe generated FCStd files for visible `Sketcher::SketchObject`, BSpline geometry, and final solid count.
