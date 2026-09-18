# placement_ticks

## API Definition

```python
def placement_ticks(value: Any) -> Dict[str, Any]
```

*Source: product/placement.py*

## Import Surface

- submodule: `from simplecadapi.product/placement import placement_ticks`

## Description

Return the integer-tick identity form of a placement frame.

Tick frames are the only representation that is hashed or persisted:
they are exact integers, so canonical JSON bytes and content hashes are
stable across save/load cycles regardless of floating-point noise.  The
stored ``z_axis`` is authoritative (derived once from ``x_axis ×
y_axis`` by :class:`Placement` at write time) and is never recomputed.
