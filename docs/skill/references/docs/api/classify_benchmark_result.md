# classify_benchmark_result

## API Definition

```python
def classify_benchmark_result(*, replay_succeeded: bool, persistence_succeeded: bool, baseline_integrity_passed: bool, candidate_bytes_equal_target: bool, target_kind: str, candidate_inspection: Mapping[str, Any], stages: Mapping[str, Mapping[str, Any]], strict_topology_requested: bool, parameter_representation_required: bool, parameter_representation_passed: bool | None) -> dict[str, Any]
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import classify_benchmark_result`

## Description

Classify trusted evidence without erasing a proven lower tier.

``candidate_inspection`` must be the unmodified, process-local result of
``inspect_benchmark_step``. Candidate validity and solid/shell kind are
derived from its completed strict-schema report, never from participant
claims. Open-shell classification requires zero solids, at least one shell
explicitly reported open, and at least one unique face. ``stages`` must likewise be the unmodified,
process-local output of ``run_comparison_bundle``. Both results bind the
evaluated paths and SHA-256 digests, so replacing either STEP invalidates
the evidence. ``exact_brep`` requires the strict report's
validity, directional-volume, point-set, and incidence evidence, not just a
claimed stage status. It also requires the trusted envelope's
``checks.hard_gate``. Parameter-representation evidence is supplied by the
trusted case harness when that additional gate is required. Global
properties, sampled boundary distances, and bounded section probes are
diagnostics and are ignored by classification.

The result schema is ``{"classification": str, "reasons": list[str]}``.
Classifications are ``unsupported_or_incomplete``, ``approximation``,
``geometry_equivalent``, and ``exact_brep``. This function performs no CAD
work and all ratios, distances, and volumes retain the units documented by
``run_comparison_bundle``.
