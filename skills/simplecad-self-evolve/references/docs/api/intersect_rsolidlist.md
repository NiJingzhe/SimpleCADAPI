# intersect_rsolidlist

## API Definition

```python
def intersect_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]
```

*Source: operations.py*

## Description

Compute the boolean intersection of solids.

All boolean operations (union/cut/intersect) accept a mix of Solid and
sequences; results are always returned as a list of Solid.
`intersect_rsolidlist(body, [clip_a, clip_b])` is valid input.
If an earlier union returned multiple solids, keep that list and intersect
each solid intentionally instead of collapsing it to `result[0]`.
If a later step truly requires one solid, first verify `len(results) == 1`.
When a preceding union produced multiple tangent-only solids, adjust the part
placement so the intended bodies overlap slightly, re-run the union, and only
then unwrap the single result.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing.

## Returns

List[Solid]: A list containing the intersection result, or an empty list if
the solids do not overlap. The result is returned as a list for
consistency with other boolean operations.

## Examples

### Example 1
```python
body = make_box_rsolid(12, 4, 4, bottom_face_center=(0, 0, 0))
clip_a = make_box_rsolid(8, 4, 4, bottom_face_center=(2, 0, 0))
clip_b = make_box_rsolid(6, 6, 6, bottom_face_center=(3, -1, -1))
```

### Example 2
```python
results = intersect_rsolidlist(body, [clip_a, clip_b])
print(f"Intersect result count: {len(results)}")
```

### Example 3
```python
# A previous union may return multiple solids; keep the list and intersect each part.
tangent_parts = union_rsolidlist(
    body,
    [
        make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0)),
        make_sphere_rsolid(2.0, center=(14.0, 2.0, 2.0)),
    ],
)
clipped_parts = []
for part in tangent_parts:
    clipped_parts.extend(intersect_rsolidlist(part, clip_a))
```
