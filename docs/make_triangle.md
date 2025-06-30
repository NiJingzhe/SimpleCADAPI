# make_triangle 函数文档

## 定义
```python
def make_triangle(p1: Point, p2: Point, p3: Point) -> Sketch
```

## 作用
通过三个顶点创建三角形草图。自动生成三条边并形成闭合的三角形。

## 参数
- `p1` (Point): 三角形的第一个顶点
- `p2` (Point): 三角形的第二个顶点  
- `p3` (Point): 三角形的第三个顶点

## 返回值
- `Sketch`: 三角形草图对象

## 示例代码

### 基础三角形
```python
from simplecadapi import *

# 创建简单三角形
vertex1 = make_point(0, 0, 0)
vertex2 = make_point(3, 0, 0)
vertex3 = make_point(1.5, 2, 0)

triangle = make_triangle(vertex1, vertex2, vertex3)
```

### 等边三角形
```python
from simplecadapi import *
import math

# 创建等边三角形
side_length = 2.0
height = side_length * math.sqrt(3) / 2

p1 = make_point(-side_length/2, 0, 0)
p2 = make_point(side_length/2, 0, 0)
p3 = make_point(0, height, 0)

equilateral_triangle = make_triangle(p1, p2, p3)
```

### 直角三角形
```python
from simplecadapi import *

# 创建直角三角形
origin = make_point(0, 0, 0)
right_corner = make_point(3, 0, 0)
top_corner = make_point(0, 4, 0)

right_triangle = make_triangle(origin, right_corner, top_corner)
```

### 用于拉伸操作
```python
from simplecadapi import *

# 创建三角形并拉伸成三角柱
p1 = make_point(0, 0, 0)
p2 = make_point(2, 0, 0)
p3 = make_point(1, 1.5, 0)

triangle_sketch = make_triangle(p1, p2, p3)
triangular_prism = extrude(triangle_sketch, distance=1.0)
```

### 在局部坐标系中创建
```python
from simplecadapi import *

# 在倾斜平面中创建三角形
with LocalCoordinateSystem(
    origin=(2, 2, 1),
    x_axis=(1, 0, 0),
    y_axis=(0, 0.707, 0.707)  # 45度倾斜
):
    v1 = make_point(0, 0, 0)
    v2 = make_point(1, 0, 0)
    v3 = make_point(0.5, 1, 0)
    
    tilted_triangle = make_triangle(v1, v2, v3)
```

### 三角形阵列
```python
from simplecadapi import *

# 创建三角形基础形状
base_triangle = make_triangle(
    make_point(0, 0, 0),
    make_point(1, 0, 0),
    make_point(0.5, 0.866, 0)
)

triangle_solid = extrude(base_triangle, distance=0.1)

# 进行线性阵列
triangle_array = make_linear_pattern(
    triangle_solid,
    direction=(2, 0, 0),
    count=5,
    spacing=1.5
)
```

### 用于扫掠截面
```python
from simplecadapi import *

# 三角形截面的扫掠
triangle_profile = make_triangle(
    make_point(0, -0.1, 0),
    make_point(0.15, 0, 0),
    make_point(0, 0.1, 0)
)

# 创建直线路径
path_start = make_point(0, 0, 0)
path_end = make_point(0, 3, 0)
path = make_segement(path_start, path_end)

# 扫掠
triangular_beam = sweep(triangle_profile, path)
```

### 复杂形状的组成部分
```python
from simplecadapi import *

# 使用三角形构建复杂形状
triangles = []

# 创建多个三角形形成类似花瓣的图案
import math
for i in range(6):
    angle = i * math.pi / 3
    center_x = math.cos(angle) * 2
    center_y = math.sin(angle) * 2
    
    p1 = make_point(center_x, center_y, 0)
    p2 = make_point(center_x + 0.5, center_y, 0)
    p3 = make_point(center_x + 0.25, center_y + 0.433, 0)
    
    petal = make_triangle(p1, p2, p3)
    triangles.append(petal)
```

### 三角形到其他形状的放样
```python
from simplecadapi import *

# 三角形到圆形的放样
triangle_base = make_triangle(
    make_point(-1, -0.577, 0),    # 等边三角形
    make_point(1, -0.577, 0),
    make_point(0, 1.155, 0)
)

with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    circle_top = make_circle(1.0)

morphed_shape = loft([triangle_base, circle_top])
```

## 注意事项
- 三个点不能共线，否则无法形成有效的三角形
- 点的顺序决定了三角形的朝向（顺时针或逆时针）
- 三角形在三个点所确定的平面内创建
- 这是手动创建三条边的便捷替代方案
- 返回的是闭合的Sketch对象，可以直接用于3D操作
- 适用于创建结构性形状、装饰元素等
