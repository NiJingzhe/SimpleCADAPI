# sweep 函数文档

## 定义
```python
def sweep(profile: Sketch, path: Line, use_frenet: bool = False) -> Body
```

## 作用
沿指定路径扫掠截面草图，创建3D实体。扫掠可以创建管道、梁、导轨等沿路径延伸的结构。

## 参数
- `profile` (Sketch): 扫掠的截面草图
- `path` (Line): 扫掠路径
- `use_frenet` (bool): 是否使用Frenet框架（用于螺旋扫掠等复杂路径），默认为False

## 返回值
- `Body`: 扫掠后的3D实体

## 示例代码

### 简单直线扫掠（来自comprehensive_test）
```python
from simplecadapi import *

# 在YZ平面创建圆形截面
with LocalCoordinateSystem(origin=(0, 0, 0), 
                         x_axis=(0, 1, 0),
                         y_axis=(0, 0, 1)):
    profile_circle = make_circle(radius=0.2)

# 创建X方向的扫掠路径
path_start = make_point(0, 0, 0)
path_end = make_point(2, 1, 1)
straight_path = make_segement(path_start, path_end)

swept_straight = sweep(profile_circle, straight_path)
```

### 垂直扫掠
```python
from simplecadapi import *

# 在XY平面创建方形截面
square_profile = make_rectangle(0.3, 0.3, center=True)

# 创建Z方向的垂直路径
vertical_start = make_point(0, 0, 0)
vertical_end = make_point(0, 0, 2)
vertical_path = make_segement(vertical_start, vertical_end)

swept_vertical = sweep(square_profile, vertical_path)
```

### 沿曲线扫掠
```python
from simplecadapi import *

# 创建圆形截面
circular_profile = make_circle(0.15)

# 创建弯曲路径（样条曲线）
curve_points = [
    make_point(0, 0, 0),
    make_point(1, 2, 0),
    make_point(3, 1, 1),
    make_point(4, 3, 2)
]
curved_path = make_spline(curve_points)

curved_tube = sweep(circular_profile, curved_path)
```

### 矩形截面管道
```python
from simplecadapi import *

# 创建矩形截面
rect_profile = make_rectangle(0.4, 0.2, center=True)

# 创建U形路径
u_points = [
    make_point(0, 0, 0),
    make_point(0, 2, 0),
    make_point(2, 2, 0),
    make_point(2, 0, 0)
]
u_path = make_spline(u_points)

u_shaped_beam = sweep(rect_profile, u_path)
```

### 椭圆截面扫掠
```python
from simplecadapi import *
import math

# 创建椭圆截面
ellipse_profile = make_ellipse(
    make_point(0, 0, 0),
    major_axis=0.6,
    minor_axis=0.3
)

# 创建螺旋形路径
spiral_points = []
for i in range(20):
    t = i * 0.2
    x = math.cos(t) * 2
    y = math.sin(t) * 2
    z = t * 0.3
    spiral_points.append(make_point(x, y, z))

spiral_path = make_spline(spiral_points)

# 使用Frenet框架确保截面正确定向
spiral_tube = sweep(ellipse_profile, spiral_path, use_frenet=True)
```

### 三角形截面结构梁
```python
from simplecadapi import *

# 创建三角形截面
triangle_profile = make_triangle(
    make_point(0, -0.1, 0),
    make_point(0.15, 0, 0),
    make_point(0, 0.1, 0)
)

# 创建弧形路径
import math
arc_points = []
for i in range(10):
    angle = i * math.pi / 9  # 180度分成9段
    x = 3 * math.cos(angle)
    y = 3 * math.sin(angle)
    z = 0
    arc_points.append(make_point(x, y, z))

arc_path = make_spline(arc_points)

triangular_arch = sweep(triangle_profile, arc_path)
```

### 复杂截面的导轨
```python
from simplecadapi import *

# 创建复杂的导轨截面
rail_points = [
    make_point(-0.2, 0, 0),      # 底部左
    make_point(-0.1, -0.1, 0),   # 底部中左
    make_point(0.1, -0.1, 0),    # 底部中右
    make_point(0.2, 0, 0),       # 底部右
    make_point(0.15, 0.05, 0),   # 侧面右
    make_point(0.05, 0.15, 0),   # 顶部右
    make_point(-0.05, 0.15, 0),  # 顶部左
    make_point(-0.15, 0.05, 0)   # 侧面左
]

rail_lines = []
for i in range(len(rail_points)):
    p1 = rail_points[i]
    p2 = rail_points[(i + 1) % len(rail_points)]
    rail_lines.append(make_segement(p1, p2))

rail_profile = make_sketch(rail_lines)

# 创建铁路弯道路径
track_points = []
for i in range(15):
    angle = i * math.pi / 7  # 约90度弯道
    radius = 10
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    z = 0
    track_points.append(make_point(x, y, z))

track_path = make_spline(track_points)

railway_track = sweep(rail_profile, track_path)
```

### 管道系统扫掠
```python
from simplecadapi import *

# 创建圆形管道截面
pipe_profile = make_circle(0.1)

# 创建复杂的管道路径（L形转弯）
pipe_segments = []

# 水平段
horizontal_start = make_point(0, 0, 0)
horizontal_end = make_point(2, 0, 0)
horizontal_path = make_segement(horizontal_start, horizontal_end)

# 弯曲段（90度弯头）
bend_points = []
for i in range(5):
    angle = i * math.pi / 8  # 90度分成4段
    x = 2 + 0.3 * math.sin(angle)
    y = 0.3 * (1 - math.cos(angle))
    z = 0
    bend_points.append(make_point(x, y, z))

bend_path = make_spline(bend_points)

# 垂直段
vertical_start = bend_points[-1]
vertical_end = make_point(vertical_start.local_coords[0], 2, 0)
vertical_path = make_segement(vertical_start, vertical_end)

# 分别扫掠各段
horizontal_pipe = sweep(pipe_profile, horizontal_path)
bend_pipe = sweep(pipe_profile, bend_path)
vertical_pipe = sweep(pipe_profile, vertical_path)

# 合并管道系统
pipe_system = union(horizontal_pipe, bend_pipe)
pipe_system = union(pipe_system, vertical_pipe)
```

### 渐变截面扫掠
```python
from simplecadapi import *

# 注意：这个例子展示概念，实际需要multiple profiles
# 创建基础圆形截面
base_profile = make_circle(0.2)

# 创建锥形路径（虽然sweep不直接支持变截面，
# 但可以通过组合多个短段sweep实现）
taper_start = make_point(0, 0, 0)
taper_end = make_point(0, 0, 2)
taper_path = make_segement(taper_start, taper_end)

# 基础扫掠（等截面）
constant_section = sweep(base_profile, taper_path)

# 实际渐变截面需要使用loft操作
# 底部大圆
bottom_circle = make_circle(0.3)

# 顶部小圆
with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    top_circle = make_circle(0.1)

tapered_cone = loft([bottom_circle, top_circle])
```

## 注意事项
- 截面草图应该垂直于扫掠路径的起始方向
- 对于复杂路径（如螺旋），建议使用`use_frenet=True`
- 扫掠路径可以是直线、圆弧或样条曲线
- 截面在扫掠过程中保持形状不变（等截面扫掠）
- 如需变截面，应该使用loft操作
- 适用于创建管道、梁、导轨、电缆等线性结构
- 路径过于复杂可能导致自相交，需要注意路径设计
