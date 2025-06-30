# Point 类文档

## 概述
Point类表示三维空间中的点，存储在指定的局部坐标系中，支持自动的坐标系转换。

## 类定义
```python
class Point:
    """三维点（存储在局部坐标系中的坐标）"""
```

## 构造函数
```python
def __init__(self, coords: Tuple[float, float, float], cs: CoordinateSystem = WORLD_CS)
```

### 参数
- `coords`: 点在局部坐标系中的坐标 (x, y, z)
- `cs`: 局部坐标系，默认为世界坐标系

## 属性
- `local_coords`: numpy数组，局部坐标系中的坐标
- `cs`: CoordinateSystem对象，该点所属的坐标系

## 属性方法

### global_coords -> np.ndarray
获取点在全局坐标系中的坐标
- **返回**: numpy数组，全局坐标

## 方法

### to_cq_vector() -> Vector
转换为CADQuery的Vector对象（使用全局坐标）
- **返回**: CADQuery Vector对象

### __repr__() -> str
字符串表示
- **返回**: 包含局部和全局坐标的字符串

## 使用示例

### 创建世界坐标系中的点
```python
from simplecadapi.core import Point

# 在世界坐标系中创建点
point1 = Point((1, 2, 3))
print(f"局部坐标: {point1.local_coords}")
print(f"全局坐标: {point1.global_coords}")
print(point1)  # Point(local=[1. 2. 3.], global=[1. 2. 3.])
```

### 创建自定义坐标系中的点
```python
from simplecadapi.core import Point, CoordinateSystem

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

### 与CADQuery集成
```python
import cadquery as cq

# 转换为CADQuery向量
point = Point((5, 5, 5))
cq_vector = point.to_cq_vector()

# 在CADQuery中使用
workplane = cq.Workplane()
# 可以使用cq_vector进行各种CADQuery操作
```

### 批量创建点
```python
# 创建多个点
points = [
    Point((0, 0, 0)),
    Point((1, 0, 0)),
    Point((1, 1, 0)),
    Point((0, 1, 0))
]

# 输出所有点的坐标
for i, point in enumerate(points):
    print(f"点{i}: 局部{point.local_coords}, 全局{point.global_coords}")
```

### 不同坐标系间的点比较
```python
# 世界坐标系中的点
world_point = Point((1, 0, 0))

# 平移坐标系中的点  
translated_cs = CoordinateSystem(origin=(1, 0, 0))
local_point = Point((0, 0, 0), translated_cs)

print(f"世界坐标系点: {world_point.global_coords}")
print(f"平移坐标系点: {local_point.global_coords}")
# 两个点在全局坐标系中位置相同
```

## 注意事项
1. 点的局部坐标在创建后不可修改
2. 全局坐标通过坐标系转换自动计算
3. 与CADQuery的Vector对象可以无缝转换
4. 适用于所有需要精确位置表示的几何操作
