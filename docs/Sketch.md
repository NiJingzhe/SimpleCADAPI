# Sketch 类文档

## 概述
Sketch类表示二维草图，由多条Line组成的闭合平面轮廓。它是所有二维到三维转换操作（如拉伸、旋转）的基础。

## 类定义
```python
class Sketch:
    """二维草图（闭合平面轮廓）"""
```

## 构造函数
```python
def __init__(self, lines: List[Line])
```

### 参数
- `lines`: Line对象列表，组成闭合轮廓的曲线

### 验证规则
- 必须形成闭合轮廓（起点和终点重合）
- 所有线段必须位于同一平面内

## 属性
- `lines`: Line对象列表，组成草图的曲线
- `_cq_wire`: CADQuery Wire对象（延迟创建）

## 方法

### _validate()
验证草图的有效性
- 检查闭合性和共面性
- **异常**: 如果不满足要求则抛出ValueError

### _is_closed() -> bool
检查草图是否闭合
- **返回**: 布尔值，True表示闭合
- 通过比较首条线的起点和末条线的终点判断

### _is_planar() -> bool
检查所有线段是否共面
- **返回**: 布尔值（当前简化实现总是返回True）
- **注意**: 完整的共面检查有待实现

### to_cq_wire()
转换为CADQuery的线框对象
- **返回**: CADQuery Wire对象
- 支持延迟创建和缓存

### __repr__() -> str
字符串表示
- **返回**: 包含线段数量的字符串

## 使用示例

### 创建矩形草图
```python
from simplecadapi.core import Point, Line, Sketch

# 定义矩形的四个角点
p1 = Point((0, 0, 0))
p2 = Point((10, 0, 0))
p3 = Point((10, 5, 0))
p4 = Point((0, 5, 0))

# 创建四条边
lines = [
    Line([p1, p2], "segment"),  # 底边
    Line([p2, p3], "segment"),  # 右边
    Line([p3, p4], "segment"),  # 顶边
    Line([p4, p1], "segment")   # 左边
]

# 创建矩形草图
rectangle = Sketch(lines)
print(rectangle)  # Sketch(lines=4)
```

### 创建三角形草图
```python
# 三角形的三个顶点
p1 = Point((0, 0, 0))
p2 = Point((10, 0, 0))
p3 = Point((5, 8, 0))

# 创建三条边
triangle_lines = [
    Line([p1, p2], "segment"),
    Line([p2, p3], "segment"),
    Line([p3, p1], "segment")
]

triangle = Sketch(triangle_lines)
```

### 创建包含圆弧的草图
```python
# 混合线段和圆弧的草图
p1 = Point((0, 0, 0))
p2 = Point((10, 0, 0))
p3 = Point((15, 5, 0))    # 圆弧中间点
p4 = Point((10, 10, 0))
p5 = Point((0, 10, 0))

mixed_lines = [
    Line([p1, p2], "segment"),      # 底边（直线）
    Line([p2, p3, p4], "arc"),      # 右边（圆弧）
    Line([p4, p5], "segment"),      # 顶边（直线）
    Line([p5, p1], "segment")       # 左边（直线）
]

mixed_sketch = Sketch(mixed_lines)
```

### 复杂轮廓草图
```python
# 使用样条曲线创建复杂轮廓
control_points = [
    Point((0, 0, 0)),
    Point((3, 2, 0)),
    Point((7, 4, 0)),
    Point((10, 3, 0)),
    Point((10, 0, 0))
]

# 顶部使用样条曲线，其他边使用直线
complex_lines = [
    Line([control_points[0], control_points[-1]], "segment"),  # 底边
    Line([control_points[-1], Point((10, 5, 0))], "segment"), # 右边
    Line(control_points[:-1], "spline"),  # 顶部曲线
    Line([control_points[0], Point((0, 5, 0))], "segment"),   # 左边上部
    Line([Point((0, 5, 0)), control_points[0]], "segment")    # 左边下部
]
```

### 与CADQuery集成
```python
import cadquery as cq

# 创建草图并转换为CADQuery线框
sketch = Sketch(lines)  # 使用前面定义的矩形
cq_wire = sketch.to_cq_wire()

# 创建面
face = cq.Face.makeFromWires(cq_wire)

# 在工作平面中使用
workplane = cq.Workplane().add(face)
```

### 在不同坐标系中创建草图
```python
from simplecadapi.core import CoordinateSystem

# 创建倾斜平面上的坐标系
tilted_cs = CoordinateSystem(
    origin=(0, 0, 5),
    x_axis=(1, 0, 0),
    y_axis=(0, 0.8, 0.6)  # 倾斜的Y轴
)

# 在倾斜平面上创建点
tilted_points = [
    Point((0, 0, 0), tilted_cs),
    Point((5, 0, 0), tilted_cs),
    Point((5, 3, 0), tilted_cs),
    Point((0, 3, 0), tilted_cs)
]

# 创建倾斜平面上的矩形草图
tilted_lines = [
    Line([tilted_points[0], tilted_points[1]], "segment"),
    Line([tilted_points[1], tilted_points[2]], "segment"),
    Line([tilted_points[2], tilted_points[3]], "segment"),
    Line([tilted_points[3], tilted_points[0]], "segment")
]

tilted_sketch = Sketch(tilted_lines)
```

## 验证和调试

### 检查草图有效性
```python
try:
    sketch = Sketch(lines)
    print("草图创建成功")
except ValueError as e:
    print(f"草图创建失败: {e}")
```

### 手动验证闭合性
```python
def check_closure(lines):
    if not lines:
        return False
    
    start = lines[0].points[0].global_coords
    end = lines[-1].points[-1].global_coords
    distance = np.linalg.norm(start - end)
    print(f"起点: {start}")
    print(f"终点: {end}")
    print(f"距离: {distance}")
    return distance < 1e-6

# 使用示例
is_closed = check_closure(lines)
print(f"草图是否闭合: {is_closed}")
```

## 注意事项
1. 草图必须形成闭合轮廓，起点和终点的距离误差须小于1e-6
2. 所有线段应位于同一平面内（当前版本的共面检查有待完善）
3. 线段的连接顺序很重要，相邻线段的端点必须重合
4. 支持混合不同类型的曲线（直线、圆弧、样条）
5. 草图是所有拉伸、旋转等3D操作的基础
6. 与CADQuery的Wire对象无缝集成
