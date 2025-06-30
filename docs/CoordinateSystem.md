# CoordinateSystem 类文档

## 概述
CoordinateSystem类表示三维右手坐标系，用于定义空间中的位置和方向。它是SimpleCAD API中所有几何操作的基础。

## 类定义
```python
class CoordinateSystem:
    """三维坐标系（右手系）"""
```

## 构造函数
```python
def __init__(self, 
             origin: Tuple[float, float, float] = (0, 0, 0),
             x_axis: Tuple[float, float, float] = (1, 0, 0),
             y_axis: Tuple[float, float, float] = (0, 1, 0))
```

### 参数
- `origin`: 坐标系原点，默认为 (0, 0, 0)
- `x_axis`: X轴方向向量，默认为 (1, 0, 0)
- `y_axis`: Y轴方向向量，默认为 (0, 1, 0)

### 说明
- Z轴通过X轴和Y轴的叉积自动计算，确保形成右手坐标系
- 输入的轴向量会自动归一化

## 属性
- `origin`: numpy数组，坐标系原点
- `x_axis`: numpy数组，归一化的X轴方向
- `y_axis`: numpy数组，归一化的Y轴方向  
- `z_axis`: numpy数组，归一化的Z轴方向（通过叉积计算）

## 方法

### _normalize(vector) -> np.ndarray
归一化输入向量
- **参数**: `vector` - 需要归一化的向量
- **返回**: 归一化后的numpy数组
- **异常**: 如果输入为零向量则抛出ValueError

### transform_point(point: np.ndarray) -> np.ndarray
将局部坐标转换为全局坐标
- **参数**: `point` - 局部坐标系中的点
- **返回**: 全局坐标系中对应的点

### to_cq_plane() -> Plane
转换为CADQuery的Plane对象
- **返回**: CADQuery Plane对象，用于与CADQuery库的互操作

## 使用示例

### 创建默认坐标系
```python
from simplecadapi.core import CoordinateSystem

# 创建世界坐标系
world_cs = CoordinateSystem()
print(f"原点: {world_cs.origin}")
print(f"X轴: {world_cs.x_axis}")
print(f"Y轴: {world_cs.y_axis}")
print(f"Z轴: {world_cs.z_axis}")
```

### 创建自定义坐标系
```python
# 创建平移和旋转的坐标系
custom_cs = CoordinateSystem(
    origin=(5, 5, 0),           # 原点平移到(5,5,0)
    x_axis=(0, 1, 0),           # X轴指向原Y轴方向
    y_axis=(-1, 0, 0)           # Y轴指向原X轴负方向
)
```

### 坐标转换
```python
import numpy as np

# 在自定义坐标系中的点(1, 0, 0)
local_point = np.array([1, 0, 0])

# 转换到全局坐标系
global_point = custom_cs.transform_point(local_point)
print(f"局部坐标 {local_point} 对应的全局坐标: {global_point}")
```

### 与CADQuery集成
```python
import cadquery as cq

# 获取CADQuery平面对象
cq_plane = custom_cs.to_cq_plane()

# 在该平面上创建工作平面
workplane = cq.Workplane(cq_plane)
```

## 注意事项
1. 坐标系必须满足右手定则
2. 输入的轴向量不必归一化，构造函数会自动处理
3. X轴和Y轴不必垂直，但不能平行，Z轴通过叉积确保垂直性
4. 该类与CADQuery库紧密集成，支持无缝转换
