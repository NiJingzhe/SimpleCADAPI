# make_circle_rface

## API Definition

```python
def make_circle_rface(center: Tuple[float, float, float], radius: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Face
```

*Source: operations.py*

## Description

创建圆形并返回面对象

创建圆形面对象，用于构建实心圆形截面。可以用于拉伸、旋转等操作来创建
圆柱体、圆锥体等三维几何体。面积等于πr²。

## Parameters

### center

- **Type**: `Tuple[float, float, float]`
- **Description**: 圆心坐标 (x, y, z)，定义圆的中心位置

### radius

- **Type**: `float`
- **Description**: 圆的半径，必须为正数

### normal

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 圆所在平面的法向量 (x, y, z)， 默认为 (0, 0, 1) 表示XY平面

## Returns

Face: 创建的面对象，表示一个实心的圆形面

## Raises

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常

## Examples

### Example 1
```python
# 创建标准圆形面
circle_face = make_circle_rface((0, 0, 0), 2.0)
area = circle_face.get_area()  # 面积为π×2²≈12.57
```

### Example 2
```python
# 创建用于拉伸的圆形截面
profile = make_circle_rface((0, 0, 0), 1.0)
cylinder = extrude_rsolid(profile, (0, 0, 1), 5.0)
```
