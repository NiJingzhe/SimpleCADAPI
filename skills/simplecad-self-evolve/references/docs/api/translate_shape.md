# translate_shape

## API Definition

```python
def translate_shape(shape: AnyShape, vector: Tuple[float, float, float]) -> AnyShape
```

*Source: operations.py*

## Description

平移几何体到新位置

将几何体从当前位置平移到新位置，不改变几何体的形状和大小。
平移操作支持当前坐标系变换，适用于所有类型的几何对象。

## Parameters

### shape

- **Type**: `AnyShape`
- **Description**: 要平移的几何体，可以是点、边、线、面、实体等任意几何对象

### vector

- **Type**: `Tuple[float, float, float]`
- **Description**: 平移向量 (dx, dy, dz)， 定义在X、Y、Z方向上的平移距离

## Returns

AnyShape: 平移后的几何体，类型与输入相同

## Raises

- **ValueError**: 当几何体或平移向量无效时抛出异常

## Examples

### Example 1
```python
# 平移立方体
box = make_box_rsolid(2, 2, 2)
moved_box = translate_shape(box, (5, 0, 0))  # 沿X轴移动5个单位
```

### Example 2
```python
# 平移圆形面
circle = make_circle_rface((0, 0, 0), 1.0)
moved_circle = translate_shape(circle, (1, 1, 2))
```

### Example 3
```python
# 平移线段
line = make_line_redge((0, 0, 0), (1, 0, 0))
moved_line = translate_shape(line, (0, 3, 0))
```
