# make_three_point_arc 函数文档

## 定义
```python
def make_three_point_arc(p1: Point, p2: Point, p3: Point) -> Line
```

## 作用
通过三个点创建圆弧，其中第二个点作为圆弧上的中间点，定义圆弧的弯曲程度和方向。

## 参数
- `p1` (Point): 圆弧起点
- `p2` (Point): 圆弧上的中间点（用于定义弯曲）
- `p3` (Point): 圆弧终点

## 返回值
- `Line`: 圆弧对象

## 示例代码

### 基础圆弧
```python
from simplecadapi import *

# 创建简单的圆弧
start = make_point(0, 0, 0)
middle = make_point(1, 1, 0)  # 控制弯曲程度
end = make_point(2, 0, 0)

arc = make_three_point_arc(start, middle, end)
```

### 半圆弧
```python
from simplecadapi import *

# 创建半圆弧
p1 = make_point(-1, 0, 0)   # 左端点
p2 = make_point(0, 1, 0)    # 顶点
p3 = make_point(1, 0, 0)    # 右端点

semicircle = make_three_point_arc(p1, p2, p3)
```

### 在复杂形状中使用
```python
from simplecadapi import *

# 创建带圆弧的复合形状
corner1 = make_point(0, 0, 0)
corner2 = make_point(2, 0, 0)
arc_mid = make_point(2.5, 0.5, 0)
corner3 = make_point(3, 1, 0)
corner4 = make_point(0, 1, 0)

# 组合直线段和圆弧
lines = [
    make_segement(corner1, corner2),
    make_three_point_arc(corner2, arc_mid, corner3),  # 圆角
    make_segement(corner3, corner4),
    make_segement(corner4, corner1)
]

rounded_shape = make_sketch(lines)
```

### 控制弧度
```python
from simplecadapi import *

# 通过中间点位置控制弧度
start = make_point(0, 0, 0)
end = make_point(2, 0, 0)

# 小弧度（中间点靠近直线）
shallow_mid = make_point(1, 0.2, 0)
shallow_arc = make_three_point_arc(start, shallow_mid, end)

# 大弧度（中间点远离直线）
deep_mid = make_point(1, 1, 0)
deep_arc = make_three_point_arc(start, deep_mid, end)
```

## 注意事项
- 三个点不能共线，否则无法形成有效的圆弧
- 中间点的位置决定了圆弧的弯曲程度和方向
- 中间点距离起终点连线越远，圆弧弯曲越大
- 这是`make_line([p1, p2, p3], "arc")`的便捷形式
- 常用于创建圆角、弯曲边界等设计元素
