# Edge

## Overview

`Edge` is the edge class in SimpleCAD API, representing a 1D geometric element connecting two vertices. Edges can be lines, arcs, splines, and other types of curves. It wraps OCP's Edge object and adds tag functionality.

## Class Definition

```python
class Edge(TaggedMixin):
    """Edge class that wraps OCP's Edge and adds tag functionality"""
```

## Inheritance Relationships

- Inherits from `TaggedMixin`, with tag and metadata functionality

## Usage

- Represent connections between two points
- Fundamental elements composing Wires and Faces
- Provide geometric information (length, vertices, etc.)
- Support tag management and queries

## Constructor

### `__init__(wrapped)`

Initialize an edge object.

**Parameters:**
- `wrapped` (OCP TopoDS_Edge): OCP edge object

**Exceptions:**
- `ValueError`: Raised when the input edge object is invalid

**Example:**
```python
from simplecadapi import make_line_redge, make_circle_redge

# Create edges through the SimpleCAD functions
line_edge = make_line_redge(start=(0, 0, 0), end=(1, 1, 0))
circle_edge = make_circle_redge(center=(0, 0, 0), radius=1.0)
```

## Main Properties

- `wrapped`: Underlying OCP edge object
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

# Line edge
line = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
line_length = line.get_length()
print(f"Line length: {line_length}")  # 5.0

# Circle edge
circle = make_circle_redge(center=(0, 0, 0), radius=2.0)
circle_length = circle.get_length()
print(f"Circle circumference: {circle_length}")  # approx 12.566 (2π * 2)
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
print(f"Start point coordinates: {start_coords}")  # (1.0, 2.0, 3.0)
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
print(f"End point coordinates: {end_coords}")  # (4.0, 5.0, 6.0)
```

### Tagging and Metadata

Use the functional public API `apply_tag(shape, tag)` and `list_tags(shape)` for tags. Use `set_metadata(key, value)` and `get_metadata(key, default=None)` for structured metadata.

## Usage Examples

### Creating Different Types of Edges

```python
from simplecadapi import (
    make_line_redge, 
    make_circle_redge, 
    make_three_point_arc_redge,
    make_spline_redge
)

# Line edge
line = make_line_redge(start=(0, 0, 0), end=(5, 0, 0))
apply_tag(line, "base_line")

# Circle edge
circle = make_circle_redge(center=(0, 0, 0), radius=2.0)
apply_tag(circle, "full_circle")

# Three-point arc edge
arc = make_three_point_arc_redge(
    start=(0, 0, 0), 
    mid=(1, 1, 0), 
    end=(2, 0, 0)
)
apply_tag(arc, "arc_segment")

# Spline edge: control_points are B-spline poles, not sample points
spline = make_spline_redge(
    control_points=[(0, 0, 0), (1, 1, 0), (2, 1, 0), (3, 0, 0)]
)
apply_tag(spline, "smooth_curve")

# Print edge info
edges = [line, circle, arc, spline]
for edge in edges:
    print(f"Edge tags: {list_tags(edge)}, length: {edge.get_length():.3f}")
```

### Edge Analysis and Classification

```python
from simplecadapi import make_line_redge
import math

def analyze_edge_collection():
    """Analyze a collection of edges"""
    
    # Create multiple edges
    edges = [
        make_line_redge(start=(0, 0, 0), end=(1, 0, 0)),  # horizontal line
        make_line_redge(start=(0, 0, 0), end=(0, 1, 0)),  # vertical line
        make_line_redge(start=(0, 0, 0), end=(1, 1, 0)),  # diagonal line
        make_line_redge(start=(0, 0, 0), end=(2, 0, 0)),  # long horizontal line
        make_line_redge(start=(0, 0, 0), end=(0, 2, 0)),  # long vertical line
    ]
    
    # Analyze each edge
    for i, edge in enumerate(edges):
        length = edge.get_length()
        start_coords = edge.get_start_vertex().get_coordinates()
        end_coords = edge.get_end_vertex().get_coordinates()
        
        # Compute the direction vector
        direction = (
            end_coords[0] - start_coords[0],
            end_coords[1] - start_coords[1],
            end_coords[2] - start_coords[2]
        )
        
        # Classify edges
        if abs(direction[0]) > 0 and abs(direction[1]) == 0:
            apply_tag(edge, "horizontal")
        elif abs(direction[0]) == 0 and abs(direction[1]) > 0:
            apply_tag(edge, "vertical")
        elif abs(direction[0]) > 0 and abs(direction[1]) > 0:
            apply_tag(edge, "diagonal")
        
        # Classify by length
        if length < 1.5:
            apply_tag(edge, "short")
        else:
            apply_tag(edge, "long")
        
        # Add metadata
        edge.set_metadata("length", length)
        edge.set_metadata("direction", direction)
        edge.set_metadata("index", i)
        
        print(f"Edge {i}: length={length:.3f}, tags={list_tags(edge)}")

analyze_edge_collection()
```

### Building Edge Networks

```python
from simplecadapi import make_line_redge

def create_edge_network():
    """Create an edge network"""
    
    # Define nodes
    nodes = [
        (0, 0, 0),  # A
        (2, 0, 0),  # B
        (2, 2, 0),  # C
        (0, 2, 0),  # D
        (1, 1, 0),  # E (center point)
    ]
    
    # Define connections
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
        
        # Add connection info
        apply_tag(edge, f"connection_{chr(65+start_idx)}{chr(65+end_idx)}")
        
        # Classify edges
        if start_idx < 4 and end_idx < 4:
            apply_tag(edge, "perimeter")
        else:
            apply_tag(edge, "internal")
        
        # Add metadata
        edge.set_metadata("start_node", chr(65+start_idx))
        edge.set_metadata("end_node", chr(65+end_idx))
        edge.set_metadata("connection_index", i)
        
        edges.append(edge)
    
    return edges

# Create the network
network_edges = create_edge_network()

# Analyze the network
perimeter_edges = [e for e in network_edges if "perimeter" in list_tags(e)]
internal_edges = [e for e in network_edges if "internal" in list_tags(e)]

print(f"Perimeter edge count: {len(perimeter_edges)}")
print(f"Internal edge count: {len(internal_edges)}")

# Compute total length
total_length = sum(edge.get_length() for edge in network_edges)
print(f"Network total length: {total_length:.3f}")
```

### Edge Geometric Calculations

```python
from simplecadapi import make_line_redge, make_circle_redge
import math

def calculate_edge_properties():
    """Calculate edge geometric properties"""
    
    # Create different types of edges
    line = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
    circle = make_circle_redge(center=(0, 0, 0), radius=5.0)
    
    # Line properties
    line_length = line.get_length()
    line_start = line.get_start_vertex().get_coordinates()
    line_end = line.get_end_vertex().get_coordinates()
    
    # Compute the line midpoint
    line_midpoint = (
        (line_start[0] + line_end[0]) / 2,
        (line_start[1] + line_end[1]) / 2,
        (line_start[2] + line_end[2]) / 2
    )
    
    # Compute the line direction vector
    line_direction = (
        line_end[0] - line_start[0],
        line_end[1] - line_start[1],
        line_end[2] - line_start[2]
    )
    
    # Normalize the direction vector
    line_dir_length = math.sqrt(sum(x*x for x in line_direction))
    line_unit_direction = tuple(x / line_dir_length for x in line_direction)
    
    # Circle properties
    circle_length = circle.get_length()  # circumference
    circle_radius = circle_length / (2 * math.pi)
    
    # Store computed results
    line.set_metadata("midpoint", line_midpoint)
    line.set_metadata("direction", line_direction)
    line.set_metadata("unit_direction", line_unit_direction)
    apply_tag(line, "calculated")
    
    circle.set_metadata("radius", circle_radius)
    circle.set_metadata("circumference", circle_length)
    apply_tag(circle, "calculated")
    
    print(f"Line length: {line_length:.3f}")
    print(f"Line midpoint: {line_midpoint}")
    print(f"Line unit direction: {line_unit_direction}")
    print(f"Circle circumference: {circle_length:.3f}")
    print(f"Circle radius: {circle_radius:.3f}")

calculate_edge_properties()
```

## String Representation

```python
from simplecadapi import make_line_redge

edge = make_line_redge(start=(0, 0, 0), end=(3, 4, 0))
apply_tag(edge, "example_edge")
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
