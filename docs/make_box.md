# make_box

## 定义
```python
def make_box(width: float, height: float, depth: float, center: bool = True) -> Body
```

## 描述

直接创建立方体/长方体3D实体。这是创建基础几何体的便捷函数，自动生成带标签的实体。

### 参数
- `width` (float): 盒子在X方向的宽度
- `height` (float): 盒子在Y方向的高度  
- `depth` (float): 盒子在Z方向的深度
- `center` (bool): 是否以当前坐标系原点为中心，默认为True

### 返回值
- `Body`: 立方体/长方体实体，自动添加面标签（"top", "bottom", "front", "back", "left", "right"）

### 特点
- 所有尺寸参数必须为正值
- center=True时，盒子以当前坐标系原点为中心
- center=False时，盒子的一个角位于当前坐标系原点
- 自动添加标准面标签，便于后续操作

## 示例

### 基础盒子创建
```python
from simplecadapi import *

# 正立方体
cube = make_box(2.0, 2.0, 2.0, center=True)

# 长方体
rectangular_box = make_box(4.0, 2.0, 1.0, center=True)

# 薄板
thin_plate = make_box(5.0, 3.0, 0.1, center=True)
```

### 不同对齐方式
```python
from simplecadapi import *

# 中心对齐的盒子
centered_box = make_box(3.0, 2.0, 1.0, center=True)

# 以原点为一个角的盒子
corner_box = make_box(3.0, 2.0, 1.0, center=False)
# 角点位置: (0,0,0) 到 (3,2,1)
```

### 机械零件应用
```python
from simplecadapi import *

# 创建机械底座
machine_base = make_box(8.0, 6.0, 2.0, center=True)

# 添加导轨
with LocalCoordinateSystem(origin=(-3, 0, 2.0)):
    rail1 = make_box(2.0, 6.0, 0.5, center=True)

with LocalCoordinateSystem(origin=(3, 0, 2.0)):
    rail2 = make_box(2.0, 6.0, 0.5, center=True)

# 组装
machine_frame = union(machine_base, rail1)
machine_frame = union(machine_frame, rail2)
```
