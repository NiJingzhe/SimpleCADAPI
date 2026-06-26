# SketchSolveResult

## Class Definition

```python
class SketchSolveResult(sketch_id: str, status: str, dof: int, residual_norm: float, iterations: int, solved_points: Dict[str, Tuple[float, float]], solved_scalars: Dict[str, float], diagnostics: Tuple[SketchConstraintDiagnostic, ...] = ())
```

*Source: sketch.py*

## Import Surface

- top-level: `from simplecadapi import SketchSolveResult`

## Description

Result of solving a declarative sketch.
