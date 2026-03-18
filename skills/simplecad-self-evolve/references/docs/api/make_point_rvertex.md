# make_point_rvertex

## API Definition

```python
def make_point_rvertex(x: float, y: float, z: float) -> Vertex
```

*Source: operations.py*

## Description

创建三维空间中的点并返回顶点对象

创建三维空间中的几何点，通常用作其他几何对象的构造参数，如作为线段的端点、
圆弧的控制点等。支持当前坐标系变换。

## Parameters

### x

- **Type**: `float`
- **Description**: X坐标值，用于定义点在X轴方向的位置

### y

- **Type**: `float`
- **Description**: Y坐标值，用于定义点在Y轴方向的位置

### z

- **Type**: `float`
- **Description**: Z坐标值，用于定义点在Z轴方向的位置

## Returns

Vertex: 创建的顶点对象，包含指定坐标的点

## Raises

- **ValueError**: 当坐标无效时抛出异常

## Examples

### Example 1
```python
# 创建原点
origin = make_point_rvertex(0, 0, 0)
```

### Example 2
```python
# 创建指定坐标的点
point = make_point_rvertex(1.5, 2.0, 3.0)
```

### Example 3
```python
 # 在工作平面中创建点
 with SimpleWorkplane((1, 1, 1)):
...     local_point = make_point_rvertex(0, 0, 0)  # 实际位置为(1, 1, 1)
```
