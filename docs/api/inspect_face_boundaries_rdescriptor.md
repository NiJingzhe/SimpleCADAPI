# inspect_face_boundaries_rdescriptor

## API Definition

```python
def inspect_face_boundaries_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, face_id: str, samples_per_edge: int = 16, compact: bool = False, include_curve_definitions: bool = False, curve_definition_edge_ids: Sequence[str] | None = None, max_total_control_points: int = 256) -> dict[str, Any]
```

*Source: inspect/brep/queries.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_face_boundaries_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Return ordered outer and inner wire occurrences for one stable face id.
