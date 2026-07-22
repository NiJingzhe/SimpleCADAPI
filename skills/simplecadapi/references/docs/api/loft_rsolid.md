# loft_rsolid

## API Definition

```python
def loft_rsolid(
    profiles: List[Wire],
    ruled: bool = False,
    *,
    tracking_policy: TrackingPolicy | str = TrackingPolicy.FULL,
    tag_prefix: Optional[str] = None,
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
proven face each; side tags apply to all proven side faces. `result_tag` targets
the solid. Recorded assignments are replayable semantic nodes.

`TrackingPolicy.FULL` is the default and preserves complete kernel topology
history. `TrackingPolicy.GRAPH` skips topology-history queries while still
recording and replaying the `make_loft_rsolid` graph node. In `GRAPH` mode,
`result_tag` remains available, but face-role tags and `tag_prefix` require
`FULL` tracking.
