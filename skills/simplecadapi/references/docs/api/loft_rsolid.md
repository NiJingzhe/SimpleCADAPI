# loft_rsolid

## API Definition

```python
def loft_rsolid(
    profiles: List[Wire],
    ruled: bool = False,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import loft_rsolid`

## Description

Create a solid by lofting multiple profiles. Kernel history assigns
`loft.start`, `loft.end`, and `loft.side` roles. Start and end tags require one
proven face each; side tags apply to all proven side faces. The generic
`output_tags` mapping accepts those full role names. `result_tag` targets the
solid. Recorded assignments are replayable semantic nodes.
