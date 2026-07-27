# twisted_sweep_rsolid

## API Definition

```python
def twisted_sweep_rsolid(
    profile: Face,
    distance: ScalarLike,
    twist_angle: ScalarLike,
    axis: Tuple[float, float, float] = (0.0, 0.0, 1.0),
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    *,
    guide_radius: ScalarLike = 1.0,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import twisted_sweep_rsolid`

## Description

Sweep a planar profile along a straight axis while rotating it linearly by the
signed total `twist_angle` in degrees. The profile must lie at the sweep start,
be planar, and be normal to `axis`.

The OCP implementation uses a one-edge straight spine and a one-edge
cylindrical auxiliary spine. This normally creates one continuous side face per
profile edge rather than splitting every side at intermediate loft sections.
Profiles with inner wires are rejected.

Kernel history assigns `twisted_sweep.start`, `twisted_sweep.end`, and
`twisted_sweep.side` roles. The operation records one canonical
`make_twisted_sweep_rsolid` graph node containing `axis`, `origin`, `distance`,
`twist_angle`, and `guide_radius`; strict replay invokes the same public
operation with the recorded parameters.

`guide_radius` controls only the auxiliary orientation guide and must be a
positive finite value. It does not set the swept profile radius.
