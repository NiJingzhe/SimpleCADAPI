# render_screenshot_rpath

## API Definition

```python
def render_screenshot_rpath(shapes: Union[Solid, Sequence[Solid]], output_path: str, highlight_tags: Optional[Sequence[str]] = None, tag_labels: Optional[Dict[str, str]] = None, image_size: Tuple[int, int] = (1400, 900), view: Union[Tuple[float, float], str] = 'auto', show_axes: bool = True, show_legend: bool = True, zoom: float = 4.0) -> str
```

*Source: operations.py*

## Description

Render a screenshot of shapes and save it to a file.
