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

Create a native cone or frustum. The kernel-backed Face roles are `cone.start`,
`cone.end`, and `cone.side`. The Edge roles are `cone.start_boundary`,
`cone.end_boundary`, and `cone.seam`.

For a pointed cone (`top_radius=0`), no top cap exists, so `cone.end` is absent
and requesting `end_face_tag` fails. `cone.end_boundary` remains available as
the kernel's degenerate apex Edge. A frustum (`top_radius>0`) has all six roles.

The role tag arguments attach tags to exact roles. `result_tag` targets the
Solid. `tag_prefix="adapter"` creates `adapter.solid`, the
Face tags `adapter.face.start`, `adapter.face.end` when present, and
`adapter.face.side`, plus `adapter.edge.start`, `adapter.edge.end`, and
`adapter.edge.seam`.

All roles and topology tags use direct OCC Cone witnesses. They are not inferred from
topology enumeration, size, normal, or position.
