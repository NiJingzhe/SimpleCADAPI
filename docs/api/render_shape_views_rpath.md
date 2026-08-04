# render_shape_views_rpath

## API Definition

```python
def render_shape_views_rpath(shape: TopoDS_Shape, output_path: str | Path, *, title: str = 'BREP views', views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS, image_size: tuple[float, float] = (18.0, 12.0), dpi: int = 180, linear_deflection: float = 0.12, angular_deflection: float = 0.18, show_brep_edges: bool = True) -> Path
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_shape_views_rpath(...)`; unavailable inside GraphSession/@model

## Description

Render smooth shaded BREP views with true topology edges by default.

``show_brep_edges`` draws exact topological edges sampled from the BREP; it
never exposes the internal triangle edges used by the GPU.
