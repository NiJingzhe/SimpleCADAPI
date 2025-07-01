# helical_sweep

## 语法
```python
helical_sweep(
    profile: Sketch,
    coil_radius: float,
    pitch: float,
    turns: float,
    points_per_turn: int = 12,
    smooth: bool = True,
) -> Body
```

## 描述
创建螺旋扫掠实体。该函数将二维截面沿螺旋路径扫掠，生成螺旋弹簧、螺纹、螺旋管道等复杂的三维几何体。支持可调节的精度和平滑选项。

## 参数
- **profile** (Sketch): 扫掠的截面草图（**必须在特定的LocalCoordinateSystem中构建**）
- **coil_radius** (float): 螺旋半径（从中心轴到螺旋路径的距离）
- **pitch** (float): 螺距（每圈沿轴方向上升的距离）
- **turns** (float): 圈数（可以是小数，如2.5圈）
- **points_per_turn** (int, optional): 每圈的点数，控制精度（6-32）。默认值：12
- **smooth** (bool, optional): 是否使用样条曲线平滑路径。默认值：True

## 重要要求：Profile坐标系

**profile截面草图必须在特定的LocalCoordinateSystem中构建：**

```python
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1),
):
    # 在此坐标系中创建profile
    profile = make_circle(radius=0.1)
    # 或其他截面形状
```

- **x_axis** 必须是 `(0, 1, 0)`
- **y_axis** 必须是 `(0, 0, 1)`
- **origin** 通常是 `(0, 0, 0)`

这个坐标系要求确保profile截面的方向正确，以便沿螺旋路径正确扫掠。

## 返回值
- **Body**: 螺旋扫掠生成的实体对象

## 异常
- **ValueError**: 当截面草图无效、参数超出范围或扫掠失败时抛出

## 示例代码

### 基础螺旋弹簧
```python
from simplecadapi.operations import *
from simplecadapi.core import LocalCoordinateSystem

# 在特定坐标系中创建圆形截面
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1),
):
    circle_profile = make_circle(radius=1)

# 创建基础螺旋弹簧
spring = helical_sweep(
    profile=circle_profile,
    coil_radius=8,          # 弹簧半径8
    pitch=4,                # 螺距4
    turns=5,                # 5圈
    points_per_turn=12,     # 每圈12个点
    smooth=True             # 平滑路径
)

export_stl(spring, "output/helical_spring_circle.stl")
```

### 方形截面螺旋
```python
from simplecadapi.operations import *
from simplecadapi.core import LocalCoordinateSystem

# 在特定坐标系中创建方形截面
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1),
):
    square_profile = make_rectangle(1.5, 1.5, center=True)

# 创建方形截面螺旋
square_helix = helical_sweep(
    profile=square_profile,
    coil_radius=10,
    pitch=6,
    turns=3,
    points_per_turn=16,     # 更高精度
    smooth=True
)

export_stl(square_helix, "output/helical_square.stl")
```

### 螺纹模拟
```python
from simplecadapi.operations import *
from simplecadapi.core import LocalCoordinateSystem

# 在特定坐标系中创建三角形截面（模拟螺纹）
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1),
):
    thread_points = [
        make_point(-0.5, 0, 0),
        make_point(0.5, 0, 0),
        make_point(0, 1, 0),
        make_point(-0.5, 0, 0)
    ]
    thread_lines = [make_segment(thread_points[i], thread_points[i+1]) 
                    for i in range(len(thread_points)-1)]
    thread_profile = make_sketch(thread_lines)

# 创建螺纹
thread = helical_sweep(
    profile=thread_profile,
    coil_radius=12,
    pitch=2,                # 细密螺距
    turns=8,
    points_per_turn=20,     # 高精度
    smooth=True
)

export_stl(thread, "output/helical_thread.stl")
```

### 变化参数的螺旋
```python
from simplecadapi.operations import *
from simplecadapi.core import LocalCoordinateSystem

# 在特定坐标系中创建椭圆截面
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1),
):
    ellipse_profile = make_ellipse(
        center=make_point(0, 0, 0),
        major_axis=2,
        minor_axis=1
    )

# 紧密螺旋
tight_helix = helical_sweep(
    profile=ellipse_profile,
    coil_radius=6,
    pitch=1.5,              # 紧密螺距
    turns=10,               # 多圈
    points_per_turn=8,      # 较低精度，更快计算
    smooth=False            # 不平滑，多边形路径
)

# 宽松螺旋
loose_helix = helical_sweep(
    profile=ellipse_profile,
    coil_radius=15,
    pitch=8,                # 宽松螺距
    turns=2.5,              # 2.5圈
    points_per_turn=24,     # 高精度
    smooth=True
)

export_stl(tight_helix, "output/tight_helix.stl")
export_stl(loose_helix, "output/loose_helix.stl")
```

### 复杂截面螺旋
```python
from simplecadapi.operations import *

# 创建复杂的星形截面
star_points = []
import math
for i in range(10):  # 5个尖角，10个点
    angle = i * math.pi / 5
    if i % 2 == 0:
        radius = 2  # 外半径
    else:
        radius = 1  # 内半径
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    star_points.append(make_point(x, y, 0))

star_points.append(star_points[0])  # 闭合
star_lines = [make_segement(star_points[i], star_points[i+1]) 
              for i in range(len(star_points)-1)]
star_profile = make_sketch(star_lines)

# 创建星形螺旋
star_helix = helical_sweep(
    profile=star_profile,
    coil_radius=12,
    pitch=5,
    turns=4,
    points_per_turn=16,
    smooth=True
)

export_stl(star_helix, "output/star_helix.stl")
```

### 不同精度对比
```python
from simplecadapi.operations import *
from simplecadapi.core import LocalCoordinateSystem

# 在特定坐标系中创建基础截面
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),
    y_axis=(0, 0, 1),
):
    base_profile = make_circle(radius=1.5)

# 低精度螺旋（快速）
low_precision = helical_sweep(
    profile=base_profile,
    coil_radius=10,
    pitch=4,
    turns=3,
    points_per_turn=6,      # 最低精度
    smooth=False
)

# 中等精度螺旋
medium_precision = helical_sweep(
    profile=base_profile,
    coil_radius=10,
    pitch=4,
    turns=3,
    points_per_turn=12,     # 默认精度
    smooth=True
)

# 高精度螺旋
high_precision = helical_sweep(
    profile=base_profile,
    coil_radius=10,
    pitch=4,
    turns=3,
    points_per_turn=24,     # 高精度
    smooth=True
)

export_stl(low_precision, "output/helix_low_precision.stl")
export_stl(medium_precision, "output/helix_medium_precision.stl")
export_stl(high_precision, "output/helix_high_precision.stl")
```

## 注意事项
1. **⚠️ 坐标系要求（重要）**：
   - profile截面草图**必须**在特定的LocalCoordinateSystem中构建
   - 必须使用 `x_axis=(0, 1, 0)` 和 `y_axis=(0, 0, 1)`
   - 不遵循此要求会导致螺旋方向错误或扫掠失败

2. `points_per_turn` 控制螺旋路径的精度：
   - 6-8: 低精度，快速计算，多边形外观
   - 12-16: 中等精度，推荐用于大多数应用
   - 20-32: 高精度，平滑外观，计算时间长

3. `smooth=True` 使用样条曲线，`smooth=False` 使用折线

4. `pitch` 为正值时螺旋向上，负值时向下

5. `turns` 可以是小数，如2.5表示两圈半

6. 截面应该相对较小，避免自相交

7. 复杂截面和高精度会显著增加计算时间

8. 生成的螺旋沿Z轴向上发展

9. 确保截面草图是有效的闭合轮廓
