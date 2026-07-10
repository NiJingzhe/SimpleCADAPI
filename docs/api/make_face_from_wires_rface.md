# make_face_from_wires_rface

## API Definition

```python
def make_face_from_wires_rface(outer_wire: Wire, inner_wires: Sequence[Wire], normal: Tuple[float, float, float] = (0, 0, 1)) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_face_from_wires_rface`

## Description

Create a face from one outer closed wire and optional inner closed wires.
