# Edge

## Overview

`Edge` is the edge class in SimpleCAD API, representing a 1D geometric element connecting two vertices. Edges can be lines, arcs, splines, and other types of curves. It wraps CADQuery's Edge object and adds tag functionality.

## Class Definition

```python
class Edge(TaggedMixin):
    """边类，包装CADQuery的Edge，添加标签功能"""
```

## Inheritance Relationships

- Inherits from `TaggedMixin`, with tag and metadata functionality

## Usage

- Represent connections between two points
- Fundamental elements composing Wires and Faces
- Provide geometric information (length, vertices, etc.)
- Support tag management and queries

## Constructor

### `__init__(cq_edge)`

Initialize an edge object.

**Parameters:**
- `cq_edge` (cadquery.Edge): CADQuery edge object

**Exceptions:**
- `ValueError`: Raised when the input edge object is invalid

**Example:**
```python
from simplecadapi import make_line_redge, make_circle_redge

# 通过 SimpleCAD 函数创建边
line_edge = make_line_redge(start=(0, 0, 0), end=(1, 1, 0))
circle_edge = make_circle_redge(center=(0, 0, 0), radius=1.0)
```

## Main Properties

- `cq_edge`: Underlying CADQuery edge object
- `_tags`: Tag set (inherited from TaggedMixin)
- `_metadata`: Metadata dictionary (inherited from TaggedMixin)

## Common Methods

### `get_length()`

Get the length of the edge.

**Returns:**
- `float`: Edge length

**Exceptions:**
- `ValueError`: Raised when length retrieval fails

**Example:**
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

Get the start vertex of the edge.

**Returns:**
- `Vertex`: Start vertex object

**Exceptions:**
- `ValueError`: Raised when vertex retrieval fails

**Example:**
```python
from simplecadapi import make_line_redge

line = make_line_redge(start=(1, 2, 3), end=(4, 5, 6))
start_vertex = line.get_start_vertex()
start_coords = start_vertex.get_coordinates()
print(f"起始点坐标: {start_coords}")  # (1.0, 2.0, 3.0)
```

### `get_end_vertex()`

Get the end vertex of the edge.

**Returns:**
- `Vertex`: End vertex object

**Exceptions:**
- `ValueError`: Raised when vertex retrieval fails

**Example:**
```python
from simplecadapi import make_line_redge

line = make_line_redge(start=(1, 2, 3), end=(4, 5, 6))
end_vertex = line.get_end_vertex()
end_coords = end_vertex.get_coordinates()
print(f"结束点坐标: {end_coords}")  # (4.0, 5.0, 6.0)
```

### Tag Management Methods

Methods inherited from `TaggedMixin`:

#### `add_tag(tag)`, `has_tag(tag)`, `get_tags()`, `remove_tag(tag)`
#### `set_metadata(key, value)`, `get_metadata(key, default=None)`

Usage is similar to Vertex; see [Vertex documentation](vertex.md) for details.

## Usage Examples

### Creating Different Types of Edges

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

### Edge Analysis and Classification

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

### Building Edge Networks

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

### Edge Geometric Calculations

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

## String Representation

```python
from simplecadapi import make_line_redge

edge = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
edge.add_tag("example_edge")
edge.set_metadata("type", "line")

print(edge)
```

Output:
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

## Relationships with Other Geometries

- **Vertex**: Endpoints of edges
- **Wire**: Composed of multiple connected edges
- **Face**: Boundary defined by edges (via wires)
- **Solid**: Ultimately composed of faces formed by edges

## Notes

- Edge length is determined by its geometry and cannot be directly modified
- Circular edges are complete circles with identical start and end vertices
- Spline edge lengths are approximate values and may have precision errors
- Edge directionality may affect certain operations
- Tags and metadata do not affect edge geometry properties
- When retrieving vertices, for closed edges like circular edges, start and end vertices may be identical
