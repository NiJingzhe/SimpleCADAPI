# ConnectorAnchor

## Class Definition

```python
class ConnectorAnchor(anchor_kind: str, geometry_ref: Optional[GeometryRef] = None, placement: Optional[Placement] = None, source_component_id: Optional[str] = None, source_connector_id: Optional[str] = None, offset: Optional[Placement] = None)
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import ConnectorAnchor`

## Description

Serializable source for a connector datum frame.

Supported `anchor_kind` values are `geometry`, `placement`, and `forwarded`.
