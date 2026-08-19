# inspect_section_rdescriptor

## API Definition

```python
def inspect_section_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, origin: Sequence[float], normal: Sequence[float], tolerance: float = 1e-07, samples_per_edge: int = 16, connection_tolerance: float | None = None, compact: bool = False, face_ids: Sequence[str] | None = None) -> dict[str, Any]
```

*Source: inspect/brep/queries.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_section_rdescriptor(...)`; unavailable inside GraphSession

## Description

Intersect a model or selected faces with a plane and assemble contours.
