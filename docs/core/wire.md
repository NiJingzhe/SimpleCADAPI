# Wire

## Overview

`Wire` is the wire class in the SimpleCAD API, representing a 1D geometric path formed by connecting multiple edges. A wire can be open (different start and end points) or closed (forming a closed path). It wraps the CADQuery Wire object and adds tagging functionality.

## Class Definition

```python
class Wire(TaggedMixin):
    """线类，包装CADQuery的Wire，添加标签功能"""
```

## Inheritance

- Inherits from `TaggedMixin`, providing tag and metadata functionality

## Usage

- Represent continuous paths or contours
- Form the boundary of faces (Face)
- Define paths for sweep, extrude, and other operations
- Create complex geometric contours

## Constructor

### `__init__(cq_wire)`

Initializes a wire object.

**Parameters:**
- `cq_wire` (cadquery.Wire): A CADQuery wire object

**Raises:**
- `ValueError`: When the input wire object is invalid

**Example:**
```python
from simplecadapi import (
    make_rectangle_rwire, 
    make_circle_rwire, 
    make_polyline_rwire
)

# 通过 SimpleCAD 函数创建线
rectangle = make_rectangle_rwire(width=5, height=3)
circle = make_circle_rwire(center=(0, 0, 0), radius=2.0)
polyline = make_polyline_rwire(points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)])
```

## Main Properties

- `cq_wire`: The underlying CADQuery wire object
- `_tags`: Tag set (inherited from TaggedMixin)
- `_metadata`: Metadata dictionary (inherited from TaggedMixin)

## Common Methods

### `get_edges()`

Get all edges that make up the wire.

**Returns:**
- `List[Edge]`: List of edge objects

**Raises:**
- `ValueError`: When edge list retrieval fails

**Example:**
```python
from simplecadapi import make_rectangle_rwire

rectangle = make_rectangle_rwire(width=4, height=3)
edges = rectangle.get_edges()

print(f"矩形由 {len(edges)} 条边组成")
for i, edge in enumerate(edges):
    print(f"边 {i}: 长度 {edge.get_length():.3f}")
```

### `is_closed()`

Check if the wire is closed.

**Returns:**
- `bool`: Returns True if the wire is closed, False otherwise

**Raises:**
- `ValueError`: When closure check fails

**Example:**
```python
from simplecadapi import make_rectangle_rwire, make_polyline_rwire

# 闭合线
rectangle = make_rectangle_rwire(width=5, height=3)
print(f"矩形是否闭合: {rectangle.is_closed()}")  # True

# 开放线
polyline = make_polyline_rwire(points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)])
print(f"折线是否闭合: {polyline.is_closed()}")  # False
```

### Tag Management Methods

Methods inherited from `TaggedMixin`:

#### `add_tag(tag)`, `has_tag(tag)`, `get_tags()`, `remove_tag(tag)`
#### `set_metadata(key, value)`, `get_metadata(key, default=None)`

Usage is similar to Vertex; see [Vertex documentation](vertex.md) for details.

## Usage Examples

### Creating Different Types of Wires

```python
from simplecadapi import (
    make_rectangle_rwire,
    make_circle_rwire,
    make_polyline_rwire,
    make_spline_rwire
)

# 矩形线
rectangle = make_rectangle_rwire(width=10, height=6)
rectangle.add_tag("rectangle")
rectangle.add_tag("closed")

# 圆形线
circle = make_circle_rwire(center=(0, 0, 0), radius=3.0)
circle.add_tag("circle")
circle.add_tag("closed")

# 折线
polyline = make_polyline_rwire(points=[
    (0, 0, 0), (2, 0, 0), (2, 2, 0), (1, 3, 0), (0, 2, 0)
])
polyline.add_tag("polyline")
polyline.add_tag("open")

# 样条线
spline = make_spline_rwire(points=[
    (0, 0, 0), (1, 2, 0), (3, 2, 0), (4, 0, 0)
])
spline.add_tag("spline")
spline.add_tag("smooth")

# 分析线的属性
wires = [rectangle, circle, polyline, spline]
for wire in wires:
    edges = wire.get_edges()
    closed = wire.is_closed()
    tags = wire.get_tags()
    
    print(f"线类型: {tags}, 边数: {len(edges)}, 闭合: {closed}")
```

### Creating Complex Contours

```python
from simplecadapi import make_polyline_rwire

def create_complex_profile():
    """创建复杂的轮廓线"""
    
    # 定义轮廓点
    points = [
        (0, 0, 0),      # 起点
        (10, 0, 0),     # 底边
        (10, 2, 0),     # 右下
        (8, 2, 0),      # 内凹1
        (8, 4, 0),      # 
        (10, 4, 0),     # 右上
        (10, 6, 0),     # 顶边右
        (0, 6, 0),      # 顶边左
        (0, 4, 0),      # 左上
        (2, 4, 0),      # 内凹2
        (2, 2, 0),      # 
        (0, 2, 0),      # 左下
        (0, 0, 0)       # 闭合回起点
    ]
    
    profile = make_polyline_rwire(points=points)
    profile.add_tag("complex_profile")
    profile.add_tag("symmetric")
    
    # 添加几何信息
    edges = profile.get_edges()
    total_length = sum(edge.get_length() for edge in edges)
    
    profile.set_metadata("total_length", total_length)
    profile.set_metadata("point_count", len(points))
    profile.set_metadata("edge_count", len(edges))
    
    return profile

profile = create_complex_profile()
print(f"复杂轮廓: {profile.get_tags()}")
print(f"总长度: {profile.get_metadata('total_length'):.3f}")
print(f"边数: {profile.get_metadata('edge_count')}")
```

### Wire Analysis and Processing

```python
from simplecadapi import make_rectangle_rwire, make_circle_rwire

def analyze_wire_properties():
    """分析线的属性"""
    
    # 创建不同的线
    rectangle = make_rectangle_rwire(width=6, height=4)
    circle = make_circle_rwire(center=(0, 0, 0), radius=2.0)
    
    wires = [rectangle, circle]
    
    for i, wire in enumerate(wires):
        # 基本属性
        edges = wire.get_edges()
        is_closed = wire.is_closed()
        
        # 计算总长度
        total_length = sum(edge.get_length() for edge in edges)
        
        # 分析边
        edge_lengths = [edge.get_length() for edge in edges]
        min_edge_length = min(edge_lengths)
        max_edge_length = max(edge_lengths)
        avg_edge_length = sum(edge_lengths) / len(edge_lengths)
        
        # 添加标签和元数据
        wire.add_tag(f"wire_{i}")
        wire.add_tag("analyzed")
        
        if is_closed:
            wire.add_tag("closed")
        else:
            wire.add_tag("open")
        
        wire.set_metadata("total_length", total_length)
        wire.set_metadata("edge_count", len(edges))
        wire.set_metadata("min_edge_length", min_edge_length)
        wire.set_metadata("max_edge_length", max_edge_length)
        wire.set_metadata("avg_edge_length", avg_edge_length)
        
        # 分类边
        for j, edge in enumerate(edges):
            edge.add_tag(f"wire_{i}_edge_{j}")
            edge.set_metadata("parent_wire", i)
            edge.set_metadata("position_in_wire", j)
        
        print(f"线 {i}:")
        print(f"  总长度: {total_length:.3f}")
        print(f"  边数: {len(edges)}")
        print(f"  闭合: {is_closed}")
        print(f"  最短边: {min_edge_length:.3f}")
        print(f"  最长边: {max_edge_length:.3f}")
        print(f"  平均边长: {avg_edge_length:.3f}")
        print()

analyze_wire_properties()
```

### Wire Transformation and Operations

```python
from simplecadapi import make_rectangle_rwire, translate_shape, rotate_shape

def transform_wires():
    """变换线的操作"""
    
    # 创建基础矩形
    base_rect = make_rectangle_rwire(width=4, height=2)
    base_rect.add_tag("base")
    base_rect.add_tag("original")
    
    # 创建变换后的线
    translated_rect = translate_shape(base_rect, offset=(5, 0, 0))
    translated_rect.add_tag("translated")
    
    rotated_rect = rotate_shape(base_rect, axis=(0, 0, 1), angle=45)
    rotated_rect.add_tag("rotated")
    
    # 收集所有线
    all_wires = [base_rect, translated_rect, rotated_rect]
    
    # 分析变换结果
    for wire in all_wires:
        edges = wire.get_edges()
        total_length = sum(edge.get_length() for edge in edges)
        
        # 计算边界框（简化版）
        all_coords = []
        for edge in edges:
            start_coords = edge.get_start_vertex().get_coordinates()
            end_coords = edge.get_end_vertex().get_coordinates()
            all_coords.extend([start_coords, end_coords])
        
        if all_coords:
            min_x = min(coord[0] for coord in all_coords)
            max_x = max(coord[0] for coord in all_coords)
            min_y = min(coord[1] for coord in all_coords)
            max_y = max(coord[1] for coord in all_coords)
            
            wire.set_metadata("bbox_min", (min_x, min_y))
            wire.set_metadata("bbox_max", (max_x, max_y))
            wire.set_metadata("bbox_width", max_x - min_x)
            wire.set_metadata("bbox_height", max_y - min_y)
        
        wire.set_metadata("total_length", total_length)
        
        print(f"线标签: {wire.get_tags()}")
        print(f"  总长度: {total_length:.3f}")
        if wire.get_metadata("bbox_min"):
            print(f"  边界框: {wire.get_metadata('bbox_min')} 到 {wire.get_metadata('bbox_max')}")
        print()

transform_wires()
```

### Building Wire Sequences

```python
from simplecadapi import make_segment_rwire

def create_wire_sequence():
    """创建线的序列"""
    
    # 创建连续的线段
    segments = []
    
    # 定义路径点
    waypoints = [
        (0, 0, 0),
        (2, 0, 0),
        (2, 2, 0),
        (0, 2, 0),
        (0, 4, 0),
        (4, 4, 0),
        (4, 0, 0),
        (6, 0, 0)
    ]
    
    # 创建连续的线段
    for i in range(len(waypoints) - 1):
        start = waypoints[i]
        end = waypoints[i + 1]
        
        segment = make_segment_rwire(start=start, end=end)
        segment.add_tag(f"segment_{i}")
        segment.add_tag("path_segment")
        
        # 添加方向信息
        direction = (
            end[0] - start[0],
            end[1] - start[1],
            end[2] - start[2]
        )
        
        if direction[0] > 0:
            segment.add_tag("eastward")
        elif direction[0] < 0:
            segment.add_tag("westward")
        
        if direction[1] > 0:
            segment.add_tag("northward")
        elif direction[1] < 0:
            segment.add_tag("southward")
        
        segment.set_metadata("start_point", start)
        segment.set_metadata("end_point", end)
        segment.set_metadata("direction", direction)
        segment.set_metadata("sequence_index", i)
        
        segments.append(segment)
    
    # 分析序列
    total_path_length = sum(seg.get_edges()[0].get_length() for seg in segments)
    
    print(f"路径段数: {len(segments)}")
    print(f"总路径长度: {total_path_length:.3f}")
    
    # 按方向分类
    eastward = [s for s in segments if s.has_tag("eastward")]
    northward = [s for s in segments if s.has_tag("northward")]
    
    print(f"向东段数: {len(eastward)}")
    print(f"向北段数: {len(northward)}")
    
    return segments

sequence = create_wire_sequence()
```

## String Representation

```python
from simplecadapi import make_rectangle_rwire

wire = make_rectangle_rwire(width=5, height=3)
wire.add_tag("example_rectangle")
wire.set_metadata("area", 15.0)

print(wire)
```

Output:
```
Wire:
  edge_count: 4
  closed: True
  edges:
    edge_0:
      length: 5.000
      vertices:
        start: (0.0, 0.0, 0.0)
        end: (5.0, 0.0, 0.0)
    edge_1:
      length: 3.000
      vertices:
        start: (5.0, 0.0, 0.0)
        end: (5.0, 3.0, 0.0)
    edge_2:
      length: 5.000
      vertices:
        start: (5.0, 3.0, 0.0)
        end: (0.0, 3.0, 0.0)
    edge_3:
      length: 3.000
      vertices:
        start: (0.0, 3.0, 0.0)
        end: (0.0, 0.0, 0.0)
  tags: [example_rectangle]
  metadata:
    area: 15.0
```

## Relationships with Other Geometry

- **Edge (Edge)**: Components of a wire
- **Face (Face)**: Closed wires can define face boundaries
- **Solid (Solid)**: Can be created by sweeping or extruding wires

## Notes

- Wire edges must be continuous; endpoints of adjacent edges must coincide
- The start and end points of a closed wire must coincide
- Wire orientation affects certain operations (such as face normal direction)
- Complex wires may contain self-intersections and require special handling
- Wire length equals the sum of all edge lengths
- When creating faces, outer boundary wires should be counterclockwise; inner boundary wires should be clockwise