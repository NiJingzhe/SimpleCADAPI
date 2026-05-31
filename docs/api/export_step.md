# export_step

## API Definition

```python
def export_step(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import export_step`

## Description

Export shapes to STEP.

Use this function when you want to export one shape or many shapes into the
same STEP file. Passing `List[Solid]` is valid for pattern outputs or
explicit shape collections. Boolean operations return a single `Solid`.

## Parameters

### shapes

- **Description**: A single exportable shape or any nested sequence of exportable shapes. Lists of Solid are supported directly, including pattern or explicitly collected multi-shape results.

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
body = union_rsolid(main_body, [left_cap, right_cap])
```

### Example 2
```python
export_step(body, "rounded_bar.step")
```
