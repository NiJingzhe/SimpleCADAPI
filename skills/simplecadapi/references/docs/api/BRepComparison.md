# BRepComparison

## Class Definition

```python
class BRepComparison(target: str | None, candidate: str | None, target_minus_candidate_volume: float, candidate_minus_target_volume: float, same_geometric_point_set: bool, geometry_labelled_incidence_graph_isomorphic: bool, target_graph_nodes_edges: tuple[int, int], candidate_graph_nodes_edges: tuple[int, int], geometric_tolerance: float, boolean_volume_tolerance: float, diagnostics: dict[str, Any] = field(default_factory=dict))
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.BRepComparison(...)`; unavailable inside GraphSession

## Description

Hard-gate comparison facts for two solid BREPs.

``diagnostics`` records validity, bounds, material, topology, and carrier
evidence. Use ``to_error_summary()`` to group every failed check by a
plausible common root cause without changing the strict hard gate.
