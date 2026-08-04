# Wire

## Overview

`Wire` is the wire class in the SimpleCAD API, representing a 1D geometric path formed by connecting multiple edges. A wire can be open (different start and end points) or closed (forming a closed path). It wraps the OCP Wire object and adds tagging functionality.

## Class Definition

```python
class Wire(TaggedMixin):
    """Wire class that wraps OCP's Wire and adds tag functionality"""
```

## Inheritance

- Inherits from `TaggedMixin`, providing tag and metadata functionality

## Usage

- Represent continuous paths or contours
- Form the boundary of faces (Face)
- Define paths for sweep, extrude, and other operations
- Create complex geometric contours

## Constructor

### `__init__(wrapped)`

Initializes a wire object.

**Parameters:**
- `wrapped` (OCP TopoDS_Wire): A OCP wire object

**Raises:**
- `ValueError`: When the input wire object is invalid

**Example:**
```python
from simplecadapi import (
    make_rectangle_rwire, 
    make_circle_rwire, 
    make_polyline_rwire
)

# Create wires through the SimpleCAD functions
rectangle = make_rectangle_rwire(width=5, height=3)
circle = make_circle_rwire(center=(0, 0, 0), radius=2.0)
polyline = make_polyline_rwire(points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)])
```

## Main Properties

- `wrapped`: The underlying OCP wire object
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

print(f"The rectangle consists of {len(edges)} edges")
for i, edge in enumerate(edges):
    print(f"Edge {i}: length {edge.get_length():.3f}")
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

# Closed wire
rectangle = make_rectangle_rwire(width=5, height=3)
print(f"Rectangle is closed: {rectangle.is_closed()}")  # True

# Open wire
polyline = make_polyline_rwire(points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)])
print(f"Polyline is closed: {polyline.is_closed()}")  # False
```

### Tagging and Metadata

Use the functional public API `apply_tag(shape, tag)` and `list_tags(shape)` for tags. Use `set_metadata(key, value)` and `get_metadata(key, default=None)` for structured metadata.

## Usage Examples

### Creating Different Types of Wires

```python
from simplecadapi import (
    make_rectangle_rwire,
    make_circle_rwire,
    make_polyline_rwire,
    make_spline_rwire
)

# Rectangle wire
rectangle = make_rectangle_rwire(width=10, height=6)
apply_tag(rectangle, "rectangle")
apply_tag(rectangle, "closed")

# Circle wire
circle = make_circle_rwire(center=(0, 0, 0), radius=3.0)
apply_tag(circle, "circle")
apply_tag(circle, "closed")

# Polyline
polyline = make_polyline_rwire(points=[
    (0, 0, 0), (2, 0, 0), (2, 2, 0), (1, 3, 0), (0, 2, 0)
])
apply_tag(polyline, "polyline")
apply_tag(polyline, "open")

# Spline wire: control_points are B-spline poles, not sample points
spline = make_spline_rwire(
    control_points=[(0, 0, 0), (1, 2, 0), (3, 2, 0), (4, 0, 0)]
)
apply_tag(spline, "spline")
apply_tag(spline, "smooth")

# Analyze wire properties
wires = [rectangle, circle, polyline, spline]
for wire in wires:
    edges = wire.get_edges()
    closed = wire.is_closed()
    tags = list_tags(wire)
    
    print(f"Wire type: {tags}, edge count: {len(edges)}, closed: {closed}")
```

### Creating Complex Contours

```python
from simplecadapi import make_polyline_rwire

def create_complex_profile():
    """Create a complex contour wire"""
    
    # Define contour points
    points = [
        (0, 0, 0),      # start point
        (10, 0, 0),     # bottom edge
        (10, 2, 0),     # bottom right
        (8, 2, 0),      # inner notch 1
        (8, 4, 0),      # 
        (10, 4, 0),     # top right
        (10, 6, 0),     # right of top edge
        (0, 6, 0),      # left of top edge
        (0, 4, 0),      # top left
        (2, 4, 0),      # inner notch 2
        (2, 2, 0),      # 
        (0, 2, 0),      # bottom left
        (0, 0, 0)       # close back to start
    ]
    
    profile = make_polyline_rwire(points=points)
    apply_tag(profile, "complex_profile")
    apply_tag(profile, "symmetric")
    
    # Add geometric info
    edges = profile.get_edges()
    total_length = sum(edge.get_length() for edge in edges)
    
    profile.set_metadata("total_length", total_length)
    profile.set_metadata("point_count", len(points))
    profile.set_metadata("edge_count", len(edges))
    
    return profile

profile = create_complex_profile()
print(f"Complex profile: {list_tags(profile)}")
print(f"Total length: {profile.get_metadata('total_length'):.3f}")
print(f"Edge count: {profile.get_metadata('edge_count')}")
```

### Wire Analysis and Processing

```python
from simplecadapi import make_rectangle_rwire, make_circle_rwire

def analyze_wire_properties():
    """Analyze wire properties"""
    
    # Create different wires
    rectangle = make_rectangle_rwire(width=6, height=4)
    circle = make_circle_rwire(center=(0, 0, 0), radius=2.0)
    
    wires = [rectangle, circle]
    
    for i, wire in enumerate(wires):
        # Basic properties
        edges = wire.get_edges()
        is_closed = wire.is_closed()
        
        # Compute total length
        total_length = sum(edge.get_length() for edge in edges)
        
        # Analyze edges
        edge_lengths = [edge.get_length() for edge in edges]
        min_edge_length = min(edge_lengths)
        max_edge_length = max(edge_lengths)
        avg_edge_length = sum(edge_lengths) / len(edge_lengths)
        
        # Add tags and metadata
        apply_tag(wire, f"wire_{i}")
        apply_tag(wire, "analyzed")
        
        if is_closed:
            apply_tag(wire, "closed")
        else:
            apply_tag(wire, "open")
        
        wire.set_metadata("total_length", total_length)
        wire.set_metadata("edge_count", len(edges))
        wire.set_metadata("min_edge_length", min_edge_length)
        wire.set_metadata("max_edge_length", max_edge_length)
        wire.set_metadata("avg_edge_length", avg_edge_length)
        
        # Classify edges
        for j, edge in enumerate(edges):
            apply_tag(edge, f"wire_{i}_edge_{j}")
            edge.set_metadata("parent_wire", i)
            edge.set_metadata("position_in_wire", j)
        
        print(f"Wire {i}:")
        print(f"  Total length: {total_length:.3f}")
        print(f"  Edge count: {len(edges)}")
        print(f"  Closed: {is_closed}")
        print(f"  Shortest edge: {min_edge_length:.3f}")
        print(f"  Longest edge: {max_edge_length:.3f}")
        print(f"  Average edge length: {avg_edge_length:.3f}")
        print()

analyze_wire_properties()
```

### Wire Transformation and Operations

```python
from simplecadapi import make_rectangle_rwire, translate_shape, rotate_shape

def transform_wires():
    """Transform wires"""
    
    # Create the base rectangle
    base_rect = make_rectangle_rwire(width=4, height=2)
    apply_tag(base_rect, "base")
    apply_tag(base_rect, "original")
    
    # Create transformed wires
    translated_rect = translate_shape(base_rect, offset=(5, 0, 0))
    apply_tag(translated_rect, "translated")
    
    rotated_rect = rotate_shape(base_rect, axis=(0, 0, 1), angle=45)
    apply_tag(rotated_rect, "rotated")
    
    # Collect all wires
    all_wires = [base_rect, translated_rect, rotated_rect]
    
    # Analyze transform results
    for wire in all_wires:
        edges = wire.get_edges()
        total_length = sum(edge.get_length() for edge in edges)
        
        # Compute bounding box (simplified)
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
        
        print(f"Wire tags: {list_tags(wire)}")
        print(f"  Total length: {total_length:.3f}")
        if wire.get_metadata("bbox_min"):
            print(f"  Bounding box: {wire.get_metadata('bbox_min')} to {wire.get_metadata('bbox_max')}")
        print()

transform_wires()
```

### Building Wire Sequences

```python
from simplecadapi import make_segment_rwire

def create_wire_sequence():
    """Create a wire sequence"""
    
    # Create consecutive segments
    segments = []
    
    # Define waypoints
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
    
    # Create consecutive segments
    for i in range(len(waypoints) - 1):
        start = waypoints[i]
        end = waypoints[i + 1]
        
        segment = make_segment_rwire(start=start, end=end)
        apply_tag(segment, f"segment_{i}")
        apply_tag(segment, "path_segment")
        
        # Add direction info
        direction = (
            end[0] - start[0],
            end[1] - start[1],
            end[2] - start[2]
        )
        
        if direction[0] > 0:
            apply_tag(segment, "eastward")
        elif direction[0] < 0:
            apply_tag(segment, "westward")
        
        if direction[1] > 0:
            apply_tag(segment, "northward")
        elif direction[1] < 0:
            apply_tag(segment, "southward")
        
        segment.set_metadata("start_point", start)
        segment.set_metadata("end_point", end)
        segment.set_metadata("direction", direction)
        segment.set_metadata("sequence_index", i)
        
        segments.append(segment)
    
    # Analyze the sequence
    total_path_length = sum(seg.get_edges(0).get_length() for seg in segments)
    
    print(f"Path segment count: {len(segments)}")
    print(f"Total path length: {total_path_length:.3f}")
    
    # Classify by direction
    eastward = [s for s in segments if "eastward" in list_tags(s)]
    northward = [s for s in segments if "northward" in list_tags(s)]
    
    print(f"Eastward segments: {len(eastward)}")
    print(f"Northward segments: {len(northward)}")
    
    return segments

sequence = create_wire_sequence()
```

## String Representation

```python
from simplecadapi import make_rectangle_rwire

wire = make_rectangle_rwire(width=5, height=3)
apply_tag(wire, "example_rectangle")
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
