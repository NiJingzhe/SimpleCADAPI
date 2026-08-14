# trim_surface_rface

## API Definition

```python
def trim_surface_rface(carrier: Face, outer: Wire, holes: Sequence[Wire] = (), *, tolerance: float = 1e-07, tag_prefix: Optional[str] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import trim_surface_rface`

## Description

Trim a carrier Face with projected 3D boundary wires.
