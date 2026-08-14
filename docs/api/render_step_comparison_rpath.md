# render_step_comparison_rpath

## API Definition

```python
def render_step_comparison_rpath(target_step_path: str | Path, current_step_path: str | Path, output_path: str | Path, *, views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS, image_size: tuple[float, float] = (16.0, 20.0), dpi: int = 160, linear_deflection: float = 0.12, angular_deflection: float = 0.18, show_brep_edges: bool = True) -> Path
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_step_comparison_rpath(...)`; unavailable inside GraphSession/@model

## Description

Render target and current STEP models with identical cameras and scale.

Shared views, union bounds, tessellation, and BREP-edge settings keep
independent camera fitting from hiding size or placement differences. The
image is diagnostic evidence and does not replace strict comparison.
