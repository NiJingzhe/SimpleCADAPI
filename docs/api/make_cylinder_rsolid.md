# make_cylinder_rsolid

## API Definition

```python
def make_cylinder_rsolid(
    radius: ScalarLike,
    height: ScalarLike,
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

- top-level: `from simplecadapi import make_cylinder_rsolid`

## Description

Create a native cylinder solid. The kernel-backed output roles are:

- `cylinder.start`, `cylinder.end`, and `cylinder.side` for Faces.
- `cylinder.start_boundary`, `cylinder.end_boundary`, and `cylinder.seam` for Edges.

The role tag arguments attach tags to those exact roles.
`tag_prefix="shaft"` creates the topology tag prefix `shaft`: the cap and
lateral Faces receive `shaft.face.start`, `shaft.face.end`, and
`shaft.face.side`; their boundary Edges inherit the corresponding Face tags.
The three native Edge roles additionally receive `shaft.edge.start`,
`shaft.edge.end`, and `shaft.edge.seam`.

Topology tag prefixes must be supplied while creating the profile or feature. The implementation
uses OCC primitive witnesses and exact incident topology, not face or edge
enumeration, area, normal, or position heuristics. Use QL relation/set queries
to disambiguate an Edge shared by two tagged Faces, for example
`Q.edges().incident_to(face_a, face_b, distinct=True)` or
`face_a.shared_boundary(face_b)`.
