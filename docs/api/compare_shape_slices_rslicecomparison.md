# compare_shape_slices_rslicecomparison

## API Definition

```python
def compare_shape_slices_rslicecomparison(target: TopoDS_Shape, candidate: TopoDS_Shape, *, slices: Sequence[SliceSpec] | None = None, samples: tuple[int, int] = (91, 121), classification_tolerance: float = 1e-08, margin_ratio: float = 0.03, output_path: str | Path | None = None, target_name: str | None = None, candidate_name: str | None = None, dpi: int = 180) -> SliceComparison
```

*Source: inspect/brep/slices.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_shape_slices_rslicecomparison(...)`; unavailable inside GraphSession/@model

## Description

Compare occupancy on physical slices and optionally render an XOR image.

This is a visual diagnostic, not a replacement for bidirectional Boolean
comparison. Keep sample counts moderate because exact BREP classification
is intentionally used for every point.
