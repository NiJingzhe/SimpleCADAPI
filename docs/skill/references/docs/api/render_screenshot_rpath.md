# render_screenshot_rpath

## API Definition

```python
def render_screenshot_rpath(shapes: Union[Solid, Sequence[Solid], Any], output_path: str, highlight_tags: Optional[Sequence[str]] = None, tag_labels: Optional[Dict[str, str]] = None, image_size: Tuple[int, int] = (1400, 900), view: Union[Tuple[float, float], str] = 'auto', views: Optional[Sequence[Tuple[float, float, str]]] = None, show_axes: bool = True, show_legend: bool = True, zoom: float = 4.0, show_callouts: bool = True, linear_deflection: Optional[float] = None, angular_deflection: Optional[float] = None, style: str = 'studio', edge_width_scale: Optional[float] = None, view_up: Optional[Sequence[float]] = None, supersample: int = 2) -> str
```

*Source: operators/features.py*

## Import Surface

- top-level: `from simplecadapi import render_screenshot_rpath`

## Description

Render solids or raw TopoDS shapes through the one OCCT/VTK pipeline.

``shapes`` accepts SDK ``Solid`` objects (with full tag highlight,
callout and legend support) or raw ``TopoDS_Shape`` entries from the
STEP inspection family (same engine, same edge ink and supersampling,
no tag features).

There is exactly one output form: a multi-view grid of one to four
panels, each carrying annotations. ``view="auto"`` (default) uses the
standard four-view set; an explicit preset name or ``(elevation,
azimuth)`` pair renders a single full-frame panel; ``views`` accepts
up to four explicit ``(elevation, azimuth, label)`` triples.
``zoom`` applies to single-panel renders only.

By default every render is a multi-view grid (SCREENSHOT_VIEWS: isometric,
top, front, side) carrying highlight-tag color groups, callout labels with
leader lines, a legend and per-panel axis triads. Pass an explicit
``view`` (preset name or ``(elevation, azimuth)``) for the legacy
single-view image, or ``views`` to choose a custom view set.

``supersample`` (default 2) renders at an integer multiple and
downsamples with LANCZOS for deterministic crisp edges; 1 renders 1:1.
``style="studio"`` turns the single-view path into a product shot
(gradient backdrop, three-point lighting, bold tubed BRep edges);
``linear_deflection``/``angular_deflection`` tighten the tessellation
for high-resolution exports. ``edge_width_scale`` tunes the studio edge
tube radius as a fraction of model span (default 0.0026; use ~0.001 for
exploded stacks so the ink does not swamp small parts).
