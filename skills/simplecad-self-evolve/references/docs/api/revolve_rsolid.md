# revolve_rsolid

## API Definition

```python
def revolve_rsolid(profile: Union[Wire, Face], axis: Tuple[float, float, float] = (0, 0, 1), angle: float = 360, origin: Tuple[float, float, float] = (0, 0, 0)) -> Solid
```

*Source: operations.py*

## Description

Create a solid by revolving a profile around an axis.
