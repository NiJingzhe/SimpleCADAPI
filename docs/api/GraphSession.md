# GraphSession

## Class Definition

```python
class GraphSession(graph_id: Optional[str] = None)
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import GraphSession`

## Description

Context manager that records CAD operations into a DAG.

For new replayable model entry points, prefer `@scad.model`, which owns the
session and returns a `ModelResult`. Use `GraphSession` directly when composing
or testing lower-level graph workflows. `result_node_ids` reports the graph
nodes selected by `capture_result`:

```python
with GraphSession(graph_id="demo") as session:
    body = make_box_rsolid(width=10.0, height=6.0, depth=2.0)
    session.capture_result(value=body)

print(session.result_node_ids)
```
