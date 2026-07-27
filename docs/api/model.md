# model

## API Definition

```python
def model(
    func=None,
    *,
    graph_id: Optional[str] = None,
    export_dir: Optional[str | Path] = None,
) -> Callable
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import model`

## Description

Decorate the single top-level entry point of a replayable model. Each invocation
creates and owns exactly one `GraphSession`, activates it while the function
runs, captures model/session JSON in memory, and returns a `ModelResult`. When
`export_dir` is provided, explicitly captured geometry/product values produce
one `<graph_id>.scene.zip` in that directory. The package embeds
`model/model.json`, mapped project-relative Python source files under
`sources/`, and the GLB/entity assets required for rendering and selection. It
does not create adjacent model/session JSON, STEP, STL, or FCStd files.

```python
import simplecadapi as scad

@scad.model(graph_id="bracket")
def build_bracket():
    body = scad.make_box_rsolid(width=20.0, height=10.0, depth=3.0)
    scad.capture_result(value=body)
    return body

result = build_bracket()
print(result.result_node_ids)
```

Use `result.artifact_paths["scene"]` to locate the package, or call
`result.export_artifacts(output_dir=...)` after a model has run without an
export directory. The explicit `export_dir` opt-in avoids unexpected filesystem
writes for library callers and tests.

Do not nest `@model` functions or create another `GraphSession` inside a model
function. Use `@requires_session` for child builders.
