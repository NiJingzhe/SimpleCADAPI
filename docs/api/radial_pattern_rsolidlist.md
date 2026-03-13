# radial_pattern_rsolidlist

## API Definition

```python
def radial_pattern_rsolidlist(shape: AnyShape, center: Tuple[float, float, float], axis: Tuple[float, float, float], count: int, total_rotation_angle: float) -> List[Solid]
```

*Source: operations.py*

## Description

创建径向阵列（圆形阵列）

围绕指定轴创建几何体的径向阵列，生成等角度间隔的旋转排列。
常用于创建齿轮、花瓣、螺栓圆形分布等对称结构。

## Parameters

### shape

- **Type**: `AnyShape`
- **Description**: 要阵列的几何体，可以是任意类型的几何对象

### center

- **Type**: `Tuple[float, float, float]`
- **Description**: 旋转中心点坐标 (x, y, z)

### axis

- **Type**: `Tuple[float, float, float]`
- **Description**: 旋转轴向量 (x, y, z)，定义旋转轴方向

### count

- **Type**: `int`
- **Description**: 阵列数量，必须为正整数，包括原始对象

### total_rotation_angle

- **Type**: `float`
- **Description**: 总旋转角度，单位为度数（0-360）， 定义整个阵列的角度范围

## Returns

List[Solid]: 径向阵列后的几何体列表，包含原始对象和所有旋转的对象

## Raises

- **ValueError**: 当阵列数量小于等于0或角度无效时抛出异常

## Examples

### Example 1
```python
# 创建立方体的径向阵列（6个，360度）
box = make_box_rsolid(1, 0.5, 0.5, (2, 0, 0))  # 距离中心2单位
radial_boxes = radial_pattern_rsolidlist(box, (0, 0, 0), (0, 0, 1), 6, 360)
```

### Example 2
```python
# 创建半圆阵列
cylinder = make_cylinder_rsolid(0.3, 1.0, (1.5, 0, 0))
half_circle = radial_pattern_rsolidlist(cylinder, (0, 0, 0), (0, 0, 1), 4, 180)
```

### Example 3
```python
# 围绕Y轴的径向阵列
element = make_sphere_rsolid(0.5, (3, 0, 0))
vertical_array = radial_pattern_rsolidlist(element, (0, 0, 0), (0, 1, 0), 8, 360)
```
