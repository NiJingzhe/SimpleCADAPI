# make_face_from_wire_rface

## API Definition

```python
def make_face_from_wire_rface(wire: Wire, normal: Tuple[float, float, float] = (0, 0, 1)) -> Face
```

*Source: operations.py*

## Description

从封闭的线对象创建面对象

将封闭的线轮廓转换为面对象，用于从复杂的线框轮廓创建面。输入的线必须
是封闭的，函数会检查面的法向量方向，如果与期望方向相反会发出警告。

## Parameters

### wire

- **Type**: `Wire`
- **Description**: 输入的线对象，必须是封闭的线轮廓

### normal

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 期望的面法向量 (x, y, z)， 用于确定面的方向，默认为 (0, 0, 1)

## Returns

Face: 创建的面对象，由输入的线轮廓围成的面

## Raises

- **ValueError**: 当输入的线对象无效、不封闭或创建面失败时抛出异常

## Examples

### Example 1
```python
# 从矩形线创建面
rect_wire = make_rectangle_rwire(3.0, 2.0)
rect_face = make_face_from_wire_rface(rect_wire)
```

### Example 2
```python
# 从圆形线创建面
circle_wire = make_circle_rwire((0, 0, 0), 1.5)
circle_face = make_face_from_wire_rface(circle_wire)
```

### Example 3
```python
# 从多边形线创建面
points = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
poly_wire = make_polyline_rwire(points, closed=True)
poly_face = make_face_from_wire_rface(poly_wire)
```
