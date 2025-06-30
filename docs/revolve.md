# revolve 函数文档

## 定义
```python
def revolve(sketch: Sketch, axis_start: Point, axis_end: Point, angle: float) -> Body
```

## 作用
将2D草图绕指定轴旋转指定角度，创建回转体。适用于创建圆形对称的物体，如瓶子、轴承、法兰等。

## 参数
- `sketch` (Sketch): 要旋转的2D草图轮廓
- `axis_start` (Point): 旋转轴的起点
- `axis_end` (Point): 旋转轴的终点
- `angle` (float): 旋转角度（弧度）

## 返回值
- `Body`: 旋转后的3D实体

## 示例代码

### L型轮廓旋转（来自comprehensive_test）
```python
from simplecadapi import *
import math

# 创建L型轮廓进行旋转
p1 = make_point(0.5, 0, 0)
p2 = make_point(1.0, 0, 0)
p3 = make_point(1.0, 0, 0.5)
p4 = make_point(0.8, 0, 0.5)
p5 = make_point(0.8, 0, 0.2)
p6 = make_point(0.5, 0, 0.2)

lines = [
    make_line([p1, p2], "segment"),
    make_line([p2, p3], "segment"),
    make_line([p3, p4], "segment"),
    make_line([p4, p5], "segment"),
    make_line([p5, p6], "segment"),
    make_line([p6, p1], "segment")
]

l_profile = make_sketch(lines)

# 绕Z轴旋转创建回转体
axis_start = make_point(0, 0, -1)
axis_end = make_point(0, 0, 1)
revolved = revolve(l_profile, axis_start, axis_end, 2 * math.pi)
```

### 部分旋转（180度）
```python
from simplecadapi import *
import math

# 创建半圆回转体
l_profile = make_sketch(lines)  # 使用上面的L型轮廓
half_revolved = revolve(l_profile, axis_start, axis_end, math.pi)
```

### 花瓶轮廓旋转
```python
from simplecadapi import *
import math

# 创建花瓶轮廓
vase_points = [
    make_point(0.2, 0, 0),    # 底部内径
    make_point(1.0, 0, 0),    # 底部外径
    make_point(0.8, 0, 0.5),  # 收腰
    make_point(1.2, 0, 2.0),  # 腹部
    make_point(0.6, 0, 3.0),  # 颈部
    make_point(0.8, 0, 3.5),  # 瓶口
    make_point(0.3, 0, 3.5),  # 瓶口内径
    make_point(0.3, 0, 0.1),  # 内壁
    make_point(0.2, 0, 0.1)   # 底部连接
]

vase_lines = []
for i in range(len(vase_points) - 1):
    vase_lines.append(make_segement(vase_points[i], vase_points[i + 1]))
vase_lines.append(make_segement(vase_points[-1], vase_points[0]))  # 闭合

vase_profile = make_sketch(vase_lines)

# 绕Z轴完全旋转
vase_axis_start = make_point(0, 0, 0)
vase_axis_end = make_point(0, 0, 4)
vase = revolve(vase_profile, vase_axis_start, vase_axis_end, 2 * math.pi)
```

### 轴承套圈
```python
from simplecadapi import *
import math

# 创建轴承内圈轮廓
bearing_points = [
    make_point(1.0, 0, 0),     # 内径
    make_point(1.5, 0, 0),     # 外径底部
    make_point(1.5, 0, 0.3),   # 外径顶部
    make_point(1.0, 0, 0.3),   # 内径顶部
]

bearing_lines = [
    make_segement(bearing_points[0], bearing_points[1]),
    make_segement(bearing_points[1], bearing_points[2]),
    make_segement(bearing_points[2], bearing_points[3]),
    make_segement(bearing_points[3], bearing_points[0])
]

bearing_profile = make_sketch(bearing_lines)

# 绕Z轴旋转
bearing_axis_start = make_point(0, 0, -0.1)
bearing_axis_end = make_point(0, 0, 0.4)
bearing_ring = revolve(bearing_profile, bearing_axis_start, bearing_axis_end, 2 * math.pi)
```

### 绕不同轴旋转
```python
from simplecadapi import *
import math

# 创建简单矩形轮廓
rect_profile = make_rectangle(0.5, 1.0, center=False)

# 绕Y轴旋转（水平轴）
y_axis_start = make_point(0, -1, 0)
y_axis_end = make_point(0, 1, 0)
horizontal_revolved = revolve(rect_profile, y_axis_start, y_axis_end, math.pi)

# 绕X轴旋转
x_axis_start = make_point(-1, 0, 0)
x_axis_end = make_point(1, 0, 0)
x_revolved = revolve(rect_profile, x_axis_start, x_axis_end, 2 * math.pi)
```

### 部分角度的扇形
```python
from simplecadapi import *
import math

# 创建扇形轮廓
sector_points = [
    make_point(0.5, 0, 0),
    make_point(2.0, 0, 0),
    make_point(2.0, 0, 1.0),
    make_point(0.5, 0, 1.0)
]

sector_lines = [
    make_segement(sector_points[0], sector_points[1]),
    make_segement(sector_points[1], sector_points[2]),
    make_segement(sector_points[2], sector_points[3]),
    make_segement(sector_points[3], sector_points[0])
]

sector_profile = make_sketch(sector_lines)

# 旋转60度创建扇形
axis_start = make_point(0, 0, 0)
axis_end = make_point(0, 0, 1)
sector_60 = revolve(sector_profile, axis_start, axis_end, math.pi / 3)  # 60度
```

### 复杂轮廓的旋转
```python
from simplecadapi import *
import math

# 使用样条曲线创建平滑轮廓
smooth_points = [
    make_point(0.3, 0, 0),
    make_point(1.0, 0, 0.2),
    make_point(1.2, 0, 1.0),
    make_point(0.8, 0, 2.0),
    make_point(0.4, 0, 2.2),
    make_point(0.3, 0, 2.2),
    make_point(0.3, 0, 0.1)
]

smooth_outline = make_spline(smooth_points[:-1])  # 除最后一个点
bottom_line = make_segement(smooth_points[-2], smooth_points[-1])
side_line = make_segement(smooth_points[-1], smooth_points[0])

smooth_profile = make_sketch([smooth_outline, bottom_line, side_line])

# 旋转创建平滑的回转体
smooth_revolved = revolve(
    smooth_profile, 
    make_point(0, 0, 0), 
    make_point(0, 0, 2.5), 
    2 * math.pi
)
```

## 注意事项
- 草图轮廓不应该与旋转轴相交（除了端点），否则会产生自相交
- angle使用弧度制，2π为完整旋转，π为半圈
- 旋转轴由两个点定义，方向为从axis_start到axis_end
- 适用于创建圆形对称的物体：瓶子、轴、轴承、法兰等
- 轮廓应该在旋转轴的一侧，通常在XZ平面或YZ平面内
- 可以创建部分旋转体（扇形、楔形）或完整的回转体
