# index_shape_rbrepmodel

## API Definition

```python
def index_shape_rbrepmodel(shape: TopoDS_Shape, *, source: str | Path | None = None) -> BRepModel
```

*Source: inspect/brep/model.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.index_shape_rbrepmodel(...)`; unavailable inside GraphSession/@model

## Description

Build stable entity maps for one in-memory OCP shape.
