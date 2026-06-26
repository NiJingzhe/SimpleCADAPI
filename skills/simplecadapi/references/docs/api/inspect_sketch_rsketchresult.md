# inspect_sketch_rsketchresult

## API Definition

```python
def inspect_sketch_rsketchresult(sketch: Sketch, *, require_fully_constrained: bool = False, strict: bool = True, tolerance: float = 1e-07, max_iterations: int = 80) -> SketchSolveResult
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import inspect_sketch_rsketchresult`

## Description

Inspect sketch constraints by running the solver without recording graph nodes.
