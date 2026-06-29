# export_stl

## API Definition

```python
def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import export_stl`

## Description

Export shapes to STL.

Use this function when you want to export one compound, solid, or face into
the same STL file. Passing `List[Solid]` is valid for pattern outputs or
explicit shape collections. Boolean operations return a single `Solid`.

## Parameters

### shapes

- **Description**: A single Compound, Solid, or Face, or any nested sequence of those. Lists of Solid are supported directly, including pattern or explicitly collected multi-shape results.

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
body = union_rsolid(main_body, [left_cap, right_cap])
```

### Example 2
```python
export_stl(body, "rounded_bar.stl")
```
