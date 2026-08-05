# make_surface_patch_rface

## API Definition

```python
def make_surface_patch_rface(boundaries: Sequence[SurfaceBoundary], *, points: Sequence[Sequence[float]] = (), settings: Optional[SurfaceFillingSettings] = None, holes: Sequence[Wire] = (), tag_prefix: Optional[str] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_surface_patch_rface`

## Description

Fill a constrained boundary network into one Face, optionally with holes.
