# Connector

## Class Definition

```python
class Connector(connector_id: str, geometry_ref: GeometryRef, name: Optional[str] = None)
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import Connector`

## Description

Semantic datum frame anchored to a geometry sub-element (Face/Edge/Vertex).

The connector wraps a QL-selected sub-shape.  The Placement is derived
from the geometry at solve/translate time, not stored directly.
