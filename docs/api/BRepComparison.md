# BRepComparison

## Class Definition

```python
class BRepComparison(target: str | None, candidate: str | None, target_minus_candidate_volume: float, candidate_minus_target_volume: float, same_geometric_point_set: bool, geometry_labelled_incidence_graph_isomorphic: bool, target_graph_nodes_edges: tuple[int, int], candidate_graph_nodes_edges: tuple[int, int], geometric_tolerance: float, boolean_volume_tolerance: float)
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.BRepComparison(...)`; unavailable inside GraphSession/@model

## Description

Hard-gate comparison facts for two solid BREPs.
