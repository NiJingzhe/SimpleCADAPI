# constrain_distance_rassembly

## API Definition

```python
def constrain_distance_rassembly(assembly: Assembly, reference: PointAnchor, moving: PointAnchor, distance: float, fallback_axis: AxisLike = 'x') -> Assembly
```

*Source: constraints.py*

## Description

Type-2 mapping: add a point-distance constraint and return a new assembly.
