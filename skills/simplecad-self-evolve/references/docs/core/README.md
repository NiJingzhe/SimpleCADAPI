# SimpleCAD API Core Classes Documentation

This directory contains detailed documentation for all core classes of SimpleCAD API.

## Core Classes Overview

SimpleCAD API provides a complete set of geometric modeling classes, from basic points, lines, and surfaces to complex solids and compounds. Each class has rich functionality and a flexible tag management system.

### Basic Classes

#### [CoordinateSystem - Coordinate System](coordinate_system.md)
A 3D coordinate system class for defining and managing local coordinate systems, supporting coordinate transformations and integration with CADQuery.

**Main Features:**
- Define local coordinate systems
- Coordinate and vector transformations
- Conversion with CADQuery coordinate systems

#### [SimpleWorkplane - Workplane](simple_workplane.md)
A workplane context manager that provides a local coordinate system environment, supporting nested usage.

**Main Features:**
- Define workplanes
- Context manager support
- Nested coordinate system management

#### [TaggedMixin - Tag Mixin Class](tagged_mixin.md)
A mixin class that provides unified tag and metadata management functionality for all geometry classes.

**Main Features:**
- Tag management (add, remove, query)
- Metadata storage and retrieval
- Geometry classification and query support

### Geometry Classes

#### 0D Geometry

##### [Vertex - Vertex](vertex.md)
Represents a point in 3D space, the fundamental element of all geometries.

**Main Features:**
- Store 3D coordinates
- Tag and metadata management
- Coordinate queries

#### 1D Geometry

##### [Edge - Edge](edge.md)
Represents a 1D geometric element connecting two vertices, which can be lines, arcs, splines, etc.

**Main Features:**
- Length calculation
- Endpoint queries
- Geometry type identification

##### [Wire - Wire](wire.md)
A 1D geometric path composed of multiple connected edges, which can be open or closed.

**Main Features:**
- Edge collection management
- Closure checking
- Path analysis

#### 2D Geometry

##### [Face - Face](face.md)
Represents 2D surface geometry, enclosed by one or more wires, and can contain holes.

**Main Features:**
- Area calculation
- Normal vector queries
- Boundary wire management

##### [Shell - Shell](shell.md)
A surface collection composed of multiple faces, which can be open or closed.

**Main Features:**
- Face collection management
- Surface analysis
- Thin-walled structure support

#### 3D Geometry

##### [Solid - Solid](solid.md)
Represents a 3D closed geometry with volume, the core object of CAD modeling.

**Main Features:**
- Volume calculation
- Face and edge queries
- Automatic face tagging
- Boolean operation support

##### [Compound - Compound](compound.md)
A collection composed of multiple geometry objects, used for managing complex assemblies.

**Main Features:**
- Multi-solid management
- Hierarchy support
- Batch operations

## Class Relationship Diagram

```
TaggedMixin
├── Vertex (0D)
├── Edge (1D)
├── Wire (1D) ← composed of Edges
├── Face (2D) ← bounded by Wires
├── Shell (2D) ← collection of Faces
├── Solid (3D) ← bounded by Shells/Faces
└── Compound (3D) ← collection of Solids

CoordinateSystem ← independent utility class
SimpleWorkplane ← uses CoordinateSystem
```

## Inheritance Relationships

All geometry classes inherit from `TaggedMixin`, obtaining unified tag and metadata management functionality:

- **Tag System**: Add string tags to geometries, supporting classification and queries
- **Metadata System**: Store key-value pairs, supporting complex attribute management
- **Query Support**: Efficient querying and filtering based on tags and metadata

## Coordinate System

SimpleCAD uses a unified coordinate system:

- **Global Coordinate System**: Z-up right-handed coordinate system
- **Local Coordinate Systems**: Defined through `CoordinateSystem` and `SimpleWorkplane`
- **CADQuery Compatible**: Automatically handles conversion with CADQuery coordinate systems

## Design Principles

### Consistency
All classes follow the same design patterns and naming conventions, providing a consistent user experience.

### Extensibility
Through the tag and metadata system, users can add custom information to geometries, supporting complex application scenarios.

### Interoperability
Seamlessly integrates with CADQuery, fully utilizing CADQuery's powerful functionality.

### Ease of Use
Provides intuitive APIs and rich examples, reducing learning costs.

## Usage Guide

### Basic Usage Flow

1. **Create Geometries**: Use `make_*` functions to create basic geometries
2. **Add Tags**: Use `add_tag()` to add identifiers to geometries
3. **Set Metadata**: Use `set_metadata()` to store attribute information
4. **Combine Operations**: Use boolean operations, transformations, etc. to create complex geometries
5. **Query and Filter**: Query desired geometries based on tags and metadata

### Best Practices

1. **Tag Naming**: Use consistent naming conventions, such as `category.subcategory.detail`
2. **Metadata Organization**: Use structured data to organize related information
3. **Coordinate System Management**: Use workplanes appropriately to simplify complex geometry creation
4. **Performance Considerations**: Avoid excessive tags and large metadata that may impact performance

## Example Code

```python
from simplecadapi import *

# 创建工作平面
with SimpleWorkplane(origin=(0, 0, 0)) as wp:
    # 创建基础几何体
    box = make_box_rsolid(width=5, height=3, depth=2)
    
    # 添加标签和元数据
    box.add_tag("structural")
    box.add_tag("aluminum")
    box.set_metadata("material", "6061-T6")
    box.set_metadata("density", 2.7)
    
    # 自动标记面
    box.auto_tag_faces("box")
    
    # 查询特定面
    top_faces = [f for f in box.get_faces() if f.has_tag("top")]
```

## Extension Development

If you need to create custom geometry classes:

1. Inherit from `TaggedMixin` to get tag functionality
2. Wrap the corresponding CADQuery object
3. Implement necessary geometry query methods
4. Provide appropriate string representation methods

```python
class CustomGeometry(TaggedMixin):
    def __init__(self, cq_object):
        TaggedMixin.__init__(self)
        self.cq_object = cq_object
    
    def get_custom_property(self):
        # 实现自定义功能
        pass
```

## More Resources

- [API Reference Documentation](../api/)
- [Example Code](../../examples.py)
- [User Guide](../../README.md)
- [Declarative Constraint Layout Design Draft](declarative_constraints.md)
