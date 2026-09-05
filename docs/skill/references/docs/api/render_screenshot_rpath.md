# render_screenshot_rpath

## API Definition

```python
def render_screenshot_rpath(shapes: Union[Solid, Sequence[Solid]], output_path: str, highlight_tags: Optional[Sequence[str]] = None, tag_labels: Optional[Dict[str, str]] = None, image_size: Tuple[int, int] = (1400, 900), view: Union[Tuple[float, float], str] = 'auto', views: Optional[Sequence[Tuple[float, float, str]]] = None, show_axes: bool = True, show_legend: bool = True, zoom: float = 4.0, show_callouts: bool = True, linear_deflection: Optional[float] = None, angular_deflection: Optional[float] = None, style: str = 'standard', edge_width_scale: Optional[float] = None, view_up: Optional[Sequence[float]] = None) -> str
```

*Source: operators/features.py*

## Import Surface

- top-level: `from simplecadapi import render_screenshot_rpath`

## Description

Render SDK solids through the shared OCCT/VTK BREP renderer.

By default every render is a multi-view grid (SCREENSHOT_VIEWS: isometric,
top, front, side) carrying highlight-tag color groups, callout labels with
leader lines, a legend and per-panel axis triads. Pass an explicit
``view`` (preset name or ``(elevation, azimuth)``) for the legacy
single-view image, or ``views`` to choose a custom view set.

``style="studio"`` turns the single-view path into a product shot
(gradient backdrop, three-point lighting, bold tubed BRep edges);
``linear_deflection``/``angular_deflection`` tighten the tessellation
for high-resolution exports. ``edge_width_scale`` tunes the studio edge
tube radius as a fraction of model span (default 0.0026; use ~0.001 for
exploded stacks so the ink does not swamp small parts).
