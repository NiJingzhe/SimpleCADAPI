# GraphSession

## Class Definition

```python
class GraphSession(graph_id: Optional[str] = None)
```

*Source: graph.py*

## Description

Context manager that records CAD operations into a DAG.

with GraphSession() as session:
n1 = record_operation(
"make_line_redge", {"start": (0, 0, 0), "end": (1, 0, 0)}
)
n2 = record_operation(
"make_line_redge", {"start": (1, 0, 0), "end": (1, 1, 0)}
)
record_operation(
"make_wire_from_edges_rwire", {"edge_count": 2}, inputs=[n1, n2]
)

# Access the graph after the session
print(session.graph.topological_order())
