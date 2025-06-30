# Line 类文档

## 概述
Line类表示三维空间中的曲线，支持线段、圆弧和样条曲线三种类型。每种类型使用不同数量的控制点来定义形状。

## 类定义
```python
class Line:
    """曲线（线段/圆弧/样条）"""
```

## 构造函数
```python
def __init__(self, points: List[Point], line_type: str = "segment")
```

### 参数
- `points`: Point对象列表，用作控制点
- `line_type`: 曲线类型，可选值:
  - `"segment"`: 线段（需要2个点）
  - `"arc"`: 圆弧（需要3个点）
  - `"spline"`: 样条曲线（至少2个点）

## 属性
- `points`: Point对象列表，控制点
- `type`: 字符串，曲线类型
- `_cq_edge`: CADQuery Edge对象（延迟创建）

## 方法

### _validate()
验证线的参数合法性
- 检查控制点数量是否符合曲线类型要求
- **异常**: 如果点数不符合要求则抛出ValueError

### to_cq_edge()
转换为CADQuery的边对象
- **返回**: CADQuery Edge对象
- 支持延迟创建，首次调用时创建并缓存

### __repr__() -> str
字符串表示
- **返回**: 包含类型和控制点数量的字符串

## 使用示例

### 创建线段
```python
from simplecadapi.core import Point, Line

# 创建两个端点
start_point = Point((0, 0, 0))
end_point = Point((10, 5, 0))

# 创建线段
line_segment = Line([start_point, end_point], "segment")
print(line_segment)  # Line(type=segment, points=2)
```

### 创建圆弧
```python
# 通过三个点定义圆弧
p1 = Point((0, 0, 0))     # 起点
p2 = Point((5, 5, 0))     # 中间点
p3 = Point((10, 0, 0))    # 终点

arc = Line([p1, p2, p3], "arc")
print(arc)  # Line(type=arc, points=3)
```

### 创建样条曲线
```python
# 使用多个控制点创建样条曲线
control_points = [
    Point((0, 0, 0)),
    Point((2, 4, 0)),
    Point((5, 3, 0)),
    Point((8, 6, 0)),
    Point((10, 2, 0))
]

spline = Line(control_points, "spline")
print(spline)  # Line(type=spline, points=5)
```

### 与CADQuery集成
```python
import cadquery as cq

# 创建线段并转换为CADQuery边
line = Line([Point((0, 0, 0)), Point((10, 0, 0))], "segment")
cq_edge = line.to_cq_edge()

# 使用CADQuery边创建线框
edges = [cq_edge]
# 可以组合多条边创建复杂形状
```

### 创建矩形轮廓
```python
# 使用四条线段创建矩形
p1 = Point((0, 0, 0))
p2 = Point((10, 0, 0))
p3 = Point((10, 5, 0))
p4 = Point((0, 5, 0))

# 四条边
lines = [
    Line([p1, p2], "segment"),  # 底边
    Line([p2, p3], "segment"),  # 右边
    Line([p3, p4], "segment"),  # 顶边
    Line([p4, p1], "segment")   # 左边
]

# 这些线可以用于创建Sketch对象
```

### 在不同坐标系中创建曲线
```python
from simplecadapi.core import CoordinateSystem

# 创建倾斜的坐标系
tilted_cs = CoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(1, 1, 0),      # 45度倾斜
    y_axis=(-1, 1, 0)
)

# 在倾斜坐标系中的点
p1_tilted = Point((0, 0, 0), tilted_cs)
p2_tilted = Point((5, 0, 0), tilted_cs)

# 创建在倾斜坐标系中的线段
tilted_line = Line([p1_tilted, p2_tilted], "segment")
```

## 曲线类型详解

### 线段 (segment)
- **控制点**: 恰好2个点（起点和终点）
- **用途**: 直线连接，多边形边界，基础几何形状
- **特点**: 最简单的曲线类型

### 圆弧 (arc) 
- **控制点**: 恰好3个点（起点、中间点、终点）
- **用途**: 圆形轮廓的一部分，平滑转角
- **特点**: 通过三点确定唯一圆弧

### 样条曲线 (spline)
- **控制点**: 至少2个点，无上限
- **用途**: 平滑的自由曲线，复杂轮廓
- **特点**: 提供最大的形状灵活性

## 注意事项
1. 每种曲线类型对控制点数量有严格要求
2. 圆弧的三个点不能共线
3. 样条曲线通过所有控制点，提供平滑插值
4. 所有曲线类型都支持与CADQuery的无缝集成
5. 延迟创建机制提高性能，仅在需要时转换为CADQuery对象
