# render_screenshot_rpath

## API Definition

```python
def render_screenshot_rpath(shapes: Union[Solid, Sequence[Solid]], output_path: str, highlight_tags: Optional[Sequence[str]] = None, tag_labels: Optional[Dict[str, str]] = None, image_size: Tuple[int, int] = (1400, 900), view: Union[Tuple[float, float], str] = 'auto', views: Optional[Sequence[Tuple[float, float, str]]] = None, show_axes: bool = True, show_legend: bool = True, zoom: float = 4.0, show_callouts: bool = True) -> str
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
