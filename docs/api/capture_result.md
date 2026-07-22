# capture_result

## API Definition

```python
def capture_result(*, value: Any) -> Any
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import capture_result`

## Description

Mark the graph nodes represented by `value` as the explicit final outputs of the
active model session. The value is returned unchanged, so it can be used inline
or assigned back to a local variable.

```python
@scad.model(graph_id="multi_output_demo")
def build_model():
    primary = scad.make_box_rsolid(width=10.0, height=4.0, depth=2.0)
    secondary = scad.make_cylinder_rsolid(radius=2.0, height=5.0)
    return scad.capture_result(value=(primary, secondary))
```

Explicit capture prevents unrelated intermediate graph leaves from becoming
model outputs. When the enclosing `@model` uses `export_dir=...`, captured
geometry and product values become roots in the single self-contained Scene ZIP.
The package embeds model JSON and mapped Python sources; automatic export does
not create adjacent model/session JSON, STEP, STL, or FCStd files. It must be
called inside `@model` or another active `GraphSession`.
