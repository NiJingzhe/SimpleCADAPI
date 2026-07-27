# ModelResult

## Class Definition

```python
@dataclass(frozen=True)
class ModelResult:
    value: Any
    session: GraphSession
    result_node_ids: Tuple[str, ...]
    model_json: str
    session_json: str
    artifact_paths: Mapping[str, Path] = field(default_factory=dict)
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import ModelResult`

## Description

Immutable result returned by a function decorated with `@scad.model`.
It keeps the ordinary Python return value together with the owned session and
the durable graph artifacts produced for that model invocation.

## Attributes

- `value`: The value returned by the model function. It may be a shape, a
  product assembly, or a tuple containing application-level reports and a
  captured preview.
- `session`: The completed `GraphSession` that recorded the model.
- `result_node_ids`: Explicitly captured graph node ids used as model outputs.
- `model_json`: Canonical low-level operation graph JSON containing the captured
  result leaves.
- `session_json`: Session JSON containing the complete session state.
- `artifact_paths`: Files written by automatic export. It contains the `scene`
  key when captured geometry or product values produced a Scene ZIP.

## Artifact Export

```python
result = build_model()
exported = result.export_artifacts(output_dir="examples/out/bracket")
print(exported.artifact_paths["scene"])
```

The same export runs automatically when `@scad.model(export_dir=...)` is used.
Only values explicitly passed to `capture_result(...)` are considered final
geometry/product outputs. Automatic export writes one self-contained
`<graph_id>.scene.zip` containing the model JSON, mapped Python sources, and
render/selection assets; it does not write adjacent model/session JSON, STEP,
STL, or FCStd files. Without an export directory, no files are written.

## Replay

```python
result = build_model()
rebuilt = result.replay()
```

`replay()` is equivalent to replaying `result.model_json`. Pass
`strict=False` only when intentionally relaxing replay validation.
