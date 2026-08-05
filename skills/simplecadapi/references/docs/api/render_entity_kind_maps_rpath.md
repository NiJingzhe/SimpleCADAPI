# render_entity_kind_maps_rpath

## API Definition

```python
def render_entity_kind_maps_rpath(model_or_path: BRepModel | TopoDS_Shape | str | Path, entity_ids: Sequence[str], output_dir: str | Path, *, title: str = 'BREP entity map', views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS, image_size: tuple[float, float] = (18.0, 12.0), dpi: int = 180, linear_deflection: float = 0.12, angular_deflection: float = 0.18, edge_samples: int = 96, context_opacity: float = 1.0, highlight_edge_width: float = 6.0, highlight_point_size: float = 18.0, label_mode: Literal['auto', 'callout', 'legend', 'none'] = 'legend', max_callouts: int = 4, legend_columns: int = 3) -> dict[str, Path]
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_entity_kind_maps_rpath(...)`; unavailable inside GraphSession/@model

## Description

Render independent face, edge, and vertex highlight maps.
