# sweep_rsolid

## API Definition

```python
def sweep_rsolid(
    profile: Face,
    path: Wire,
    is_frenet: bool = False,
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

- top-level: `from simplecadapi import sweep_rsolid`

## Description

Create a solid by sweeping a profile along a path. Kernel history assigns
`sweep.start`, `sweep.end`, and `sweep.side` roles. Start and end tags require one
proven face each; side tags apply to all proven side faces. `result_tag` targets
the solid, and recorded assignments are replayable semantic nodes.

Profiles with inner wires are rejected because the current PipeShell operation
receives only the outer wire; silently dropping profile holes is not allowed.
