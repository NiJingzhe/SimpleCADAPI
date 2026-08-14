# classify_benchmark_result

## API Definition

```python
def classify_benchmark_result(*, replay_succeeded: bool, persistence_succeeded: bool, baseline_integrity_passed: bool, candidate_bytes_equal_target: bool, candidate_valid: bool, target_kind: str, candidate_kind_matches: bool, candidate_has_solid: bool, candidate_has_shell: bool, stages: Mapping[str, Mapping[str, Any]], strict_topology_requested: bool, parameter_representation_required: bool, parameter_representation_passed: bool | None) -> dict[str, Any]
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import classify_benchmark_result`

## Description

Classify evidence without letting diagnostics erase proven lower tiers.
