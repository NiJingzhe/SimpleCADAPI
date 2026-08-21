# make_cylinder_rsolid

## API Definition

```python
def make_cylinder_rsolid(radius: ScalarLike, height: ScalarLike, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1), *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_face_tag: Optional[str] = None, start_edge_tag: Optional[str] = None, end_edge_tag: Optional[str] = None, seam_edge_tag: Optional[str] = None) -> Solid
```

*Source: _operators_geometry.py*

## Import Surface

- top-level: `from simplecadapi import make_cylinder_rsolid`

## Description

Create a cylinder with native kernel-backed Face and Edge topology tags.

The cylinder extends ``height`` along ``axis`` from the bottom face.

## Parameters

### radius

- **Description**: Cylinder radius.

### height

- **Description**: Cylinder length along ``axis``.

### bottom_face_center

- **Description**: Geometric center of the cylinder's bottom (start) face in the current coordinate system; the solid extends the full ``height`` along ``axis`` from this point.

### axis

- **Description**: Direction of the cylinder axis in the current coordinate system.
