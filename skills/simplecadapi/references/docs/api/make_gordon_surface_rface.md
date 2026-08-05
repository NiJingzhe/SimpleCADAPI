# make_gordon_surface_rface

## API Definition

```python
def make_gordon_surface_rface(profiles: Sequence[Edge], guides: Sequence[Edge], *, tolerance: float = 0.001, tag_prefix: Optional[str] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_gordon_surface_rface`

## Description

Create a Gordon Face from intersecting profile and guide edge networks.
