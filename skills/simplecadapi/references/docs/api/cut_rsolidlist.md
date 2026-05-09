# cut_rsolidlist

## API Definition

```python
def cut_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> Solid
```

*Source: operations.py*

## Description

Compute the boolean difference of solids.

Accepts a base solid followed by one or more tool solids, including nested
sequences, and returns a single `Solid`.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing; the first solid is the base, the rest are subtracted in order.

## Returns

Solid: The cut result solid.
