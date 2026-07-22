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
`extrusion.start`, `extrusion.end`, and `extrusion.side`. Use the semantic role
tag arguments to attach user tags to those exact role sets.

When `tag_prefix` is supplied, profile Edge tags are recommended at creation
time through the profile API (`edge_tags` and `tag_prefix`). The feature
produces `<tag_prefix>.face.start`, `<tag_prefix>.face.end`, and one
`<tag_prefix>.face.side.<profile_edge_tag>` for each kernel-proven profile Edge.
The cap Face tags are inherited by their boundary Edges, so an exact Edge
can be selected from two tagged neighboring Faces with QL `incident_to` or
`shared_boundary` rather than an enumeration index.

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
