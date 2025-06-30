# make_point 函数文档

## 定义
```python
def make_point(x: float, y: float, z: float) -> Point
```

## 作用
在当前坐标系中创建一个三维点。这是创建点的基础函数，返回的点会存储在当前活动的坐标系中。

## 参数
- `x` (float): X坐标值
- `y` (float): Y坐标值 
- `z` (float): Z坐标值

## 返回值
- `Point`: 在当前坐标系中的点对象

## 示例代码

### 基础用法
```python
from simplecadapi import *

# 在世界坐标系中创建点
p1 = make_point(1.0, 2.0, 3.0)
print(f"点坐标: {p1.local_coords}")  # (1.0, 2.0, 3.0)
```

### 在局部坐标系中创建点
```python
from simplecadapi import *

# 在局部坐标系中创建点
with LocalCoordinateSystem(origin=(5, 5, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    p2 = make_point(1.0, 1.0, 0.0)  # 在局部坐标系中的(1,1,0)
    # 实际在世界坐标系中是(6,6,0)
```

### 批量创建点
```python
from simplecadapi import *

# 创建多个点用于构建几何体
points = []
for i in range(4):
    angle = i * math.pi / 2
    x = math.cos(angle)
    y = math.sin(angle)
    points.append(make_point(x, y, 0.0))
```

## 注意事项
- 点的坐标会存储在调用时的当前坐标系中
- 如果在局部坐标系中创建点，该点会自动参与坐标系转换
- 点对象可以用于创建线段、草图等更复杂的几何体
