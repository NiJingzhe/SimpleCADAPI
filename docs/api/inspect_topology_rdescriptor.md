# inspect_topology_rdescriptor

## API Definition

```python
def inspect_topology_rdescriptor(model_or_shape: ModelInput, *, max_problem_edges: int = 100, small_face_area_threshold: float = 1e-08, max_small_faces: int = 100) -> dict[str, Any]
```

*Source: inspect/brep/topology_inspection.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_topology_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Report topology use counts independently from generic BREP validity.

Edge classifications use face-local occurrences, so a seam used twice by
one face is distinct from a free edge that merely has one unique ancestor.
