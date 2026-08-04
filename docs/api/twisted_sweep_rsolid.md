# twisted_sweep_rsolid

## API Definition

```python
def twisted_sweep_rsolid(profile: Face, distance: ScalarLike, twist_angle: ScalarLike, axis: Tuple[float, float, float] = (0.0, 0.0, 1.0), origin: Tuple[float, float, float] = (0.0, 0.0, 0.0), *, guide_radius: ScalarLike = 1.0, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import twisted_sweep_rsolid`

## Description

Sweep a planar profile along a straight axis with linear rotation.

``twist_angle`` is the signed total rotation in degrees. The operation uses
a cylindrical auxiliary spine to define a continuous rotation law, yielding
one continuous side face per profile edge instead of a segmented ruled loft.
