# loft 函数文档

## 定义
```python
def loft(sketches: List[Sketch]) -> Body
```

## 作用
通过多个截面草图进行放样，创建平滑过渡的3D实体。放样在不同截面之间创建平滑的表面连接，适用于复杂的有机形状。

## 参数
- `sketches` (List[Sketch]): 放样的截面草图列表（至少需要2个）

## 返回值
- `Body`: 放样后的3D实体

## 示例代码

### 分层矩形放样（来自comprehensive_test）
```python
from simplecadapi import *

# 创建不同大小的矩形在不同高度进行放样
# 底层 - 大矩形 (z=0)
rect1 = make_rectangle(2.0, 2.0, center=True)

# 中层 - 中矩形 (z=1)
with LocalCoordinateSystem(origin=(0, 0, 1), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rect2 = make_rectangle(1.5, 1.5, center=True)

# 顶层 - 小矩形 (z=2)
with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rect3 = make_rectangle(1.0, 1.0, center=True)

lofted = loft([rect1, rect2, rect3])
```

### 圆形到矩形的放样
```python
from simplecadapi import *

# 底层圆形 (z=0)
circle = make_circle(1.0)

# 顶层矩形 (z=1.5)
with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    square = make_rectangle(2.0, 2.0, center=True)

circle_to_square = loft([circle, square])
```

### 复杂形状变形
```python
from simplecadapi import *
import math

# 三角形到六边形的放样
# 底层三角形
triangle = make_triangle(
    make_point(-1, -0.577, 0),
    make_point(1, -0.577, 0),
    make_point(0, 1.155, 0)
)

# 顶层六边形
with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    hex_points = []
    for i in range(6):
        angle = i * math.pi / 3
        x = math.cos(angle)
        y = math.sin(angle)
        hex_points.append(make_point(x, y, 0))
    
    hex_lines = []
    for i in range(6):
        p1 = hex_points[i]
        p2 = hex_points[(i + 1) % 6]
        hex_lines.append(make_segement(p1, p2))
    
    hexagon = make_sketch(hex_lines)

triangle_to_hex = loft([triangle, hexagon])
```

### 飞机机翼式放样
```python
from simplecadapi import *

# 翼根截面（大的椭圆）
root_section = make_ellipse(
    make_point(0, 0, 0),
    major_axis=2.0,
    minor_axis=0.6
)

# 中间截面
with LocalCoordinateSystem(origin=(0, 2, 0.3), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    mid_section = make_ellipse(
        make_point(0, 0, 0),
        major_axis=1.5,
        minor_axis=0.4
    )

# 翼尖截面（小的椭圆）
with LocalCoordinateSystem(origin=(0, 4, 0.8), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    tip_section = make_ellipse(
        make_point(0, 0, 0),
        major_axis=0.8,
        minor_axis=0.2
    )

wing = loft([root_section, mid_section, tip_section])
```

### 瓶子形状放样
```python
from simplecadapi import *

# 瓶底（圆形）
bottom = make_circle(1.5)

# 瓶身（椭圆）
with LocalCoordinateSystem(origin=(0, 0, 1), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    body_section = make_ellipse(
        make_point(0, 0, 0),
        major_axis=2.0,
        minor_axis=1.8
    )

# 瓶肩（小椭圆）
with LocalCoordinateSystem(origin=(0, 0, 2.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    shoulder = make_ellipse(
        make_point(0, 0, 0),
        major_axis=1.2,
        minor_axis=1.0
    )

# 瓶颈（小圆）
with LocalCoordinateSystem(origin=(0, 0, 3.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    neck = make_circle(0.4)

bottle = loft([bottom, body_section, shoulder, neck])
```

### 螺旋式渐变放样
```python
from simplecadapi import *
import math

# 创建旋转渐变的放样
sections = []
num_sections = 5

for i in range(num_sections):
    height = i * 0.5
    rotation = i * math.pi / 6  # 每层旋转30度
    scale = 1.0 - i * 0.15      # 每层缩小15%
    
    with LocalCoordinateSystem(
        origin=(0, 0, height),
        x_axis=(math.cos(rotation), math.sin(rotation), 0),
        y_axis=(-math.sin(rotation), math.cos(rotation), 0)
    ):
        section = make_rectangle(2.0 * scale, 1.0 * scale, center=True)
        sections.append(section)

twisted_tower = loft(sections)
```

### 船体形状放样
```python
from simplecadapi import *

# 船体横截面放样
# 船底（尖的椭圆）
keel = make_ellipse(
    make_point(0, 0, 0),
    major_axis=0.2,
    minor_axis=1.0
)

# 水线处（宽椭圆）
with LocalCoordinateSystem(origin=(0, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    waterline = make_ellipse(
        make_point(0, 0, 0),
        major_axis=2.0,
        minor_axis=4.0
    )

# 甲板线（矩形）
with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    deck = make_rectangle(1.8, 3.5, center=True)

hull = loft([keel, waterline, deck])
```

### 多段式复杂放样
```python
from simplecadapi import *

# 创建多个中间截面的复杂放样
base_circle = make_circle(1.0)

sections = [base_circle]

# 添加多个中间截面
heights = [0.5, 1.0, 1.5, 2.0, 2.5]
shapes = ['ellipse', 'rectangle', 'triangle', 'circle', 'ellipse']
sizes = [1.2, 1.4, 1.0, 0.8, 0.4]

for i, (height, shape, size) in enumerate(zip(heights, shapes, sizes)):
    with LocalCoordinateSystem(origin=(0, 0, height), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        if shape == 'circle':
            section = make_circle(size)
        elif shape == 'ellipse':
            section = make_ellipse(make_point(0, 0, 0), size * 1.5, size)
        elif shape == 'rectangle':
            section = make_rectangle(size * 2, size, center=True)
        elif shape == 'triangle':
            section = make_triangle(
                make_point(-size, -size*0.577, 0),
                make_point(size, -size*0.577, 0),
                make_point(0, size*1.155, 0)
            )
        sections.append(section)

complex_loft = loft(sections)
```

## 注意事项
- 至少需要2个截面草图才能进行放样
- 截面草图应该在不同的平面上，通常在不同的Z高度
- 截面的形状可以完全不同（圆形→方形→三角形等）
- 截面的大小可以变化，创建锥形或扩张效果
- 放样会在截面之间创建平滑的过渡表面
- 适用于复杂的有机形状、机翼、船体、瓶子等
- 截面的点数和排列顺序会影响放样结果的质量
