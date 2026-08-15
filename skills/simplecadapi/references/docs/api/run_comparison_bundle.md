# run_comparison_bundle

## API Definition

```python
def run_comparison_bundle(config: EvaluationConfig, *, target_path: str | Path, candidate_path: str | Path, output_directory: str | Path, diagnostics: bool = False, strict_topology: bool = False, python_executable: str = sys.executable) -> dict[str, dict[str, Any]]
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import run_comparison_bundle`

## Description

Run trusted acceptance stages and optional geometric diagnostics.

Worker-stage envelopes contain ``status``, ``gate_passed``,
``elapsed_seconds``, ``report``, ``report_path``, and ``error``. Completed
comparison stages also contain boolean ``checks``. Non-run stages contain a
``reason`` instead; the aggregate ``sections`` stage contains ``reports``,
one worker envelope per unique section ID. Status is ``passed``, ``failed``,
``error``, ``skipped``, or ``not_applicable``. ``global`` and ``material``
always appear; ``boundary`` and ``sections`` appear only when
``diagnostics=True``; ``strict`` always appears but runs only for a solid
with proven material equality when ``strict_topology=True``.

Report schemas and units:

- ``global`` reports bounding-box and centroid distances in millimetres,
surface area in square millimetres, volume in cubic millimetres, topology
counts, and dimensionless relative deltas.
- ``material`` reports the comparison method, directional missing/excess
volumes in cubic millimetres, Boolean and volume-balance validity, and the
derived ``strict_point_set_equal`` tri-state. Its
``relative_total_difference`` is dimensionless.
- ``boundary`` reports sampled-to-exact distances in millimetres, including
approximate Hausdorff and p95 distances. It is diagnostic, never equality
proof.
- ``sections`` contains one envelope per configured section. Plane values,
perimeters, and Hausdorff distances are millimetres; section areas are
square millimetres; ``relative_area_error`` is dimensionless.
- ``strict`` reports directional difference volumes in cubic millimetres,
geometric and Boolean tolerances, STEP validity, geometric point-set
equality, geometry-labelled incidence isomorphism, and
``hard_gate_passed``. Exact classification also requires the trusted
envelope's ``checks.hard_gate`` to be true.

The evaluator configuration, target/candidate paths, worker executable, and
returned reports are trusted-harness data. Participant-authored reports or
edited stage envelopes must never be passed to classification. Global,
boundary, and section results are diagnostics and cannot establish geometric
or exact BREP equality.
