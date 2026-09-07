# SketchSolveResult

## Class Definition

```python
class SketchSolveResult(sketch_id: str, status: str, dof: int, residual_norm: float, iterations: int, solved_points: Dict[str, Tuple[float, float]], solved_scalars: Dict[str, float], solved_entities: Dict[str, Dict[str, Any]] = field(default_factory=dict), diagnostics: Tuple[SketchConstraintDiagnostic, ...] = (), backend: str = 'unknown', backend_version: str = 'unknown', backend_status_code: Optional[int] = None)
```

*Source: sketch.py*

## Import Surface

- top-level: `from simplecadapi import SketchSolveResult`

## Description

Backend-neutral result of solving a declarative sketch.
