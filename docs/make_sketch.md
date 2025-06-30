# make_sketch 函数文档

## 定义
```python
def make_sketch(lines: List[Line]) -> Sketch
```

## 作用
将多条线段、圆弧或样条曲线组合成一个闭合的草图对象。草图是2D平面图形，是进行拉伸、旋转等3D建模操作的基础。

## 参数
- `lines` (List[Line]): 构成草图边界的线条列表

## 返回值
- `Sketch`: 闭合草图对象

## 示例代码

### 创建矩形草图
```python
from simplecadapi import *

# 手动创建矩形草图
p1 = make_point(0, 0, 0)
p2 = make_point(2, 0, 0)
p3 = make_point(2, 1, 0)
p4 = make_point(0, 1, 0)

lines = [
    make_segement(p1, p2),
    make_segement(p2, p3),
    make_segement(p3, p4),
    make_segement(p4, p1)
]

rectangle_sketch = make_sketch(lines)
```

### 创建三角形草图
```python
from simplecadapi import *

# 创建三角形
vertex1 = make_point(0, 0, 0)
vertex2 = make_point(3, 0, 0)
vertex3 = make_point(1.5, 2, 0)

triangle_lines = [
    make_segement(vertex1, vertex2),
    make_segement(vertex2, vertex3),
    make_segement(vertex3, vertex1)
]

triangle_sketch = make_sketch(triangle_lines)
```

### L型轮廓（来自comprehensive_test）
```python
from simplecadapi import *

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
```

### 带圆弧的复合形状
```python
from simplecadapi import *
import math

# 创建带圆角的形状
corner1 = make_point(0, 0, 0)
corner2 = make_point(3, 0, 0)
arc_center = make_point(3, 1, 0)
corner3 = make_point(2, 2, 0)
corner4 = make_point(0, 2, 0)

mixed_lines = [
    make_segement(corner1, corner2),                    # 底边
    make_angle_arc(arc_center, 1.0, -math.pi/2, 0),   # 右下圆角
    make_segement(corner3, corner4),                    # 顶边
    make_segement(corner4, corner1)                     # 左边
]

rounded_shape = make_sketch(mixed_lines)
```

### 用于螺旋扫掠的截面
```python
from simplecadapi import *

# 创建螺纹齿形截面（梯形）
thread_points = [
    make_point(0, -0.1, 0),
    make_point(0.2, -0.05, 0),
    make_point(0.2, 0.05, 0),
    make_point(0, 0.1, 0),
]

thread_lines = []
for i in range(len(thread_points)):
    p1 = thread_points[i]
    p2 = thread_points[(i + 1) % len(thread_points)]
    thread_lines.append(make_line([p1, p2], "segment"))

thread_profile = make_sketch(thread_lines)
```

### 复杂的多边形
```python
from simplecadapi import *
import math

# 创建正六边形
def create_hexagon(center_x, center_y, radius):
    points = []
    lines = []
    
    # 生成六边形的顶点
    for i in range(6):
        angle = i * math.pi / 3
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        points.append(make_point(x, y, 0))
    
    # 创建边
    for i in range(6):
        p1 = points[i]
        p2 = points[(i + 1) % 6]
        lines.append(make_segement(p1, p2))
    
    return make_sketch(lines)

hexagon = create_hexagon(0, 0, 2.0)
```

## 注意事项
- 草图应该是闭合的，即所有线条应该首尾相连
- 草图通常在2D平面内，虽然可以包含Z坐标，但建议保持在同一平面
- 草图是进行拉伸、旋转、放样等3D操作的基础
- 线条的顺序很重要，应该按照边界的连续性排列
- 可以混合使用直线段、圆弧和样条曲线
- 草图对象可以转换为CADQuery的wire对象进行进一步操作
