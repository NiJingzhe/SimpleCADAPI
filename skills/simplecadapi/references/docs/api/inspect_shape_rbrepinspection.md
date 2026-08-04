# inspect_shape_rbrepinspection

## API Definition

```python
def inspect_shape_rbrepinspection(shape: TopoDS_Shape, *, source: str | Path | None = None) -> BRepInspection
```

*Source: inspect/brep/inspect.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_shape_rbrepinspection(...)`; unavailable inside GraphSession/@model

## Description

Inspect one imported shape without relying on STEP entity numbering.
