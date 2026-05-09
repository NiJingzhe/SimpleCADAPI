# union_rsolid

## API Definition

```python
def union_rsolid(*solids: Union[Solid, Sequence[Solid]], clean: bool = True, glue: bool = _DEFAULT_UNION_GLUE, tol: Optional[float] = None) -> Solid
```

*Source: operations.py*

## Description

Compute the boolean union and return one solid.

Accepts standalone `Solid` objects, lists of `Solid`, and nested sequences,
but always returns exactly one `Solid`. If the kernel cannot produce
exactly one solid result, the API raises a clear error instead of
returning multiple pieces.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing.

### clean

- **Description**: Unify same-domain faces and remove splitter edges when possible.

### glue

- **Description**: Enable OCC glue mode for touching or partially overlapping inputs. Defaults to True for SimpleCAD's standard union behavior.

### tol

- **Description**: Optional fuzzy-boolean tolerance used by the OCC union kernel. When omitted, SimpleCAD chooses a conservative scale-aware tolerance.

## Returns

Solid: The merged union result.

## Examples

```python
body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
rib = make_box_rsolid(2, 4, 4, bottom_face_center=(4, 0, 0))
merged = union_rsolid(body, rib)
print(merged.get_volume())
```
