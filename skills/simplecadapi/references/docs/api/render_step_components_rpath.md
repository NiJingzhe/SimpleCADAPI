# render_step_components_rpath

## API Definition

```python
def render_step_components_rpath(step_path: str | Path, component_names: Sequence[str], output_path: str | Path, *, with_context: bool = True, title: str | None = None, views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS, image_size: tuple[float, float] = (18.0, 12.0), dpi: int = 180, linear_deflection: float = 0.12, angular_deflection: float = 0.18) -> Path
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_step_components_rpath(...)`; unavailable inside GraphSession/@model

## Description

Render named XCAF component occurrences, optionally in assembly context.
