# make_angle_arc 函数文档

## 定义
```python
def make_angle_arc(center: Point, radius: float, start_angle: float, end_angle: float) -> Line
```

## 作用
根据中心点、半径和起始终止角度创建圆弧。这种方式更适合精确控制圆弧的几何参数。

## 参数
- `center` (Point): 圆弧的中心点
- `radius` (float): 圆弧半径
- `start_angle` (float): 起始角度（弧度）
- `end_angle` (float): 终止角度（弧度）

## 返回值
- `Line`: 圆弧对象

## 示例代码

### 基础角度圆弧
```python
from simplecadapi import *
import math

# 创建90度圆弧
center = make_point(0, 0, 0)
quarter_arc = make_angle_arc(
    center=center,
    radius=1.0,
    start_angle=0,           # 0度（X轴正方向）
    end_angle=math.pi/2      # 90度（Y轴正方向）
)
```

### 半圆弧
```python
from simplecadapi import *
import math

# 创建半圆
center = make_point(1, 1, 0)
semicircle = make_angle_arc(
    center=center,
    radius=2.0,
    start_angle=0,
    end_angle=math.pi        # 180度
)
```

### 完整圆形
```python
from simplecadapi import *
import math

# 创建完整圆（接近闭合的圆弧）
center = make_point(0, 0, 0)
full_circle = make_angle_arc(
    center=center,
    radius=1.5,
    start_angle=0,
    end_angle=2*math.pi - 0.01  # 几乎完整的圆
)
```

### 特定角度范围
```python
from simplecadapi import *
import math

# 创建60度扇形弧
center = make_point(2, 2, 0)
sector_arc = make_angle_arc(
    center=center,
    radius=1.0,
    start_angle=math.pi/6,    # 30度
    end_angle=math.pi/2       # 90度
)
```

### 在复合形状中使用
```python
from simplecadapi import *
import math

# 创建带圆弧连接的形状
center1 = make_point(1, 0, 0)
center2 = make_point(3, 0, 0)

# 左半圆
left_arc = make_angle_arc(center1, 1.0, math.pi/2, 3*math.pi/2)
# 右半圆  
right_arc = make_angle_arc(center2, 1.0, math.pi/2, 3*math.pi/2)

# 连接线
top_line = make_segement(
    make_point(1, 1, 0), 
    make_point(3, 1, 0)
)
bottom_line = make_segement(
    make_point(1, -1, 0), 
    make_point(3, -1, 0)
)

oval_shape = make_sketch([left_arc, top_line, right_arc, bottom_line])
```

## 注意事项
- 角度使用弧度制，不是角度制
- 起始角度和终止角度的方向遵循数学惯例（逆时针为正）
- 0弧度对应X轴正方向，π/2弧度对应Y轴正方向
- 如果start_angle > end_angle，会创建跨越0度的圆弧
- 常用于精确的几何设计，如齿轮齿形、机械零件的圆角等
