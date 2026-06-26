# GeometryRef

## Class Definition

```python
class GeometryRef(kind: str, source_node_id: Optional[str], geo_selector: Dict[str, Any], flip: bool = False)
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import GeometryRef`

## Description

Serializable reference to a sub-shape selected via QL.

Wraps the geo_selector fingerprint + source graph node id so the
exact sub-element (Face/Edge/Vertex) can be re-resolved at translation
time or during constraint solving. When flip is True, the derived
placement Z axis is negated.
