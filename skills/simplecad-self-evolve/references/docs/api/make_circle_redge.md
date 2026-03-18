# make_circle_redge

## API Definition

```python
def make_circle_redge(center: Tuple[float, float, float], radius: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Edge
```

*Source: operations.py*

## Description

创建圆形并返回边对象

创建圆形边对象，用于构建圆形轮廓、圆弧路径等。圆的方向由法向量确定，
支持在任意平面内创建圆形。支持当前坐标系变换。

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

Edge: 创建的边对象，表示一个完整的圆形

## Raises

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常

## Examples

### Example 1
```python
# 创建XY平面上的圆
circle = make_circle_redge((0, 0, 0), 2.0)
```

### Example 2
```python
# 创建垂直平面上的圆
vertical_circle = make_circle_redge((0, 0, 0), 1.5, (1, 0, 0))
```

### Example 3
```python
# 创建指定位置的圆
offset_circle = make_circle_redge((2, 3, 1), 1.0, (0, 0, 1))
```
