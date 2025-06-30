# make_segement 函数文档

## 定义
```python
def make_segement(p1: Point, p2: Point) -> Line
```

## 作用
创建连接两个点的直线段。这是`make_line`函数的便捷版本，专门用于创建简单的线段。

## 参数
- `p1` (Point): 线段起点
- `p2` (Point): 线段终点

## 返回值
- `Line`: 线段对象

## 示例代码

### 基础用法
```python
from simplecadapi import *

# 创建简单线段
start_point = make_point(0, 0, 0)
end_point = make_point(3, 4, 0)
segment = make_segement(start_point, end_point)
```

### 创建连续线段
```python
from simplecadapi import *

# 创建折线的各个段
p1 = make_point(0, 0, 0)
p2 = make_point(1, 0, 0)
p3 = make_point(1, 1, 0)
p4 = make_point(0, 1, 0)

# 分别创建各个线段
seg1 = make_segement(p1, p2)
seg2 = make_segement(p2, p3)
seg3 = make_segement(p3, p4)
seg4 = make_segement(p4, p1)

# 用于构建闭合草图
segments = [seg1, seg2, seg3, seg4]
square_sketch = make_sketch(segments)
```

### 在几何构建中的应用
```python
from simplecadapi import *

# 构建三角形的各边
vertex1 = make_point(0, 0, 0)
vertex2 = make_point(2, 0, 0)
vertex3 = make_point(1, 2, 0)

side1 = make_segement(vertex1, vertex2)
side2 = make_segement(vertex2, vertex3)
side3 = make_segement(vertex3, vertex1)

triangle = make_sketch([side1, side2, side3])
```

## 注意事项
- 这是`make_line([p1, p2], "segment")`的简写形式
- 只能创建直线段，不能创建弧线或样条
- 常用于构建多边形或复杂草图的边界
- 返回的Line对象可以与其他线段组合形成闭合草图
