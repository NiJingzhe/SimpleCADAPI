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
It contains the ordinary Python return value, the completed graph session, the
explicit result node ids, the model/session JSON artifacts, and any paths
written by automatic artifact export.

```python
result = build_model()
rebuilt = result.replay()
```

`replay()` replays `result.model_json`. Use `result.value` for the application
return value and `result.result_node_ids` to inspect the captured graph outputs.
Use `result.export_artifacts(output_dir=...)` to write one self-contained
`<graph_id>.scene.zip` after the model runs. The package embeds model JSON,
mapped project-relative Python sources, and render/selection assets; automatic
export does not write adjacent model/session JSON, STEP, STL, or FCStd files.
