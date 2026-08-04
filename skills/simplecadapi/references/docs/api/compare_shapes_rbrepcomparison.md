# compare_shapes_rbrepcomparison

## API Definition

```python
def compare_shapes_rbrepcomparison(target: TopoDS_Shape, candidate: TopoDS_Shape, *, target_name: str | None = None, candidate_name: str | None = None, geometric_tolerance: float = 1e-07, boolean_volume_tolerance: float = 1e-09, boolean_fuzzy_tolerance: float | None = None, material_difference_volumes: Sequence[float] | None = None) -> BRepComparison
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_shapes_rbrepcomparison(...)`; unavailable inside GraphSession/@model

## Description

Compare material point sets and geometry-labelled incidence graphs.

Optional precomputed volumes are validated for compatibility but never used
as equality evidence; strict directional cuts are always recomputed.
