# BRepInspection

## Class Definition

```python
class BRepInspection(source: str | None, valid: bool, counts: dict[str, int], bounding_box: list[float], volume: float, surface_area: float, center_of_mass: list[float], surface_type_counts: dict[str, int], edge_type_counts: dict[str, int], faces: list[dict[str, Any]], edges: list[dict[str, Any]])
```

*Source: inspect/brep/inspect.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.BRepInspection(...)`; unavailable inside GraphSession/@model

## Description

JSON-serializable geometry and topology facts for one BREP.
