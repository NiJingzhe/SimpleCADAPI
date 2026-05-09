# helical_sweep_rsolid

## API Definition

```python
def helical_sweep_rsolid(profile: Wire, pitch: float, height: float, radius: float, center: Tuple[float, float, float] = (0, 0, 0), dir: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

*Source: operations.py*

## Description

Create a solid by sweeping a profile along a helical path.
