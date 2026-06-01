# Vertex

## Overview

`Vertex` is the vertex class in SimpleCAD API, representing a point in 3D space. It wraps OCP's Vertex object and adds tag functionality for identifying and managing specific vertices in geometries.

## Class Definition

```python
class Vertex(TaggedMixin):
    """顶点类，包装OCP的Vertex，添加标签功能"""
```

## Inheritance Relationships

- Inherits from `TaggedMixin`, with tag and metadata functionality

## Usage

- Represent points in 3D space
- Serve as building elements for edges, wires, faces, and other geometries
- Provide vertex coordinate information
- Support tag management and queries

## Constructor

### `__init__(wrapped)`

Initialize a vertex object.

**Parameters:**
- `wrapped` (OCP TopoDS_Vertex): OCP vertex object

**Exceptions:**
- `ValueError`: Raised when the input vertex object is invalid

**Example:**
```python
from simplecadapi import make_point_rvertex

# 通过 SimpleCAD 函数创建顶点
vertex = make_point_rvertex(1.0, 2.0, 3.0)
```

## Main Properties

- `wrapped`: Underlying OCP vertex object
- `_tags`: Tag set (inherited from TaggedMixin)
- `_metadata`: Metadata dictionary (inherited from TaggedMixin)

## Common Methods

### `get_coordinates()`

Get the coordinates of the vertex.

**Returns:**
- `Tuple[float, float, float]`: Vertex coordinates (x, y, z)

**Exceptions:**
- `ValueError`: Raised when coordinate retrieval fails

**Example:**
```python
from simplecadapi import make_point_rvertex

vertex = make_point_rvertex(1.0, 2.0, 3.0)
coords = vertex.get_coordinates()
print(coords)  # (1.0, 2.0, 3.0)
```

### Tagging and Metadata

Use the functional public API `apply_tag(shape, tag)` and `list_tags(shape)` for tags. Use `set_metadata(key, value)` and `get_metadata(key, default=None)` for structured metadata.

**Example:**
```python
from simplecadapi import apply_tag, list_tags, make_point_rvertex

vertex = make_point_rvertex(0, 0, 0)
apply_tag(vertex, "role.origin")
apply_tag(vertex, "anchor.reference_point")

if "role.origin" in list_tags(vertex):
    print("这是原点")
```

### Metadata Management Methods

#### `set_metadata(key, value)`
Set metadata.

**Example:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.set_metadata("created_by", "user_input")
vertex.set_metadata("importance", "high")
```

#### `get_metadata(key, default=None)`
Get metadata.

**Example:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.set_metadata("created_by", "user_input")

creator = vertex.get_metadata("created_by")
print(creator)  # "user_input"

unknown = vertex.get_metadata("unknown_key", "default_value")
print(unknown)  # "default_value"
```

## Usage Examples

### Creating and Using Vertices

```python
from simplecadapi import make_point_rvertex

# 创建顶点
vertex1 = make_point_rvertex(0, 0, 0)
vertex2 = make_point_rvertex(1, 1, 1)

# 获取坐标
coords1 = vertex1.get_coordinates()
coords2 = vertex2.get_coordinates()

print(f"顶点1坐标: {coords1}")  # 顶点1坐标: (0.0, 0.0, 0.0)
print(f"顶点2坐标: {coords2}")  # 顶点2坐标: (1.0, 1.0, 1.0)
```

### Vertex Tag Management

```python
from simplecadapi import make_point_rvertex

# 创建关键点
origin = make_point_rvertex(0, 0, 0)
corner1 = make_point_rvertex(10, 0, 0)
corner2 = make_point_rvertex(10, 10, 0)
corner3 = make_point_rvertex(0, 10, 0)

# 添加标签
apply_tag(origin, "origin")
apply_tag(origin, "reference")

apply_tag(corner1, "corner")
apply_tag(corner1, "x_axis")

apply_tag(corner2, "corner")
apply_tag(corner2, "diagonal")

apply_tag(corner3, "corner")
apply_tag(corner3, "y_axis")

# 查找所有角点
vertices = [origin, corner1, corner2, corner3]
corners = [v for v in vertices if "corner" in list_tags(v)]

print(f"找到 {len(corners)} 个角点")
```

### Vertex Classification and Management

```python
from simplecadapi import make_point_rvertex

def create_grid_vertices(width, height, spacing):
    """创建网格顶点"""
    vertices = []
    
    for i in range(width + 1):
        for j in range(height + 1):
            x = i * spacing
            y = j * spacing
            z = 0
            
            vertex = make_point_rvertex(x, y, z)
            
            # 添加位置标签
            if i == 0 and j == 0:
                apply_tag(vertex, "origin")
            elif i == 0:
                apply_tag(vertex, "left_edge")
            elif i == width:
                apply_tag(vertex, "right_edge")
            
            if j == 0:
                apply_tag(vertex, "bottom_edge")
            elif j == height:
                apply_tag(vertex, "top_edge")
            
            # 添加角点标签
            if (i == 0 or i == width) and (j == 0 or j == height):
                apply_tag(vertex, "corner")
            
            # 添加元数据
            vertex.set_metadata("grid_position", (i, j))
            vertex.set_metadata("distance_from_origin", (x*x + y*y)**0.5)
            
            vertices.append(vertex)
    
    return vertices

# 创建 5x3 网格
vertices = create_grid_vertices(5, 3, 1.0)

# 查找特定顶点
corners = [v for v in vertices if "corner" in list_tags(v)]
origin = [v for v in vertices if "origin" in list_tags(v)][0]

print(f"网格顶点总数: {len(vertices)}")
print(f"角点数量: {len(corners)}")
print(f"原点坐标: {origin.get_coordinates()}")
```

### Vertex Distance Calculation

```python
import math
from simplecadapi import make_point_rvertex

def calculate_distance(vertex1, vertex2):
    """计算两个顶点之间的距离"""
    coords1 = vertex1.get_coordinates()
    coords2 = vertex2.get_coordinates()
    
    dx = coords2[0] - coords1[0]
    dy = coords2[1] - coords1[1]
    dz = coords2[2] - coords1[2]
    
    return math.sqrt(dx*dx + dy*dy + dz*dz)

# 创建顶点
v1 = make_point_rvertex(0, 0, 0)
v2 = make_point_rvertex(3, 4, 0)
v3 = make_point_rvertex(0, 0, 5)

# 计算距离
dist12 = calculate_distance(v1, v2)
dist13 = calculate_distance(v1, v3)
dist23 = calculate_distance(v2, v3)

print(f"v1 到 v2 的距离: {dist12}")  # 5.0
print(f"v1 到 v3 的距离: {dist13}")  # 5.0
print(f"v2 到 v3 的距离: {dist23}")  # 约 7.07
```

## String Representation

```python
from simplecadapi import make_point_rvertex

vertex = make_point_rvertex(1.234, 5.678, 9.012)
apply_tag(vertex, "test_point")
vertex.set_metadata("created_by", "example")

print(vertex)
```

Output:
```
Vertex:
  coordinates: [1.234, 5.678, 9.012]
  tags: [test_point]
  metadata:
    created_by: example
```

## Relationships with Other Geometries

Vertices are the fundamental elements that compose more complex geometries:

- **Edge**: Defined by two vertices
- **Wire**: Composed of multiple connected edges, containing multiple vertices
- **Face**: Boundary defined by vertices
- **Solid**: Ultimately composed of vertices

## Notes

- Vertex objects wrap OCP's underlying vertices; do not modify coordinates directly
- Tags are of string type and are case-sensitive
- Metadata can store values of any type
- Vertex coordinates are read-only; to modify positions, create new vertices
- Floating-point coordinates may have precision issues; consider tolerance when comparing
