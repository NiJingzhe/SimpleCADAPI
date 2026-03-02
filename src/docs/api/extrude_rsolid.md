# extrude_rsolid

## API定义

```python
def extrude_rsolid(profile: Union[Wire, Face], direction: Tuple[float, float, float], distance: float) -> Solid
```

*来源文件: operations.py*

## API作用

沿指定方向拉伸二维轮廓创建三维实体。如果输入是线，必须是封闭的线；
如果输入是面，直接进行拉伸。这是创建柱状、管状等规则几何体的基础操作。

## API参数说明

### profile

- **类型**: `Union[Wire, Face]`
- **说明**: 要拉伸的轮廓，可以是封闭的线或面

### direction

- **类型**: `Tuple[float, float, float]`
- **说明**: 拉伸方向向量 (x, y, z)， 定义拉伸的方向，会被标准化处理

### distance

- **类型**: `float`
- **说明**: 拉伸距离，必须为正数

## 返回值说明

Solid: 拉伸后的实体对象

## 异常

- **ValueError**: 当轮廓不是封闭的线、距离小于等于0或其他参数无效时抛出异常

## API使用例子

```python
# 拉伸圆形面创建圆柱体
circle = make_circle_rface((0, 0, 0), 1.0)
cylinder = extrude_rsolid(circle, (0, 0, 1), 5.0)
# 拉伸矩形面创建立方体
rect = make_rectangle_rface(2.0, 2.0)
box = extrude_rsolid(rect, (0, 0, 1), 3.0)
# 拉伸复杂轮廓
points = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (0, 1, 0)]
profile_wire = make_polyline_rwire(points, closed=True)
extruded_shape = extrude_rsolid(profile_wire, (0, 0, 1), 4.0)
```
