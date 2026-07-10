# Connector

## Class Definition

```python
class Connector(connector_id: str, geometry_ref: Optional[GeometryRef] = None, name: Optional[str] = None, anchor: Optional[ConnectorAnchor] = None)
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import Connector`

## Description

Semantic datum frame anchored by geometry, placement, or forwarding.

Geometry connectors derive placement from a selected BREP sub-shape.
Placement connectors store an explicit local datum frame. Forwarded
connectors expose a component connector as an assembly-level public
interface.
