# Solid

## Overview

`Solid` is the solid class in the SimpleCAD API, representing a 3D closed geometry. Solids have volume and are one of the most important geometry types in CAD modeling. It wraps the OCP Solid object and adds tagging functionality and automatic face tagging capability.

## Class Definition

```python
class Solid(TaggedMixin):
    """Solid class that wraps OCP's Solid and adds tag functionality"""
```

## Inheritance

- Inherits from `TaggedMixin`, providing tag and metadata functionality

## Usage

- Represent 3D solid objects
- Perform boolean operations (union, intersection, difference)
- Apply feature operations (fillets, chamfers, etc.)
- Calculate physical properties such as volume and surface area
- Generate manufacturing data

## Constructor

### `__init__(wrapped)`

Initializes a solid object.

**Parameters:**
- `wrapped` (Union[OCP TopoDS_Solid, Any]): A OCP solid object or other Shape object

**Raises:**
- `ValueError`: When the input solid object is invalid

**Example:**
```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid
)

# Create solids through the SimpleCAD functions
box = make_box_rsolid(width=5, height=3, depth=2)
cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)
sphere = make_sphere_rsolid(center=(0, 0, 0), radius=1.5)
```

## Main Properties

- `wrapped`: The underlying OCP solid object
- `_tags`: Tag set (inherited from TaggedMixin)
- `_metadata`: Metadata dictionary (inherited from TaggedMixin)
- `_face_tags`: Face tag dictionary (internal use)

## Common Methods

### `get_volume()`

Get the volume of the solid.

**Returns:**
- `float`: The volume of the solid

**Raises:**
- `ValueError`: When volume retrieval fails

**Example:**
```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid
import math

# Box volume
box = make_box_rsolid(width=2, height=3, depth=4)
box_volume = box.get_volume()
print(f"Box volume: {box_volume}")  # 24.0

# Cylinder volume
cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)
cylinder_volume = cylinder.get_volume()
expected_volume = math.pi * 2**2 * 5
print(f"Cylinder volume: {cylinder_volume:.3f}, expected: {expected_volume:.3f}")

# Sphere volume
sphere = make_sphere_rsolid(center=(0, 0, 0), radius=1.5)
sphere_volume = sphere.get_volume()
expected_volume = (4/3) * math.pi * 1.5**3
print(f"Sphere volume: {sphere_volume:.3f}, expected: {expected_volume:.3f}")
```

### `get_faces()`

Get all faces that make up the solid.

**Returns:**
- `List[Face]`: List of face objects

**Raises:**
- `ValueError`: When face list retrieval fails

**Example:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=4, height=3, depth=2)
faces = box.get_faces()

print(f"The box has {len(faces)} faces")
for i, face in enumerate(faces):
    area = face.get_area()
    print(f"Face {i}: area {area:.3f}")
```

### `get_faces(index)`

Get one face by explicit index. In an active `GraphSession`, this intentional
indexed pick is preserved as a graph geo select node.

**Returns:**
- `Face`: The selected face object

**Example:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=4, height=3, depth=2)
first_face = box.get_faces(0)
print(first_face.get_area())
```

### `get_edges()`

Get all edges that make up the solid.

**Returns:**
- `List[Edge]`: List of edge objects

**Raises:**
- `ValueError`: When edge list retrieval fails

**Example:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=4, height=3, depth=2)
edges = box.get_edges()

print(f"The box has {len(edges)} edges")
for i, edge in enumerate(edges):
    length = edge.get_length()
    print(f"Edge {i}: length {length:.3f}")
```

### `get_edges(index)`

Get one edge by explicit index. In an active `GraphSession`, this intentional
indexed pick is preserved as a graph geo select node.

**Returns:**
- `Edge`: The selected edge object

**Example:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=4, height=3, depth=2)
first_edge = box.get_edges(0)
print(first_edge.get_length())
```

### `auto_tag_faces(geometry_type)`

Automatically add tags to faces.

**Parameters:**
- `geometry_type` (str): Geometry type ("box", "cylinder", "sphere", "unknown")

**Example:**
```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid

# Box face tagging
box = make_box_rsolid(width=4, height=3, depth=2)
box.auto_tag_faces("box")

faces = box.get_faces()
for face in faces:
    print(f"Face tags: {list_tags(face)}")

# Cylinder face tagging
cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)
cylinder.auto_tag_faces("cylinder")

faces = cylinder.get_faces()
for face in faces:
    print(f"Face tags: {list_tags(face)}")
```

### Tagging and Metadata

Use the functional public API `apply_tag(shape, tag)` and `list_tags(shape)` for tags. Use `set_metadata(key, value)` and `get_metadata(key, default=None)` for structured metadata.

## Usage Examples

### Creating and Analyzing Basic Solids

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid
)

def create_basic_solids():
    """Create and analyze basic solids"""
    
    # Create different types of solids
    solids = [
        ("box", make_box_rsolid(width=4, height=3, depth=2)),
        ("cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)),
        ("sphere", make_sphere_rsolid(center=(0, 0, 0), radius=1.5))
    ]
    
    for name, solid in solids:
        # Add basic tags
        apply_tag(solid, name)
        apply_tag(solid, "basic_geometry")
        
        # Auto-tag faces
        solid.auto_tag_faces(name)
        
        # Get geometric properties
        volume = solid.get_volume()
        faces = solid.get_faces()
        edges = solid.get_edges()
        
        # Compute surface area
        total_surface_area = sum(face.get_area() for face in faces)
        
        # Analyze face distribution
        face_areas = [face.get_area() for face in faces]
        min_face_area = min(face_areas)
        max_face_area = max(face_areas)
        avg_face_area = sum(face_areas) / len(face_areas)
        
        # Store metadata
        solid.set_metadata("volume", volume)
        solid.set_metadata("surface_area", total_surface_area)
        solid.set_metadata("face_count", len(faces))
        solid.set_metadata("edge_count", len(edges))
        solid.set_metadata("min_face_area", min_face_area)
        solid.set_metadata("max_face_area", max_face_area)
        solid.set_metadata("avg_face_area", avg_face_area)
        
        # Compute volume efficiency (volume/surface-area ratio)
        volume_efficiency = volume / total_surface_area if total_surface_area > 0 else 0
        solid.set_metadata("volume_efficiency", volume_efficiency)
        
        print(f"{name.upper()} solid analysis:")
        print(f"  Volume: {volume:.3f}")
        print(f"  Surface area: {total_surface_area:.3f}")
        print(f"  Face count: {len(faces)}")
        print(f"  Edge count: {len(edges)}")
        print(f"  Volume efficiency: {volume_efficiency:.3f}")
        print(f"  Area range: {min_face_area:.3f} - {max_face_area:.3f}")
        print()

create_basic_solids()
```

### Boolean Operations Example

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    union_rsolid,
    cut_rsolid,
    intersect_rsolid
)

def boolean_operations_example():
    """Boolean operations example"""
    
    # Create base geometries
    box = make_box_rsolid(width=6, height=4, depth=3)
    apply_tag(box, "base_box")
    
    cylinder = make_cylinder_rsolid(center=(3, 2, 0), radius=1, height=5)
    apply_tag(cylinder, "cutting_cylinder")
    
    # Union operation
    union_result = union_rsolid(box, cylinder)
    apply_tag(union_result, "union_result")
    apply_tag(union_result, "combined_geometry")
    
    # Difference operation (subtract the cylinder from the box)
    cut_result = cut_rsolid(box, cylinder)[0]
    apply_tag(cut_result, "cut_result")
    apply_tag(cut_result, "with_hole")
    
    # Intersection operation
    intersect_result = intersect_rsolid(box, cylinder)[0]
    apply_tag(intersect_result, "intersect_result")
    apply_tag(intersect_result, "common_volume")
    
    # Analyze results
    operations = [
        ("original box", box),
        ("original cylinder", cylinder),
        ("union", union_result),
        ("difference", cut_result),
        ("intersection", intersect_result)
    ]
    
    for name, solid in operations:
        volume = solid.get_volume()
        faces = solid.get_faces()
        surface_area = sum(face.get_area() for face in faces)
        
        solid.set_metadata("operation_type", name)
        solid.set_metadata("volume", volume)
        solid.set_metadata("surface_area", surface_area)
        
        print(f"{name}:")
        print(f"  Volume: {volume:.3f}")
        print(f"  Surface area: {surface_area:.3f}")
        print(f"  Face count: {len(faces)}")
        print(f"  Tags: {list_tags(solid)}")
        print()

boolean_operations_example()
```

### Feature Operations Example

```python
from simplecadapi import (
    make_box_rsolid,
    fillet_rsolid,
    chamfer_rsolid,
    select_edges_by_tag
)

def feature_operations_example():
    """Feature operations example"""
    
    # Create the base box
    base_box = make_box_rsolid(width=8, height=6, depth=4)
    apply_tag(base_box, "base_geometry")
    base_box.auto_tag_faces("box")
    
    # Analyze the original geometry
    original_volume = base_box.get_volume()
    original_faces = base_box.get_faces()
    original_edges = base_box.get_edges()
    
    print(f"Original geometry:")
    print(f"  Volume: {original_volume:.3f}")
    print(f"  Face count: {len(original_faces)}")
    print(f"  Edge count: {len(original_edges)}")
    print()
    
    # Fillet operation
    try:
        filleted_box = fillet_rsolid(base_box, radius=0.5)
        apply_tag(filleted_box, "filleted")
        apply_tag(filleted_box, "rounded_edges")
        
        filleted_volume = filleted_box.get_volume()
        filleted_faces = filleted_box.get_faces()
        filleted_edges = filleted_box.get_edges()
        
        filleted_box.set_metadata("original_volume", original_volume)
        filleted_box.set_metadata("volume_change", filleted_volume - original_volume)
        filleted_box.set_metadata("volume_ratio", filleted_volume / original_volume)
        
        print(f"After fillet:")
        print(f"  Volume: {filleted_volume:.3f}")
        print(f"  Volume change: {filleted_volume - original_volume:.3f}")
        print(f"  Face count: {len(filleted_faces)}")
        print(f"  Edge count: {len(filleted_edges)}")
        print()
        
    except Exception as e:
        print(f"Fillet failed: {e}")
        filleted_box = None
    
    # Chamfer operation
    try:
        chamfered_box = chamfer_rsolid(base_box, distance=0.3)
        apply_tag(chamfered_box, "chamfered")
        apply_tag(chamfered_box, "beveled_edges")
        
        chamfered_volume = chamfered_box.get_volume()
        chamfered_faces = chamfered_box.get_faces()
        chamfered_edges = chamfered_box.get_edges()
        
        chamfered_box.set_metadata("original_volume", original_volume)
        chamfered_box.set_metadata("volume_change", chamfered_volume - original_volume)
        chamfered_box.set_metadata("volume_ratio", chamfered_volume / original_volume)
        
        print(f"After chamfer:")
        print(f"  Volume: {chamfered_volume:.3f}")
        print(f"  Volume change: {chamfered_volume - original_volume:.3f}")
        print(f"  Face count: {len(chamfered_faces)}")
        print(f"  Edge count: {len(chamfered_edges)}")
        print()
        
    except Exception as e:
        print(f"Chamfer failed: {e}")
        chamfered_box = None
    
    # Compare results
    results = [("original", base_box)]
    if filleted_box:
        results.append(("fillet", filleted_box))
    if chamfered_box:
        results.append(("chamfer", chamfered_box))
    
    print("Feature operation comparison:")
    for name, solid in results:
        volume = solid.get_volume()
        faces = solid.get_faces()
        tags = list_tags(solid)
        print(f"  {name}: volume={volume:.3f}, face count={len(faces)}, tags={tags}")

feature_operations_example()
```

### Creating Complex Geometry

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid,
    union_rsolid,
    cut_rsolid,
    translate_shape,
    rotate_shape
)

def create_complex_geometry():
    """Create complex geometry"""
    
    # Create the main body
    main_body = make_box_rsolid(width=12, height=8, depth=6)
    apply_tag(main_body, "main_body")
    apply_tag(main_body, "base_structure")
    
    # Create cylindrical holes
    holes = []
    hole_positions = [(3, 2, 0), (9, 2, 0), (3, 6, 0), (9, 6, 0)]
    
    for i, (x, y, z) in enumerate(hole_positions):
        hole = make_cylinder_rsolid(center=(x, y, z), radius=0.8, height=8)
        apply_tag(hole, f"hole_{i}")
        apply_tag(hole, "mounting_hole")
        holes.append(hole)
    
    # Create a spherical feature
    sphere_feature = make_sphere_rsolid(center=(6, 4, 6), radius=2)
    apply_tag(sphere_feature, "sphere_feature")
    apply_tag(sphere_feature, "decorative")
    
    # Create a cylindrical support
    support_cylinder = make_cylinder_rsolid(center=(6, 4, 0), radius=1, height=4)
    apply_tag(support_cylinder, "support_cylinder")
    apply_tag(support_cylinder, "structural")
    
    # Combine geometries
    complex_solid = union_rsolid(main_body, sphere_feature)
    complex_solid = union_rsolid(complex_solid, support_cylinder)
    
    # Subtract holes
    for hole in holes:
        complex_solid = cut_rsolid(complex_solid, hole)[0]
    
    # Tag the complex solid
    apply_tag(complex_solid, "complex_geometry")
    apply_tag(complex_solid, "multi_feature")
    apply_tag(complex_solid, "machined_part")
    
    # Analyze the complex solid
    volume = complex_solid.get_volume()
    faces = complex_solid.get_faces()
    edges = complex_solid.get_edges()
    
    # Compute geometric complexity
    face_count = len(faces)
    edge_count = len(edges)
    complexity_ratio = edge_count / face_count if face_count > 0 else 0
    
    # Analyze face distribution
    face_areas = [face.get_area() for face in faces]
    total_surface_area = sum(face_areas)
    
    # Classify faces
    small_faces = [f for f in faces if f.get_area() < 1.0]
    large_faces = [f for f in faces if f.get_area() > 10.0]
    medium_faces = [f for f in faces if 1.0 <= f.get_area() <= 10.0]
    
    # Store analysis results
    complex_solid.set_metadata("volume", volume)
    complex_solid.set_metadata("surface_area", total_surface_area)
    complex_solid.set_metadata("face_count", face_count)
    complex_solid.set_metadata("edge_count", edge_count)
    complex_solid.set_metadata("complexity_ratio", complexity_ratio)
    complex_solid.set_metadata("small_face_count", len(small_faces))
    complex_solid.set_metadata("medium_face_count", len(medium_faces))
    complex_solid.set_metadata("large_face_count", len(large_faces))
    
    # Add complexity tags
    if complexity_ratio < 5:
        apply_tag(complex_solid, "simple_topology")
    elif complexity_ratio < 10:
        apply_tag(complex_solid, "moderate_topology")
    else:
        apply_tag(complex_solid, "complex_topology")
    
    print(f"Complex geometry analysis:")
    print(f"  Volume: {volume:.3f}")
    print(f"  Surface area: {total_surface_area:.3f}")
    print(f"  Face count: {face_count}")
    print(f"  Edge count: {edge_count}")
    print(f"  Complexity ratio: {complexity_ratio:.2f}")
    print(f"  Face distribution - small:{len(small_faces)}, medium:{len(medium_faces)}, large:{len(large_faces)}")
    print(f"  Tags: {list_tags(complex_solid)}")
    
    return complex_solid

complex_geometry = create_complex_geometry()
```

### Solid Quality Analysis

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid

def analyze_solid_quality():
    """Analyze solid quality"""
    
    # Create test solids
    test_solids = [
        ("small_box", make_box_rsolid(width=1, height=1, depth=1)),
        ("large_box", make_box_rsolid(width=10, height=10, depth=10)),
        ("thin_box", make_box_rsolid(width=10, height=10, depth=0.1)),
        ("cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)),
        ("sphere", make_sphere_rsolid(center=(0, 0, 0), radius=2))
    ]
    
    for name, solid in test_solids:
        apply_tag(solid, name)
        apply_tag(solid, "test_geometry")
        
        # Basic geometric properties
        volume = solid.get_volume()
        faces = solid.get_faces()
        edges = solid.get_edges()
        
        # Compute quality metrics
        surface_area = sum(face.get_area() for face in faces)
        volume_to_surface_ratio = volume / surface_area if surface_area > 0 else 0
        
        # Analyze topology complexity
        face_count = len(faces)
        edge_count = len(edges)
        euler_characteristic = None  # the simplified version does not compute the Euler characteristic
        
        # Face area distribution analysis
        face_areas = [face.get_area() for face in faces]
        if face_areas:
            min_area = min(face_areas)
            max_area = max(face_areas)
            area_ratio = max_area / min_area if min_area > 0 else float('inf')
        else:
            min_area = max_area = area_ratio = 0
        
        # Quality assessment
        quality_score = 0
        quality_issues = []
        
        # Volume check
        if volume > 1e-6:
            quality_score += 20
        else:
            quality_issues.append("extremely small volume")
        
        # Face count check
        if 4 <= face_count <= 100:
            quality_score += 20
        elif face_count > 100:
            quality_issues.append("too many faces")
        else:
            quality_issues.append("abnormal face count")
        
        # Area ratio check
        if area_ratio < 1000:
            quality_score += 20
        else:
            quality_issues.append("excessive area variation")
        
        # Volume efficiency check
        if volume_to_surface_ratio > 0.1:
            quality_score += 20
        else:
            quality_issues.append("low volume efficiency")
        
        # Edge count sanity check
        if edge_count < face_count * 10:
            quality_score += 20
        else:
            quality_issues.append("too many edges")
        
        # Store quality data
        solid.set_metadata("volume", volume)
        solid.set_metadata("surface_area", surface_area)
        solid.set_metadata("face_count", face_count)
        solid.set_metadata("edge_count", edge_count)
        solid.set_metadata("volume_to_surface_ratio", volume_to_surface_ratio)
        solid.set_metadata("area_ratio", area_ratio)
        solid.set_metadata("quality_score", quality_score)
        solid.set_metadata("quality_issues", quality_issues)
        
        # Quality tags
        if quality_score >= 80:
            apply_tag(solid, "high_quality")
        elif quality_score >= 60:
            apply_tag(solid, "good_quality")
        elif quality_score >= 40:
            apply_tag(solid, "acceptable_quality")
        else:
            apply_tag(solid, "poor_quality")
        
        print(f"{name.upper()} quality analysis:")
        print(f"  Volume: {volume:.6f}")
        print(f"  Surface area: {surface_area:.3f}")
        print(f"  Face count: {face_count}")
        print(f"  Edge count: {edge_count}")
        print(f"  Volume efficiency: {volume_to_surface_ratio:.3f}")
        print(f"  Area ratio: {area_ratio:.2f}")
        print(f"  Quality score: {quality_score}/100")
        if quality_issues:
            print(f"  Quality issues: {', '.join(quality_issues)}")
        print(f"  Quality grade: {[tag for tag in list_tags(solid) if 'quality' in tag]}")
        print()

analyze_solid_quality()
```

## String Representation

```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)
apply_tag(box, "example_box")
box.auto_tag_faces("box")
box.set_metadata("material", "aluminum")

print(box)
```

Output:
```
Solid:
  volume: 30.000
  face_count: 6
  edge_count: 12
  faces:
    face_0:
      area: 15.000
      normal: [0.000, 0.000, 1.000]
      tags: [top]
    face_1:
      area: 15.000
      normal: [0.000, 0.000, -1.000]
      tags: [bottom]
    face_2:
      area: 10.000
      normal: [0.000, 1.000, 0.000]
      tags: [front]
    face_3:
      area: 10.000
      normal: [0.000, -1.000, 0.000]
      tags: [back]
    face_4:
      area: 6.000
      normal: [1.000, 0.000, 0.000]
      tags: [right]
    face_5:
      area: 6.000
      normal: [-1.000, 0.000, 0.000]
      tags: [left]
  tags: [example_box]
  metadata:
    material: aluminum
```

## Relationships with Other Geometry

- **Face (Face)**: Boundary surfaces of a solid
- **Edge (Edge)**: Boundaries of faces
- **Shell (Shell)**: Solids can be decomposed into shells
- **Compound (Compound)**: Multiple solids can form a compound

## Application Scenarios

- **Mechanical design**: Part modeling
- **Architectural design**: Building components
- **Product design**: Industrial products
- **3D printing**: Prototype manufacturing
- **Simulation analysis**: Finite element analysis

## Notes

- Solids must be closed, valid geometry
- Boolean operations may change the solid's topology
- Complex solids may contain many faces and edges
- Feature operations may fail and require appropriate error handling
- Automatic face tagging depends on geometry regularity
- Solid quality directly affects the success rate and performance of subsequent operations
