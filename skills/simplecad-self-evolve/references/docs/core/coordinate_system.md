# CoordinateSystem 坐标系

## 概述

`CoordinateSystem` 是 SimpleCAD API 中的三维坐标系类，用于定义和管理三维空间中的坐标系。SimpleCAD 使用 Z 向上的右手坐标系，原点在 (0, 0, 0)，X 轴向前，Y 轴向右，Z 轴向上。

## 类定义

```python
class CoordinateSystem:
    """三维坐标系
    
    SimpleCAD使用Z向上的右手坐标系，原点在(0, 0, 0)，X轴向前，Y轴向右，Z轴向上
    """
```

## 用途

- 定义局部坐标系
- 坐标转换（局部坐标到全局坐标）
- 与 CADQuery 坐标系的转换
- 几何变换的基础

## 构造函数

### `__init__(origin, x_axis, y_axis)`

初始化坐标系。

**参数:**
- `origin` (Tuple[float, float, float], 可选): 坐标系原点，默认 (0, 0, 0)
- `x_axis` (Tuple[float, float, float], 可选): X轴方向向量，默认 (1, 0, 0)
- `y_axis` (Tuple[float, float, float], 可选): Y轴方向向量，默认 (0, 1, 0)

**异常:**
- `ValueError`: 当输入的坐标或方向向量无效时抛出

**示例:**
```python
from simplecadapi import CoordinateSystem

# 默认坐标系（世界坐标系）
world_cs = CoordinateSystem()

# 自定义坐标系
custom_cs = CoordinateSystem(
    origin=(1, 2, 3),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0)
)

# 旋转的坐标系
rotated_cs = CoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0.707, 0.707, 0),  # 绕Z轴旋转45度
    y_axis=(-0.707, 0.707, 0)
)
```

## 主要属性

- `origin`: 坐标系原点 (numpy.ndarray)
- `x_axis`: X轴方向向量 (numpy.ndarray)
- `y_axis`: Y轴方向向量 (numpy.ndarray)
- `z_axis`: Z轴方向向量 (numpy.ndarray，自动计算)

## 常用方法

### `transform_point(point)`

将局部坐标转换为全局坐标。

**参数:**
- `point` (numpy.ndarray): 局部坐标点

**返回:**
- `numpy.ndarray`: 全局坐标点

**示例:**
```python
import numpy as np
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(origin=(1, 0, 0))
local_point = np.array([1, 0, 0])
global_point = cs.transform_point(local_point)
print(global_point)  # [2. 0. 0.]
```

### `transform_vector(vector)`

将局部方向向量转换为全局方向向量（不包含平移）。

**参数:**
- `vector` (numpy.ndarray): 局部方向向量

**返回:**
- `numpy.ndarray`: 全局方向向量

**示例:**
```python
import numpy as np
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),  # X轴指向Y方向
    y_axis=(1, 0, 0)   # Y轴指向X方向
)

local_vector = np.array([1, 0, 0])  # 局部X方向
global_vector = cs.transform_vector(local_vector)
print(global_vector)  # [0. 1. 0.] (全局Y方向)
```

### `to_cq_plane()`

转换为 CADQuery 的 Plane 对象。

**返回:**
- `cadquery.Plane`: CADQuery 平面对象

**示例:**
```python
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(origin=(0, 0, 1))
cq_plane = cs.to_cq_plane()
```

## 坐标系转换

SimpleCAD 使用 Z 向上坐标系，而 CADQuery 使用 Y 向上坐标系。转换规则为：

- SimpleCAD 的 X 轴（前）→ CADQuery 的 Z 轴（前）
- SimpleCAD 的 Y 轴（右）→ CADQuery 的 X 轴（右）
- SimpleCAD 的 Z 轴（上）→ CADQuery 的 Y 轴（上）

## 全局坐标系

SimpleCAD 提供了一个全局世界坐标系：

```python
from simplecadapi import WORLD_CS

print(WORLD_CS.origin)  # [0. 0. 0.]
print(WORLD_CS.x_axis)  # [1. 0. 0.]
print(WORLD_CS.y_axis)  # [0. 1. 0.]
print(WORLD_CS.z_axis)  # [0. 0. 1.]
```

## 字符串表示

```python
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(origin=(1, 2, 3))
print(cs)
```

输出：
```
CoordinateSystem:
  origin: [1.000, 2.000, 3.000]
  x_axis: [1.000, 0.000, 0.000]
  y_axis: [0.000, 1.000, 0.000]
  z_axis: [0.000, 0.000, 1.000]
```

## 注意事项

- 输入的方向向量会自动归一化
- Z 轴通过 X 轴和 Y 轴的叉积自动计算
- 如果输入零向量，会抛出 ValueError
- 坐标系应保持右手系的特性
