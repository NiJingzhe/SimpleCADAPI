# render_step_components_colored_rpath

## API Definition

```python
def render_step_components_colored_rpath(step_path: str | Path, component_colors: Mapping[str, ColorSpec], output_path: str | Path, *, palette: Sequence[ColorSpec] | None = None, with_context: bool = True, title: str | None = None, views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS, image_size: tuple[float, float] = (18.0, 12.0), dpi: int = 180, linear_deflection: float = 0.12, angular_deflection: float = 0.18, show_legend: bool = True) -> Path
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.render_step_components_colored_rpath(...)`; unavailable inside GraphSession/@model

## Description

Render multiple STEP components, each in its own color.

The recommended, most semantic form maps each component selector
directly to a color NAME::

render_step_components_colored_rpath(
"assembly.step",
{"SPK-2030X4MM": "cyan", "USER_LIBRARY-USB_TYPE_C_PORT__S": "purple"},
"out.png",
)

Selectors resolve like ``render_step_components_rpath`` (names, paths,
or node ids) and multiple occurrences of one name share its color.
``component_colors`` values accept a named color from the built-in set
(red, crimson, orange, gold, yellow, lime, green, teal, cyan, skyblue,
blue, navy, purple, violet, magenta, pink, salmon, brown, tan, olive,
gray, silver, black, white), a ``#RRGGBB`` / ``#RGB`` hex string, an
``(r, g, b)`` 0..1 tuple, or an integer palette index (with ``palette``).
The result shows every selected solid at once, color-coded, with an
optional color legend so the geometry can be matched to per-component
text.
