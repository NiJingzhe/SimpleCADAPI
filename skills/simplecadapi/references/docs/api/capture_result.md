# capture_result

## API Definition

```python
def capture_result(*, value: Any) -> Any
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import capture_result`

## Description

Mark the graph nodes represented by `value` as explicit final outputs of the
active model session. The value is returned unchanged. Explicit capture keeps
intermediate/debug graph leaves out of `ModelResult.model_json`. Captured
geometry/product values are also the inputs to automatic artifact export when
the model decorator receives `export_dir=...`.

```python
@scad.model(graph_id="demo")
def build_demo():
    body = scad.make_box_rsolid(width=10.0, height=4.0, depth=2.0)
    return scad.capture_result(value=body)
```

Call it inside `@model` or another active `GraphSession`.
