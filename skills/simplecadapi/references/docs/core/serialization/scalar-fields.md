# Scalar Fields / SDF Status

SDF and scalar field modeling are temporarily removed from the supported SimpleCADAPI surface.

Current contract:

- `simplecadapi.field` is not exported.
- `make_field_surface_rsolid` is not exported.
- `*_rscalarfield` APIs are not generated in public API docs.
- `make_field_surface_rsolid` is not a canonical graph op.
- Model JSON replay does not rebuild scalar field surfaces.

Historical payloads or examples that rely on scalar field trees should be treated as unsupported until a new SDF contract is designed.
