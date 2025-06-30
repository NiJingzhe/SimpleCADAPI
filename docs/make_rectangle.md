# make_rectangle 函数文档

## 定义
```python
def make_rectangle(width: float, height: float, center: bool = True) -> Sketch
```

## 作用
创建矩形草图。这是创建矩形的便捷函数，自动生成四个顶点和四条边。

## 参数
- `width` (float): 矩形宽度
- `height` (float): 矩形高度
- `center` (bool): 是否以原点为中心，默认为True

## 返回值
- `Sketch`: 矩形草图对象

## 示例代码

### 中心对齐矩形
```python
from simplecadapi import *

# 创建以原点为中心的矩形
rect_centered = make_rectangle(4.0, 2.0, center=True)
# 顶点位置: (-2,-1,0), (2,-1,0), (2,1,0), (-2,1,0)
```

### 原点对齐矩形
```python
from simplecadapi import *

# 创建以原点为一个角的矩形
rect_origin = make_rectangle(3.0, 2.0, center=False)
# 顶点位置: (0,0,0), (3,0,0), (3,2,0), (0,2,0)
```

### 用于拉伸操作（来自comprehensive_test）
```python
from simplecadapi import *

# 创建矩形并拉伸
rect = make_rectangle(2.0, 1.0, center=True)
extruded_rect = extrude(rect, distance=0.5)
```

### 在不同坐标系中创建
```python
from simplecadapi import *

# 在局部坐标系中创建矩形
with LocalCoordinateSystem(origin=(5, 3, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    local_rect = make_rectangle(2.0, 1.5, center=True)
    # 实际位置会根据局部坐标系变换
```

### 用于放样操作
```python
from simplecadapi import *

# 创建不同大小的矩形在不同高度进行放样
rect1 = make_rectangle(2.0, 2.0, center=True)  # 底层

with LocalCoordinateSystem(origin=(0, 0, 1), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rect2 = make_rectangle(1.5, 1.5, center=True)  # 中层

with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rect3 = make_rectangle(1.0, 1.0, center=True)  # 顶层

lofted = loft([rect1, rect2, rect3])
```

### 创建正方形
```python
from simplecadapi import *

# 创建正方形（特殊的矩形）
square = make_rectangle(3.0, 3.0, center=True)
```

### 批量创建不同尺寸的矩形
```python
from simplecadapi import *

rectangles = []
for i in range(1, 4):
    width = i * 2.0
    height = i * 1.0
    rect = make_rectangle(width, height, center=True)
    rectangles.append(rect)
```

### 用于2D阵列的基础形状
```python
from simplecadapi import *

# 创建基础矩形
base_rect = make_rectangle(1.0, 0.5, center=True)
base_extruded = extrude(base_rect, distance=0.2)

# 进行2D阵列
array_2d = make_2d_pattern(
    base_extruded,
    x_direction=(2, 0, 0),
    y_direction=(0, 2, 0),
    x_count=3,
    y_count=2,
    x_spacing=1.5,
    y_spacing=1.5
)
```

## 注意事项
- 当center=True时，矩形以当前坐标系原点为中心
- 当center=False时，矩形的一个角位于当前坐标系原点
- 返回的是闭合的Sketch对象，可以直接用于拉伸等3D操作
- 矩形在XY平面内创建，Z坐标为0
- 这是手动创建四个点和四条线段的便捷替代方案
