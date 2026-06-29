# Sketch

## Class Definition

```python
class Sketch(curves: Iterable[Edge | Wire] | None = None, *, name: Optional[str] = None, plane: Any = 'XY', sketch_id: Optional[str] = None)
```

*Source: sketch.py*

## Import Surface

- top-level: `from simplecadapi import Sketch`

## Description

Declarative constrained sketch container.

Use `make_sketch_rsketch(...)`, `add_point_rsketch(...)`,
`add_line_rsketch(...)`, `add_circle_rsketch(...)`, and
`constrain_*_rsketch(...)` as the canonical API for building sketch
profiles. Public sketch construction APIs are functional and return an
updated `Sketch` document. The legacy `curves` constructor remains only for
reading already-built wire/edge containers.
