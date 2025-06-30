# make_line 函数文档

## 定义
```python
def make_line(points: List[Point], line_type: str = "segment") -> Line
```

## 作用
根据给定的点列表创建不同类型的曲线，包括线段、圆弧和样条曲线。

## 参数
- `points` (List[Point]): 定义曲线的点列表
- `line_type` (str): 曲线类型，可选值：
  - `"segment"`: 线段（默认）
  - `"arc"`: 圆弧
  - `"spline"`: 样条曲线

## 返回值
- `Line`: 曲线对象

## 示例代码

### 创建线段
```python
from simplecadapi import *

# 创建两点间的线段
p1 = make_point(0, 0, 0)
p2 = make_point(2, 2, 0)
line_segment = make_line([p1, p2], "segment")
```

### 创建圆弧
```python
from simplecadapi import *

# 创建三点圆弧
p1 = make_point(0, 0, 0)
p2 = make_point(1, 1, 0)  # 中间点
p3 = make_point(2, 0, 0)
arc = make_line([p1, p2, p3], "arc")
```

### 创建样条曲线
```python
from simplecadapi import *

# 创建平滑的样条曲线
control_points = [
    make_point(0, 0, 0),
    make_point(1, 2, 0),
    make_point(3, 1, 0),
    make_point(4, 3, 0)
]
spline = make_line(control_points, "spline")
```

### 在comprehensive_test中的应用
```python
# 创建L型轮廓的线段
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
```

## 注意事项
- 线段至少需要2个点
- 圆弧需要3个点（起点、中间点、终点）
- 样条曲线至少需要2个点，更多点可以创建更平滑的曲线
- 返回的Line对象可以用于构建Sketch对象
