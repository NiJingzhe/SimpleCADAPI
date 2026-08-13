# BRepComparison

## Class Definition

```python
class BRepComparison(target: str | None, candidate: str | None, target_minus_candidate_volume: float, candidate_minus_target_volume: float, same_geometric_point_set: bool, geometry_labelled_incidence_graph_isomorphic: bool, target_graph_nodes_edges: tuple[int, int], candidate_graph_nodes_edges: tuple[int, int], geometric_tolerance: float, boolean_volume_tolerance: float, diagnostics: dict[str, Any] = field(default_factory=dict))
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.BRepComparison(...)`; unavailable inside GraphSession/@model

## Description

Hard-gate comparison facts for two solid BREPs.

`diagnostics` contains STEP validity, bounding box, volume, strict Boolean
difference, topology counts, Face-Edge topology, and surface/curve type facts.
Use `write_json(...)` to write the complete comparison. Use
`to_error_summary()` or `write_error_summary_json(...)` to obtain every failed
check grouped by plausible common root cause. These methods do not change the
existing hard-gate definition.
