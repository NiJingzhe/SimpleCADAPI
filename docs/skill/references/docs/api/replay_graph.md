# replay_graph

## API Definition

```python
def replay_graph(graph: OperationGraph, *, strict: bool = True) -> List[Any]
```

*Source: serializer.py*

## Import Surface

- top-level: `from simplecadapi import replay_graph`

## Description

Replay an OperationGraph to rebuild the model.

Executes nodes in topological order. Primitives are created from their
parameters; boolean operations consume upstream outputs.

## Parameters

### graph

- **Description**: The graph to replay.

## Returns

List of leaf-node outputs. These may be solids, faces, wires, edges,
or vertices depending on the workflow.
