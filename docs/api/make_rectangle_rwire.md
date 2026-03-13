# make_rectangle_rwire

## API Definition

```python
def make_rectangle_rwire(width: float, height: float, center: Tuple[float, float, float] = (0, 0, 0), normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

*Source: operations.py*

## Description

创建矩形并返回线对象

创建矩形线对象，用于构建矩形轮廓。矩形以指定中心点为中心，在指定平面内
创建。可以用于构建复杂的多边形轮廓或作为拉伸的基础轮廓。

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

Wire: 创建的线对象，表示一个封闭的矩形轮廓

## Raises

- **ValueError**: 当宽度或高度小于等于0或其他参数无效时抛出异常

## Examples

### Example 1
```python
# 创建标准矩形轮廓
rect = make_rectangle_rwire(4.0, 3.0)
```

### Example 2
```python
# 创建偏移的矩形
offset_rect = make_rectangle_rwire(2.0, 2.0, (1, 1, 0))
```

### Example 3
```python
# 创建垂直平面上的矩形
vertical_rect = make_rectangle_rwire(3.0, 2.0, (0, 0, 0), (1, 0, 0))
```
