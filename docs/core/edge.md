# Edge 边

## 概述

`Edge` 是 SimpleCAD API 中的边类，表示连接两个顶点的一维几何元素。边可以是直线、圆弧、样条曲线等不同类型的曲线。它包装了 CADQuery 的 Edge 对象，并添加了标签功能。

## 类定义

```python
class Edge(TaggedMixin):
    """边类，包装CADQuery的Edge，添加标签功能"""
```

## 继承关系

- 继承自 `TaggedMixin`，具有标签和元数据功能

## 用途

- 表示两点之间的连接
- 构成线 (Wire) 和面 (Face) 的基本元素
- 提供边的几何信息（长度、顶点等）
- 支持标签管理和查询

## 构造函数

### `__init__(cq_edge)`

初始化边对象。

**参数:**
- `cq_edge` (cadquery.Edge): CADQuery 的边对象

**异常:**
- `ValueError`: 当输入的边对象无效时抛出

**示例:**
```python
from simplecadapi import make_line_redge, make_circle_redge

# 通过 SimpleCAD 函数创建边
line_edge = make_line_redge(start=(0, 0, 0), end=(1, 1, 0))
circle_edge = make_circle_redge(center=(0, 0, 0), radius=1.0)
```

## 主要属性

- `cq_edge`: 底层的 CADQuery 边对象
- `_tags`: 标签集合（继承自 TaggedMixin）
- `_metadata`: 元数据字典（继承自 TaggedMixin）

## 常用方法

### `get_length()`

获取边的长度。

**返回:**
- `float`: 边的长度

**异常:**
- `ValueError`: 获取长度失败时抛出

**示例:**
```python
from simplecadapi import make_line_redge, make_circle_redge
import math

# 直线边
line = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
line_length = line.get_length()
print(f"直线长度: {line_length}")  # 5.0

# 圆形边
circle = make_circle_redge(center=(0, 0, 0), radius=2.0)
circle_length = circle.get_length()
print(f"圆形周长: {circle_length}")  # 约 12.566 (2π * 2)
```

### `get_start_vertex()`

获取边的起始顶点。

**返回:**
- `Vertex`: 起始顶点对象

**异常:**
- `ValueError`: 获取顶点失败时抛出

**示例:**
```python
from simplecadapi import make_line_redge

line = make_line_redge(start=(1, 2, 3), end=(4, 5, 6))
start_vertex = line.get_start_vertex()
start_coords = start_vertex.get_coordinates()
print(f"起始点坐标: {start_coords}")  # (1.0, 2.0, 3.0)
```

### `get_end_vertex()`

获取边的结束顶点。

**返回:**
- `Vertex`: 结束顶点对象

**异常:**
- `ValueError`: 获取顶点失败时抛出

**示例:**
```python
from simplecadapi import make_line_redge

line = make_line_redge(start=(1, 2, 3), end=(4, 5, 6))
end_vertex = line.get_end_vertex()
end_coords = end_vertex.get_coordinates()
print(f"结束点坐标: {end_coords}")  # (4.0, 5.0, 6.0)
```

### 标签管理方法

继承自 `TaggedMixin` 的方法：

#### `add_tag(tag)`、`has_tag(tag)`、`get_tags()`、`remove_tag(tag)`
#### `set_metadata(key, value)`、`get_metadata(key, default=None)`

使用方法与 Vertex 类似，详见 [Vertex 文档](vertex.md)。

## 使用示例

### 创建不同类型的边

```python
from simplecadapi import (
    make_line_redge, 
    make_circle_redge, 
    make_three_point_arc_redge,
    make_spline_redge
)

# 直线边
line = make_line_redge(start=(0, 0, 0), end=(5, 0, 0))
line.add_tag("base_line")

# 圆形边
circle = make_circle_redge(center=(0, 0, 0), radius=2.0)
circle.add_tag("full_circle")

# 三点圆弧边
arc = make_three_point_arc_redge(
    start=(0, 0, 0), 
    mid=(1, 1, 0), 
    end=(2, 0, 0)
)
arc.add_tag("arc_segment")

# 样条边
spline = make_spline_redge(points=[(0, 0, 0), (1, 1, 0), (2, 0, 0), (3, 1, 0)])
spline.add_tag("smooth_curve")

# 打印边的信息
edges = [line, circle, arc, spline]
for edge in edges:
    print(f"边标签: {edge.get_tags()}, 长度: {edge.get_length():.3f}")
```

### 边的分析和分类

```python
from simplecadapi import make_line_redge
import math

def analyze_edge_collection():
    """分析边的集合"""
    
    # 创建多条边
    edges = [
        make_line_redge(start=(0, 0, 0), end=(1, 0, 0)),  # 水平线
        make_line_redge(start=(0, 0, 0), end=(0, 1, 0)),  # 垂直线
        make_line_redge(start=(0, 0, 0), end=(1, 1, 0)),  # 对角线
        make_line_redge(start=(0, 0, 0), end=(2, 0, 0)),  # 长水平线
        make_line_redge(start=(0, 0, 0), end=(0, 2, 0)),  # 长垂直线
    ]
    
    # 分析每条边
    for i, edge in enumerate(edges):
        length = edge.get_length()
        start_coords = edge.get_start_vertex().get_coordinates()
        end_coords = edge.get_end_vertex().get_coordinates()
        
        # 计算方向向量
        direction = (
            end_coords[0] - start_coords[0],
            end_coords[1] - start_coords[1],
            end_coords[2] - start_coords[2]
        )
        
        # 分类边
        if abs(direction[0]) > 0 and abs(direction[1]) == 0:
            edge.add_tag("horizontal")
        elif abs(direction[0]) == 0 and abs(direction[1]) > 0:
            edge.add_tag("vertical")
        elif abs(direction[0]) > 0 and abs(direction[1]) > 0:
            edge.add_tag("diagonal")
        
        # 根据长度分类
        if length < 1.5:
            edge.add_tag("short")
        else:
            edge.add_tag("long")
        
        # 添加元数据
        edge.set_metadata("length", length)
        edge.set_metadata("direction", direction)
        edge.set_metadata("index", i)
        
        print(f"边 {i}: 长度={length:.3f}, 标签={edge.get_tags()}")

analyze_edge_collection()
```

### 构建边的网络

```python
from simplecadapi import make_line_redge

def create_edge_network():
    """创建边的网络结构"""
    
    # 定义节点
    nodes = [
        (0, 0, 0),  # A
        (2, 0, 0),  # B
        (2, 2, 0),  # C
        (0, 2, 0),  # D
        (1, 1, 0),  # E (中心点)
    ]
    
    # 定义连接关系
    connections = [
        (0, 1),  # A-B
        (1, 2),  # B-C
        (2, 3),  # C-D
        (3, 0),  # D-A
        (0, 4),  # A-E
        (1, 4),  # B-E
        (2, 4),  # C-E
        (3, 4),  # D-E
    ]
    
    edges = []
    
    for i, (start_idx, end_idx) in enumerate(connections):
        start_point = nodes[start_idx]
        end_point = nodes[end_idx]
        
        edge = make_line_redge(start=start_point, end=end_point)
        
        # 添加连接信息
        edge.add_tag(f"connection_{chr(65+start_idx)}{chr(65+end_idx)}")
        
        # 分类边
        if start_idx < 4 and end_idx < 4:
            edge.add_tag("perimeter")
        else:
            edge.add_tag("internal")
        
        # 添加元数据
        edge.set_metadata("start_node", chr(65+start_idx))
        edge.set_metadata("end_node", chr(65+end_idx))
        edge.set_metadata("connection_index", i)
        
        edges.append(edge)
    
    return edges

# 创建网络
network_edges = create_edge_network()

# 分析网络
perimeter_edges = [e for e in network_edges if e.has_tag("perimeter")]
internal_edges = [e for e in network_edges if e.has_tag("internal")]

print(f"周边边数: {len(perimeter_edges)}")
print(f"内部边数: {len(internal_edges)}")

# 计算总长度
total_length = sum(edge.get_length() for edge in network_edges)
print(f"网络总长度: {total_length:.3f}")
```

### 边的几何计算

```python
from simplecadapi import make_line_redge, make_circle_redge
import math

def calculate_edge_properties():
    """计算边的几何属性"""
    
    # 创建不同类型的边
    line = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
    circle = make_circle_redge(center=(0, 0, 0), radius=5.0)
    
    # 直线属性
    line_length = line.get_length()
    line_start = line.get_start_vertex().get_coordinates()
    line_end = line.get_end_vertex().get_coordinates()
    
    # 计算直线的中点
    line_midpoint = (
        (line_start[0] + line_end[0]) / 2,
        (line_start[1] + line_end[1]) / 2,
        (line_start[2] + line_end[2]) / 2
    )
    
    # 计算直线的方向向量
    line_direction = (
        line_end[0] - line_start[0],
        line_end[1] - line_start[1],
        line_end[2] - line_start[2]
    )
    
    # 归一化方向向量
    line_dir_length = math.sqrt(sum(x*x for x in line_direction))
    line_unit_direction = tuple(x / line_dir_length for x in line_direction)
    
    # 圆形属性
    circle_length = circle.get_length()  # 周长
    circle_radius = circle_length / (2 * math.pi)
    
    # 存储计算结果
    line.set_metadata("midpoint", line_midpoint)
    line.set_metadata("direction", line_direction)
    line.set_metadata("unit_direction", line_unit_direction)
    line.add_tag("calculated")
    
    circle.set_metadata("radius", circle_radius)
    circle.set_metadata("circumference", circle_length)
    circle.add_tag("calculated")
    
    print(f"直线长度: {line_length:.3f}")
    print(f"直线中点: {line_midpoint}")
    print(f"直线单位方向: {line_unit_direction}")
    print(f"圆形周长: {circle_length:.3f}")
    print(f"圆形半径: {circle_radius:.3f}")

calculate_edge_properties()
```

## 字符串表示

```python
from simplecadapi import make_line_redge

edge = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
edge.add_tag("example_edge")
edge.set_metadata("type", "line")

print(edge)
```

输出：
```
Edge:
  length: 5.000
  vertices:
    start: (0.0, 0.0, 0.0)
    end: (3.0, 4.0, 0.0)
  tags: [example_edge]
  metadata:
    type: line
```

## 与其他几何体的关系

- **顶点 (Vertex)**: 边的端点
- **线 (Wire)**: 由多个连接的边组成
- **面 (Face)**: 边界由边（通过线）定义
- **实体 (Solid)**: 最终由边构成的面组成

## 注意事项

- 边的长度由其几何形状决定，不能直接修改
- 圆形边是完整的圆，起始和结束顶点相同
- 样条边的长度是近似值，可能存在精度误差
- 边的方向性可能影响某些操作
- 标签和元数据不会影响边的几何属性
- 获取顶点时，对于圆形边等闭合边，起始和结束顶点可能相同
