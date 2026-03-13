# make_rectangle_rface

## API Definition

```python
def make_rectangle_rface(width: float, height: float, center: Tuple[float, float, float] = (0, 0, 0), normal: Tuple[float, float, float] = (0, 0, 1)) -> Face
```

*Source: operations.py*

## Description

创建矩形并返回面对象

创建矩形面对象，用于构建实心矩形截面。可以用于拉伸、旋转等操作来创建
立方体、棱柱等三维几何体。面积等于width×height。

## Parameters

### width

- **Type**: `float`
- **Description**: 矩形的宽度，必须为正数

### height

- **Type**: `float`
- **Description**: 矩形的高度，必须为正数

### center

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 矩形中心坐标 (x, y, z)， 默认为 (0, 0, 0)

### normal

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 矩形所在平面的法向量 (x, y, z)， 默认为 (0, 0, 1) 表示XY平面

## Returns

Face: 创建的面对象，表示一个实心的矩形面

## Raises

- **ValueError**: 当宽度或高度小于等于0或其他参数无效时抛出异常

## Examples

### Example 1
```python
# 创建标准矩形面
rect_face = make_rectangle_rface(5.0, 3.0)
area = rect_face.get_area()  # 面积为5×3=15
```

### Example 2
```python
# 创建用于拉伸的矩形截面
profile = make_rectangle_rface(2.0, 2.0)
box = extrude_rsolid(profile, (0, 0, 1), 3.0)
```
