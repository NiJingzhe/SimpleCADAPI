# render_step_views_rpath

## API Definition

```python
def render_step_views_rpath(step_path: str | Path, output_path: str | Path, **kwargs) -> Path
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_step_views_rpath(...)`; unavailable inside GraphSession/@model

## Description

Load STEP/XCAF colors and render smooth faces with true BREP edges.
