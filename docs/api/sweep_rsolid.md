# sweep_rsolid

## API定义

```python
def sweep_rsolid(profile: Face, path: Wire, is_frenet: bool = False) -> Solid
```

*来源文件: operations.py*

## API作用

沿指定路径扫掠二维轮廓创建三维实体或壳体。常用于创建管道、导线、
复杂曲面等。Frenet框架控制轮廓在路径上的旋转行为。

## API参数说明

### profile

- **类型**: `Face`
- **说明**: 要扫掠的轮廓面，定义扫掠的横截面形状

### path

- **类型**: `Wire`
- **说明**: 扫掠路径线，定义轮廓沿其移动的路径

### is_frenet

- **类型**: `bool, optional`
- **说明**: 是否使用Frenet框架，默认为False。 True时轮廓沿路径的法向量旋转，False时保持轮廓方向

## 返回值说明

Union[Solid, Shell]: 扫掠后的实体或壳体，取决于make_solid参数

## 异常

- **ValueError**: 当轮廓、路径无效或扫掠操作失败时抛出异常

## API使用例子

```python
# 沿直线扫掠圆形创建圆管
circle = make_circle_rface((0, 0, 0), 0.5)
line_path = make_segment_rwire((0, 0, 0), (10, 0, 0))
tube = sweep_rsolid(circle, line_path)
# 沿螺旋路径扫掠创建螺旋管
square = make_rectangle_rface(0.2, 0.2)
helix_path = make_helix_rwire(1.0, 5.0, 2.0)
spiral_tube = sweep_rsolid(square, helix_path, is_frenet=True)
# 沿曲线扫掠创建复杂形状
profile = make_rectangle_rface(1.0, 0.5)
curve_points = [(0, 0, 0), (2, 2, 1), (4, 0, 2), (6, -1, 3)]
curve_path = make_spline_rwire(curve_points)
swept_shape = sweep_rsolid(profile, curve_path)
```
