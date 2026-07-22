# extrude_rsolid

## API Definition

```python
def extrude_rsolid(
    profile: Union[Wire, Face],
    direction: Tuple[float, float, float],
    distance: ScalarLike,
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

- top-level: `from simplecadapi import extrude_rsolid`

## Description

Create a solid by extruding a profile. Kernel history assigns the output roles
`extrusion.start`, `extrusion.end`, and `extrusion.side`. Use the role tag
arguments to attach tags to those exact role sets.

Use creation-time profile topology tags (`tag_prefix` and `edge_tags`) when
durable feature Face/Edge identity is required. A tagged profile Edge yields a
corresponding `<tag_prefix>.face.side.<edge_tag>` when OCC proves the generated
side Face. Tagged Faces expose their effective tags to boundary Edge queries; use QL
`incident_to(..., distinct=True)` or `shared_boundary(...)` to disambiguate
an Edge by its two neighboring Faces.

Start and end roles require exactly one proven face. The side role requires one
or more proven faces and tags all of them. Missing, ambiguous, or unsupported
roles fail the whole operation instead of returning an untagged result.

`result_tag` attaches a local tag to the resulting solid. In a `GraphSession`,
all requested tags lower to replayable `apply_tag_rselection` semantic nodes;
they are not stored as geometry parameters.

Topology tags produced by `tag_prefix` remain directly queryable after
booleans when OCC provides a complete preserved or modified Face history. The
result binding retains the original semantic binding ID and source topology ID;
new boundary faces do not inherit the topology tag.
