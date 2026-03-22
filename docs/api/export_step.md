# export_step

## API Definition

```python
def export_step(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None
```

*Source: operations.py*

## Description

Export shapes to STEP.

Use this function when you want to export one shape or many shapes into the
same STEP file. Passing `List[Solid]` is valid and often preferred when a
previous boolean operation returned multiple solids.

## Parameters

### shapes

- **Description**: A single exportable shape or any nested sequence of exportable shapes. Lists of Solid are supported directly, including list results returned by boolean operations.

### filename

- **Description**: Output STEP file path.

## Returns

None: Writes the provided shapes into one STEP file.

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
# Export the full list directly; no need to collapse to body_parts[0].
export_step(body_parts, "rounded_bar.step")
```
