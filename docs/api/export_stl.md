# export_stl

## API Definition

```python
def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None
```

*Source: operations.py*

## Description

Export shapes to STL.

Use this function when you want to export one solid or many solids/faces into
the same STL file. Passing `List[Solid]` is valid and often preferred when a
previous boolean operation returned multiple solids.

## Parameters

### shapes

- **Description**: A single Solid or Face, or any nested sequence of Solid/Face. Lists of Solid are supported directly, including list results returned by boolean operations.

### filename

- **Description**: Output STL file path.

## Returns

None: Writes the provided shapes into one STL file.

## Examples

### Example 1
```python
main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
body_parts = union_rsolidlist(main_body, [left_cap, right_cap])
```

### Example 2
```python
# Export the list result directly.
export_stl(body_parts, "rounded_bar.stl")
```
