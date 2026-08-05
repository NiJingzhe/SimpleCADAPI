# render_region_rpath

## API Definition

```python
def render_region_rpath(model_or_path: BRepModel | TopoDS_Shape | str | Path, entity_ids: Sequence[str], output_path: str | Path, *, neighborhood_depth: int = 0, title: str = 'Highlighted BREP region', views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS, image_size: tuple[float, float] = (18.0, 12.0), dpi: int = 180, linear_deflection: float = 0.12, angular_deflection: float = 0.18, edge_samples: int = 96, highlight_edge_width: float = 6.0, highlight_point_size: float = 18.0) -> Path
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_region_rpath(...)`; unavailable inside GraphSession/@model

## Description

Highlight stable entities and their optional topology neighborhood.
