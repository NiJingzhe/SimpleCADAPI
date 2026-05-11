# Scalar Field Surface Serialization

`make_field_surface_rsolid(...)` is a canonical replayable operation when its input field is a `simplecadapi.field.ScalarField` tree.

It differs from other primitive operations because the node stores both:

1. normal operation parameters, such as `bounds`, `resolution`, and `iso`
2. a recursive scalar-field expression tree in `params.field_tree`

## Recommended source pattern

Use `scad.field.*_rscalarfield` builders, not arbitrary Python callables:

```python
import simplecadapi as scad

field = scad.field.smooth_subtract_rscalarfield(
    scad.field.make_sphere_rscalarfield((0, 0, 0), 1.0),
    scad.field.make_box_rscalarfield((0.3, 0, 0), (0.8, 0.8, 0.8)),
    k=0.12,
)

with scad.GraphSession() as session:
    solid = scad.make_field_surface_rsolid(
        field,
        bounds=((-1.2, -1.2, -1.2), (1.2, 1.2, 1.2)),
        resolution=(24, 24, 24),
        iso=0.0,
        cap_bounds=True,
    )
```

## Serialized operation node

The graph node looks like:

```json
{
  "op": "make_field_surface_rsolid",
  "params": {
    "bounds": {
      "min": [-1.2, -1.2, -1.2],
      "max": [1.2, 1.2, 1.2]
    },
    "resolution": [24.0, 24.0, 24.0],
    "iso": 0.0,
    "cap_bounds": true,
    "field_serialization_mode": "scalar_field",
    "field_tree": {
      "op": "smooth_subtract",
      "params": {"k": 0.12},
      "children": [
        {
          "op": "sphere",
          "params": {
            "center": [0.0, 0.0, 0.0],
            "radius": 1.0
          },
          "children": []
        },
        {
          "op": "box",
          "params": {
            "center": [0.3, 0.0, 0.0],
            "size": [0.8, 0.8, 0.8]
          },
          "children": []
        }
      ]
    }
  },
  "inputs": [],
  "output_count": 1
}
```

Replay effect:

1. Read `params.field_tree`.
2. Rebuild a `ScalarField` via `deserialize_scalar_field(field_tree)`.
3. Call:

```python
make_field_surface_rsolid(
    field,
    bounds=(params["bounds"]["min"], params["bounds"]["max"]),
    resolution=params["resolution"],
    iso=params["iso"],
    cap_bounds=params["cap_bounds"],
)
```

## Base params

| Param | JSON shape | Replay meaning |
| --- | --- | --- |
| `bounds` | `{ "min": [x,y,z], "max": [x,y,z] }` | Sampling domain for isosurface extraction |
| `resolution` | `[nx, ny, nz]` | Sampling grid resolution; replay coerces values to `int` |
| `iso` | number | Isosurface value |
| `cap_bounds` | bool | Whether field was clipped to bounds before meshing |
| `field_serialization_mode` | string | `scalar_field` or `opaque_callable` |
| `field_tree` | object | Recursive field tree, present only in `scalar_field` mode |
| `field_callable_repr` | string | Debug-only callable representation, present only in `opaque_callable` mode |

## `field_tree` shape

Every field tree node has:

```json
{
  "op": "sphere",
  "params": {...},
  "children": []
}
```

| Field | Meaning |
| --- | --- |
| `op` | Scalar field operation name |
| `params` | Operation-local parameters |
| `children` | Child scalar-field nodes |

## Supported field tree operations

### Leaf field ops

| `op` | Params | Source builder |
| --- | --- | --- |
| `sphere` | `center`, `radius` | `make_sphere_rscalarfield(center, radius)` |
| `ellipsoid` | `center`, `radii` | `make_ellipsoid_rscalarfield(center, radii)` |
| `box` | `center`, `size` | `make_box_rscalarfield(center, size)` |
| `capsule` | `p0`, `p1`, `radius` | `make_capsule_rscalarfield(p0, p1, radius)` |

### CSG field ops

| `op` | Params | Children | Source builder |
| --- | --- | --- | --- |
| `union` | `{}` | 1+ | `union_rscalarfield(*fields)` |
| `intersect` | `{}` | 1+ | `intersect_rscalarfield(*fields)` |
| `subtract` | `{}` | 2 | `subtract_rscalarfield(a, b)` |
| `smooth_union` | `k` | 2 | `smooth_union_rscalarfield(a, b, k)` |
| `smooth_subtract` | `k` | 2 | `smooth_subtract_rscalarfield(a, b, k)` |

### Transform field ops

| `op` | Params | Children | Source builder |
| --- | --- | --- | --- |
| `translate` | `offset` | 1 | `translate_rscalarfield(field, offset)` |
| `scale` | `factors` | 1 | `scale_rscalarfield(field, factors)` |
| `rotate` | `axis`, `angle` | 1 | `rotate_rscalarfield(field, axis, angle_degrees)` |

## Opaque callable mode

If the source passes a plain Python callable:

```python
solid = scad.make_field_surface_rsolid(
    lambda x, y, z: x*x + y*y + z*z - 1.0,
    bounds=((-1, -1, -1), (1, 1, 1)),
)
```

The node records only:

```json
{
  "field_serialization_mode": "opaque_callable",
  "field_callable_repr": "<function ...>"
}
```

Replay effect: replay raises an error. Python callables are not serialized as executable code.

Use a `ScalarField` tree whenever a field surface must be saved and replayed.

## Interaction with `cap_bounds`

At build time, if `cap_bounds=True`, the runtime clips the field to the sampling bounds before meshing. The exported `field_tree` remains the original user-provided field, and `cap_bounds` is stored separately. Replay applies the same cap behavior again by calling `make_field_surface_rsolid(..., cap_bounds=True)`.

## Metadata

The runtime solid also receives a `field_report` metadata object with diagnostic information such as sampled min/max values, triangle count, and shell closure. This report is runtime metadata, not the source of truth for replay. Replay uses `params` and `field_tree`.
