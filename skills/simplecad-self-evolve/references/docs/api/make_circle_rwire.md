# make_circle_rwire

## API Definition

```python
def make_circle_rwire(center: Tuple[float, float, float], radius: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

*Source: operations.py*

## Description

创建圆形并返回线对象

创建圆形线对象，用于构建封闭的圆形轮廓。与make_circle_redge不同，
此函数返回的是线对象，可以直接用于创建面或进行其他线操作。

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

Wire: 创建的线对象，表示一个完整的圆形轮廓

## Raises

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常

## Examples

### Example 1
```python
# 创建标准圆形轮廓
circle_wire = make_circle_rwire((0, 0, 0), 3.0)
```

### Example 2
```python
# 创建小圆轮廓
small_circle = make_circle_rwire((1, 1, 0), 0.5)
```
