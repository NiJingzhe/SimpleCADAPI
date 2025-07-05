# Point

## 定义
```python
class Point:
    """三维点（存储在局部坐标系中的坐标）"""
    
    def __init__(self, coords: Tuple[float, float, float], cs: CoordinateSystem = WORLD_CS)
```

## 描述

## 方法

Point类表示三维空间中的点，存储在指定的局部坐标系中，支持自动的坐标系转换。

### 参数
- `coords`: 点在局部坐标系中的坐标 (x, y, z)
- `cs`: 局部坐标系，默认为世界坐标系

### 主要属性
- `local_coords`: numpy数组，局部坐标系中的坐标
- `global_coords`: 点在全局坐标系中的坐标（自动计算）
- `cs`: CoordinateSystem对象，该点所属的坐标系

### 主要方法
- `to_cq_vector()`: 转换为CADQuery的Vector对象
- `__repr__()`: 字符串表示，显示局部和全局坐标

## 示例

### 基础点操作
```python
from simplecadapi import *

# 在世界坐标系中创建点
point1 = Point((1, 2, 3))
print(f"局部坐标: {point1.local_coords}")
print(f"全局坐标: {point1.global_coords}")
print(point1)  # Point(local=[1. 2. 3.], global=[1. 2. 3.])
```

### 自定义坐标系中的点
```python
from simplecadapi import *

# 创建自定义坐标系
custom_cs = CoordinateSystem(
    origin=(10, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1)
)

# 在自定义坐标系中创建点
point2 = Point((1, 0, 0), custom_cs)
print(f"局部坐标: {point2.local_coords}")    # [1. 0. 0.]
print(f"全局坐标: {point2.global_coords}")   # [10. 1. 0.]
```

### 批量点操作
```python
from simplecadapi import *

# 创建多个点构成轮廓
points = [
    Point((0, 0, 0)),
    Point((1, 0, 0)),
    Point((1, 1, 0)),
    Point((0, 1, 0))
]

# 输出所有点的坐标
for i, point in enumerate(points):
    print(f"点{i}: 局部{point.local_coords}, 全局{point.global_coords}")

# 使用点创建线段
lines = []
for i in range(len(points)):
    start = points[i]
    end = points[(i + 1) % len(points)]
    line = Line(start, end)
    lines.append(line)
```
