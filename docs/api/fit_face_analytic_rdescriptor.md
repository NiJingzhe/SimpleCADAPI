# fit_face_analytic_rdescriptor

## API Definition

```python
def fit_face_analytic_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, face_id: str, *, tolerance: float = 0.001, u_samples: int = 11, v_samples: int = 11) -> dict[str, Any]
```

*Source: inspect/brep/fitting.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.fit_face_analytic_rdescriptor(...)`; unavailable inside GraphSession

## Description

Fit plane, sphere, cylinder, and cone carriers to one indexed face.

Results are evidence, not feature-history assertions. Callers should use
``accepted`` and residuals instead of assuming the best candidate is exact.
The report includes every fitted candidate and the selected carrier
parameters.
