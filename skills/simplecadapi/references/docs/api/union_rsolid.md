# union_rsolid

## API Definition

```python
def union_rsolid(
    *solids: Union[Solid, Sequence[Solid]],
    clean: bool = True,
    glue: bool = _DEFAULT_UNION_GLUE,
    tol: Optional[float] = None,
    tracking_policy: TrackingPolicy | str = TrackingPolicy.FULL,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import union_rsolid`

## Description

Compute the boolean union and return one manifold solid.

Face-area contact and positive-volume overlap can produce one solid without
artificially embedding either input. Edge-only, vertex-only, and point/curve
tangencies are non-manifold connections and therefore cannot satisfy this API's
single-`Solid` contract.

When `glue=True`, SimpleCAD tries OCC glue optimization first. If that optimized
pass returns multiple solids, it automatically retries the normal fuse algorithm.
Glue is an optimization, not a topology-repair switch.

## Parameters

### solids

- **Description**: One or more Solid objects or sequences of Solid. Nested sequences are flattened before processing.

### clean

- **Description**: Unify same-domain faces and remove splitter edges when possible.

### glue

- **Description**: Try OCC glue optimization first and fall back to normal fuse when necessary. Defaults to `False`. It supports compatible face-touching or coincident topology but cannot repair non-manifold point-, edge-, or tangent-only contact.

### tol

- **Type**: `Optional[float]`
- **Description**: Finite non-negative fuzzy tolerance. It may intentionally bridge a small gap, but it does not make lower-dimensional contact into one manifold solid.

### tracking_policy

- **Description**: `TrackingPolicy.FULL` computes topology history and lineage. `TrackingPolicy.GRAPH` preserves the replayable operation node while omitting history-derived topology lineage.

## Returns

Solid: The merged union result.

## Examples

```python
body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
rib = make_box_rsolid(2, 4, 4, bottom_face_center=(4, 0, 0))
merged = union_rsolid(body, rib)
print(merged.get_volume())
```
