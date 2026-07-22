# solids

## API Definition

```python
def solids() -> ShapeSelector
```

*Source: ql.py*

## Import Surface

- submodule: `from simplecadapi import ql`

## Description

Create a serializable selector over Solid topology. Solid selectors can be
traversed to boundary Edges and combined with `intersection(...)` or
`shared_boundary(...)` to find topology common to two named Solid selectors.
