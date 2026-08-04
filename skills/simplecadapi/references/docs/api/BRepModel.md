# BRepModel

## Class Definition

```python
class BRepModel(root: TopoDS_Shape, source: str | None, bodies: tuple[TopoDS_Solid, ...], faces: tuple[TopoDS_Face, ...], edges: tuple[TopoDS_Edge, ...], vertices: tuple[TopoDS_Vertex, ...], adjacency: dict[str, set[str]])
```

*Source: inspect/brep/model.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.BRepModel(...)`; unavailable inside GraphSession/@model

## Description

One BREP with deterministic zero-based topology ids and incidence data.
