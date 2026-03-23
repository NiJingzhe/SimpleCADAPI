# union_rsolidlist

## API Definition

```python
def union_rsolidlist(
    *solids: Union[Solid, Sequence[Solid]],
    clean: bool = True,
    glue: bool = True,
    tol: Optional[float] = None,
) -> List[Solid]
```

*Source: operations.py*

## Description

Compute the boolean union of one or more solids.

All boolean operations (union/cut/intersect) accept a mix of Solid and
sequences; results are always returned as a list of Solid.
Keep the list result unless you have explicitly verified `len(result) == 1`.
SimpleCAD enables glue mode by default and applies a conservative internal fuzzy
tolerance, so normal modeling code does not need to tune boolean parameters.
By default this follows CadQuery's union flow: perform one OCC fuse across the
input solids, then call `clean()` to unify same-domain faces when possible.
Touching-but-not-intersecting inputs can legitimately return multiple solids.
If that happens, keep using the list: pass it directly into later union calls,
or iterate over the solids for later cut/intersect steps.
When the returned solids are still separated by more than the active tolerance,
SimpleCAD prints a stdout warning explaining that the objects do not touch and
that their gap exceeds `tol`.
If you truly need exactly one merged solid, you must check the list length
before using `result[0]`.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing.

### clean

- **Description**: Call CadQuery's `clean()` after the union to remove splitter edges and unify same-domain faces when possible.

### glue

- **Description**: Enable OCC glue mode for touching or partially overlapping inputs. Defaults to `True` for SimpleCAD's standard union behavior.

### tol

- **Description**: Optional fuzzy-boolean tolerance passed to the OCC union kernel. When omitted, SimpleCAD derives a conservative scale-aware value automatically.

## Returns

List[Solid]: Resulting solids after union attempts. Solids that can be fused
are merged; disjoint or tangent-only contacts remain separate, so the
list may contain multiple solids.

## Examples

### Example 1
```python
# Rounded-bar style input: end caps only touch the center body.
main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
```

### Example 2
```python
body_parts = union_rsolidlist(main_body, [left_cap, right_cap])
print(f"Union result count: {len(body_parts)}")
# This is acceptable: tangent-only contact can stay as multiple solids.
for solid in body_parts:
    print(f"- volume: {solid.get_volume():.6f}")
```

### Example 3
```python
# Keep using the returned list in later boolean steps.
rib = make_box_rsolid(2, 4, 4, bottom_face_center=(4, 0, 0))
combined_parts = union_rsolidlist(body_parts, rib)
print(f"Combined result count: {len(combined_parts)}")
```

### Example 4
```python
# Only unwrap to one solid after an explicit length check.
left_cap_embedded = make_sphere_rsolid(2.0, center=(-1.8, 2.0, 2.0))
right_cap_embedded = make_sphere_rsolid(2.0, center=(11.8, 2.0, 2.0))
merged = union_rsolidlist(main_body, [left_cap_embedded, right_cap_embedded])
if len(merged) != 1:
    raise ValueError(
        "Adjust part placement so each cap overlaps the body slightly before "
        "using merged[0]."
    )
final_body = merged[0]
```
