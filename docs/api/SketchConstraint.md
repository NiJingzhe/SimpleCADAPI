# SketchConstraint

## Class Definition

```python
class SketchConstraint(constraint_id: str, kind: str, targets: Tuple[Dict[str, Any], ...], value: Any = None, driving: bool = True, metadata: Dict[str, Any] = field(default_factory=dict))
```

*Source: sketch.py*

## Import Surface

- top-level: `from simplecadapi import SketchConstraint`

## Description

Serializable constraint inside a declarative sketch.
