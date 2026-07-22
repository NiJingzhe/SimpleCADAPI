# revolve_rsolid

## API Definition

```python
def revolve_rsolid(
    profile: Union[Wire, Face],
    axis: Tuple[float, float, float] = (0, 0, 1),
    angle: ScalarLike = 360,
    origin: Tuple[float, float, float] = (0, 0, 0),
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import revolve_rsolid`

## Description

Create a solid by revolving a profile around an axis. Kernel history assigns
`revolution.start`, `revolution.end`, and `revolution.side` output roles.

Start and end roles require exactly one proven face; side tags apply to every
proven side face. A full 360-degree revolve normally has no separate start or end
face, so requesting either cap tag raises a capability error rather than guessing.
`result_tag` tags the resulting solid. Role tags are replayable semantic nodes.
