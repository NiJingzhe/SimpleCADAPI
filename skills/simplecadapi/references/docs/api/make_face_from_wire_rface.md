# make_face_from_wire_rface

## API Definition

```python
def make_face_from_wire_rface(
    wire: Wire,
    normal: Tuple[float, float, float] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_face_from_wire_rface`

## Description

Create a face from a closed wire. Existing proven Edge topology tags on the
wire are copied to corresponding Face boundary Edges. `tag_prefix` optionally
adds the Face tag `<tag_prefix>.face`.
