# cut_rsolidlist

## API Definition

```python
def cut_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]
```

*Source: operations.py*

## Description

Compute the boolean difference of solids.

All boolean operations (union/cut/intersect) accept a mix of Solid and
sequences; results are always returned as a list of Solid.
`cut_rsolidlist(base, [tool_a, tool_b])` is valid input.
If an earlier union returned multiple solids, keep that list and process each
solid intentionally instead of collapsing it to `result[0]` without proof.
If a later step truly requires one solid, first verify `len(results) == 1`.
When a preceding union produced multiple tangent-only solids, adjust the part
placement so the intended bodies overlap slightly, re-run the union, and only
then unwrap the single result.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing; the first solid is the base, the rest are subtracted in order.

## Returns

List[Solid]: A list containing the cut result solid, or an empty list when
there is no valid input. The result is returned as a list for consistency
with other boolean operations.

## Examples

### Example 1
```python
body = make_box_rsolid(12, 4, 4, bottom_face_center=(0, 0, 0))
slot = make_box_rsolid(2, 2, 6, bottom_face_center=(2, 1, -1))
relief = make_cylinder_rsolid(radius=0.8, height=6, center=(8, 2, 2))
```

### Example 2
```python
results = cut_rsolidlist(body, [slot, relief])
print(f"Cut result count: {len(results)}")
```

### Example 3
```python
# If a previous union returned multiple solids, keep the list and cut each part.
tangent_parts = union_rsolidlist(
    body,
    [
        make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0)),
        make_sphere_rsolid(2.0, center=(14.0, 2.0, 2.0)),
    ],
)
trimmed_parts = []
for part in tangent_parts:
    trimmed_parts.extend(cut_rsolidlist(part, [slot, relief]))
```
