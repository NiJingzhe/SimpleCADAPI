# make_cone_rsolid

## API Definition

```python
def make_cone_rsolid(
    bottom_radius: ScalarLike,
    height: ScalarLike,
    top_radius: ScalarLike = 0.0,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_face_tag: Optional[str] = None,
    start_edge_tag: Optional[str] = None,
    end_edge_tag: Optional[str] = None,
    seam_edge_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_cone_rsolid`

## Description

Create a native cone or frustum with direct kernel-backed `cone.start`,
`cone.end`, and `cone.side` Face roles and `cone.start_boundary`,
`cone.end_boundary`, and `cone.seam` Edge roles.

A pointed cone (`top_radius=0`) has no `cone.end` Face, so requesting that role
fails. Its `cone.end_boundary` is the kernel's degenerate apex Edge. A frustum
has all six roles. `tag_prefix="adapter"` creates corresponding
`adapter.face.*` and `adapter.edge.*` topology-identity tags; use the role tag
arguments for role assignments.
