# make_placement_rplacement

## API Definition

```python
def make_placement_rplacement(origin: Tuple[float, float, float], x_axis: Tuple[float, float, float] = (1.0, 0.0, 0.0), y_axis: Tuple[float, float, float] = (0.0, 1.0, 0.0)) -> Placement
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_placement_rplacement`

## Description

Create a canonical right-handed component placement.

The placement maps child-local coordinates into parent assembly coordinates
using one representation only: origin plus child x/y axes in parent space.
