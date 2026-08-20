# Connector

## Class Definition

```python
class Connector(connector_id: str, geometry_ref: Optional[GeometryRef] = None, name: Optional[str] = None, anchor: Optional[ConnectorAnchor] = None)
```

*Source: connector.py*

## Import Surface

- top-level: `from simplecadapi import Connector`

## Description

Semantic datum frame anchored by geometry or an explicit placement.

Assembly public interfaces reference existing component connectors instead
of cloning connectors into the Assembly.
