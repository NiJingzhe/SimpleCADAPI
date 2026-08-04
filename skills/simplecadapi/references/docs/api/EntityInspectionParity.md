# EntityInspectionParity

## Class Definition

```python
class EntityInspectionParity(source: str | None, valid: bool, issues: tuple[str, ...], checked_faces: int, checked_edges: int, degenerate_edges: int)
```

*Source: inspect/brep/parity.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.EntityInspectionParity(...)`; unavailable inside GraphSession/@model

## Description

Result of checking stable entity output against a BRepInspection report.
