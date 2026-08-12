# fit_face_analytic_rdescriptor

```python
fit_face_analytic_rdescriptor(model_or_path, face_id: str, *, tolerance: float = 1e-3, u_samples: int = 11, v_samples: int = 11) -> dict
```

Inspection namespace. Samples one indexed BREP face, fits plane, sphere,
cylinder, and cone carriers, and ranks them by residual error. Use
`accepted=True` and the reported residuals as geometric evidence; the result
does not recover or assert feature history.
