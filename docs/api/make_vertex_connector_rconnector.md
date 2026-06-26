# make_vertex_connector_rconnector

## API Definition

```python
def make_vertex_connector_rconnector(connector_id: str, vertex: Vertex, name: Optional[str] = None, flip: bool = False) -> Connector
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_vertex_connector_rconnector`

## Description

Create a connector anchored to a Vertex.

Origin is the vertex point; axes are identity.
flip has no effect on vertex connectors (no direction).
