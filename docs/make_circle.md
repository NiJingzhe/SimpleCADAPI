# make_circle 函数文档

## 定义
```python
def make_circle(radius: float, center_point: Optional[Point] = None) -> Sketch
```

## 作用
创建圆形草图。使用多边形（默认16边形）近似圆形，提供足够的精度用于大多数CAD应用。

## 参数
- `radius` (float): 圆的半径
- `center_point` (Optional[Point]): 圆心位置，默认为当前坐标系原点

## 返回值
- `Sketch`: 圆形草图对象

## 示例代码

### 基础圆形
```python
from simplecadapi import *

# 在原点创建圆
circle = make_circle(radius=1.5)
```

### 指定圆心的圆形
```python
from simplecadapi import *

# 在指定位置创建圆
center = make_point(2, 3, 0)
circle_offset = make_circle(radius=1.0, center_point=center)
```

### 用于拉伸操作（来自comprehensive_test）
```python
from simplecadapi import *

# 创建圆形并拉伸成圆柱
circle = make_circle(0.5)
extruded_circle = extrude(circle, distance=1.0)
```

### 用于放样操作
```python
from simplecadapi import *

# 圆形到矩形的放样
circle = make_circle(1.0)  # 底层圆形

with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    square = make_rectangle(2.0, 2.0, center=True)  # 顶层方形

circle_to_square = loft([circle, square])
```

### 用于扫掠操作的截面
```python
from simplecadapi import *

# 创建圆形截面进行扫掠
profile_circle = make_circle(radius=0.2)

# 创建扫掠路径
path_start = make_point(0, 0, 0)
path_end = make_point(2, 1, 1)
path = make_segement(path_start, path_end)

# 进行扫掠
swept_tube = sweep(profile_circle, path)
```

### 螺旋扫掠的截面
```python
from simplecadapi import *

# 创建圆形截面进行螺旋扫掠
circle_profile = make_circle(radius=0.15)

spring = helical_sweep(
    profile=circle_profile,
    coil_radius=1.0,
    pitch=0.8,
    turns=3.0
)
```

### 不同坐标系中的圆形
```python
from simplecadapi import *

# 在倾斜平面中创建圆形
with LocalCoordinateSystem(
    origin=(0, 0, 1), 
    x_axis=(1, 0, 0), 
    y_axis=(0, 0.707, 0.707)  # 45度倾斜
):
    tilted_circle = make_circle(radius=1.0)
```

### 创建多个同心圆
```python
from simplecadapi import *

# 创建同心圆系列
circles = []
center = make_point(0, 0, 0)

for i in range(1, 4):
    radius = i * 0.5
    circle = make_circle(radius, center)
    circles.append(circle)
```

### 用于布尔运算
```python
from simplecadapi import *

# 创建圆形进行布尔运算
large_circle = make_circle(2.0)
large_cylinder = extrude(large_circle, distance=1.0)

small_circle = make_circle(0.5)
small_cylinder = extrude(small_circle, distance=1.2)

# 布尔减运算创建空心圆柱
hollow_cylinder = cut(large_cylinder, small_cylinder)
```

## 注意事项
- 圆形使用16边形近似，对大多数应用足够精确
- 如果需要更高精度，可以考虑使用CADQuery的原生圆形函数
- 圆形在XY平面内创建，Z坐标为0
- 如果不指定center_point，圆心位于当前坐标系的原点
- 返回的是闭合的Sketch对象，可以直接用于3D操作
- 半径必须为正值
