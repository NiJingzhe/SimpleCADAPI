# render_entity_kind_maps_rpath

## API Definition

```python
def render_entity_kind_maps_rpath(model_or_path, entity_ids, output_dir, *, title='BREP entity map', views=DEFAULT_VIEWS, image_size=(18.0, 12.0), dpi=180, linear_deflection=0.12, angular_deflection=0.18, edge_samples=96, context_opacity=1.0, highlight_edge_width=6.0, highlight_point_size=18.0, label_mode='legend', max_callouts=4, legend_columns=3) -> dict[str, Path]
```

*Source: inspect/brep/render.py*

## Import Surface

```python
from simplecadapi.inspect import brep
brep.render_entity_kind_maps_rpath(model, ["face:0", "edge:0", "vertex:0"], "out/maps")
```

## Description

Resolve a mixed stable-entity selection and render independent maps for faces, edges, and vertices. Empty kinds are omitted. Files are written as `face-map.png`, `edge-map.png`, and `vertex-map.png` below `output_dir`.

`highlight_edge_width` and `highlight_point_size` make edge and vertex evidence more prominent without changing the underlying BREP geometry.
