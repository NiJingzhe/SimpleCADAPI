# extrude_rsolid

## API Definition

```python
def extrude_rsolid(
    profile: Union[Wire, Face],
    direction: Tuple[float, float, float],
    distance: ScalarLike,
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

- top-level: `from simplecadapi import extrude_rsolid`

## Description

Create a solid by extruding a profile. Kernel history assigns the output roles
`extrusion.start`, `extrusion.end`, and `extrusion.side`. Use the named tag
arguments or `output_tags` to attach user semantics to those exact role sets.

Start and end roles require exactly one proven face. The side role requires one
or more proven faces and tags all of them. Missing, ambiguous, or unsupported
roles fail the whole operation instead of returning an untagged result.

`result_tag` attaches a local tag to the resulting solid. In a `GraphSession`,
all requested tags lower to replayable `apply_tag_rselection` semantic nodes;
they are not stored as geometry parameters.
