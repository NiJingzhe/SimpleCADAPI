# select

## API Definition

```python
def select(items: Iterable[Any]) -> Query
```

*Source: ql.py*

## Import Surface

- submodule: `from simplecadapi.ql import select` or `simplecadapi.ql.select`

## Description

Start a QL query over a shape collection or selector scope.

For topology-aware selection, use `ql.faces()`, `ql.edges()`, `ql.wires()`,
`ql.vertices()`, or `ql.solids()`. `ShapeSelector.intersection(other)` forms a
serializable set intersection. `selector.shared_boundary(other,
to_kind="edge")` intersects the boundaries of two selectors. Edge selectors
also support `incident_to(face_selector, ..., distinct=True)` and
`incident_face_count(exactly=2)` to select edges by exact incident Face
witnesses and reject open or non-manifold edges.

These selectors resolve by topology identity, not enumeration order, area,
normal, or position heuristics. Their `to_dict()` payloads can be restored with
`ql.selector_from_dict(...)`.
