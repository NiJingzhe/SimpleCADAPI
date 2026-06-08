# cut_rsolid

## API Definition

```python
def cut_rsolid(*solids: Union[Solid, Sequence[Solid]], skip_non_intersecting: bool = True) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import cut_rsolid`

## Description

Compute the boolean difference of solids.

Accepts a base solid followed by one or more tool solids, including nested
sequences, and returns a single `Solid`.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing; the first solid is the base, the rest are subtracted in order.

### skip_non_intersecting

- **Description**: When True, tools with no meaningful intersection are ignored for interactive convenience. Graph replay records this flag and should use False for strict diagnostic workflows.

## Returns

Solid: The cut result solid.
