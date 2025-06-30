# make_spline 函数文档

## 定义
```python
def make_spline(points: List[Point]) -> Line
```

## 作用
通过一系列控制点创建平滑的样条曲线。样条曲线会平滑地通过或接近所有控制点，产生自然的弯曲效果。

## 参数
- `points` (List[Point]): 样条曲线的控制点列表（至少需要2个点）

## 返回值
- `Line`: 样条曲线对象

## 示例代码

### 基础样条曲线
```python
from simplecadapi import *

# 创建简单的S形样条曲线
control_points = [
    make_point(0, 0, 0),
    make_point(1, 2, 0),
    make_point(2, -1, 0),
    make_point(3, 1, 0)
]

spline = make_spline(control_points)
```

### 平滑的波浪形
```python
from simplecadapi import *
import math

# 创建正弦波样的样条曲线
wave_points = []
for i in range(10):
    x = i * 0.5
    y = math.sin(x) * 2
    wave_points.append(make_point(x, y, 0))

wave_spline = make_spline(wave_points)
```

### 3D螺旋样条
```python
from simplecadapi import *
import math

# 创建3D螺旋形样条曲线
helix_points = []
for i in range(20):
    t = i * 0.2
    x = math.cos(t) * 2
    y = math.sin(t) * 2
    z = t * 0.5
    helix_points.append(make_point(x, y, z))

helix_spline = make_spline(helix_points)
```

### 复杂轮廓设计
```python
from simplecadapi import *

# 设计流线型轮廓
profile_points = [
    make_point(0, 0, 0),       # 起点
    make_point(1, 0.5, 0),     # 上升
    make_point(3, 1.2, 0),     # 峰值区域
    make_point(5, 1.0, 0),     # 平缓下降
    make_point(7, 0.3, 0),     # 继续下降
    make_point(8, 0, 0)        # 终点
]

aerodynamic_profile = make_spline(profile_points)

# 结合直线创建闭合形状
bottom_line = make_segement(
    make_point(8, 0, 0), 
    make_point(0, 0, 0)
)

airfoil_sketch = make_sketch([aerodynamic_profile, bottom_line])
```

### 在comprehensive_test中的应用
```python
# 创建螺纹齿形的样条版本
thread_points = [
    make_point(0, -0.1, 0),
    make_point(0.05, -0.05, 0),  # 平滑过渡点
    make_point(0.15, -0.02, 0),  # 峰值前
    make_point(0.2, 0, 0),       # 峰值
    make_point(0.15, 0.02, 0),   # 峰值后
    make_point(0.05, 0.05, 0),   # 平滑过渡点
    make_point(0, 0.1, 0)
]

smooth_thread_profile = make_spline(thread_points)
```

## 注意事项
- 至少需要2个控制点，但通常需要3个或更多点才能体现样条的优势
- 样条曲线会尽量平滑地连接所有控制点
- 控制点越多，曲线越复杂，但也可能产生不期望的振荡
- 适用于需要平滑过渡的有机形状、流线型设计
- 这是`make_line(points, "spline")`的便捷形式
- 样条曲线计算比直线段复杂，但提供更自然的外观
