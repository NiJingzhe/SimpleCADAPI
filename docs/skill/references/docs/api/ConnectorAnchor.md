# ConnectorAnchor

## Class Definition

```python
class ConnectorAnchor(anchor_kind: str, geometry_ref: Optional[GeometryRef] = None, placement: Optional[Placement] = None)
```

*Source: product/connector.py*

## Import Surface

- top-level: `from simplecadapi import ConnectorAnchor`

## Description

Serializable source for a connector datum frame.

Supported ``anchor_kind`` values are ``geometry`` and ``placement``.
Assembly public exposure is modeled separately by ``PublicConnectorRef``.
