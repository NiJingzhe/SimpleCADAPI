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
``elapsed_seconds``, ``report``, ``report_path``, and ``error``. Successful
diagnostics have status ``completed``, ``gate_passed=None``, and no
acceptance checks. Completed material and strict acceptance stages add
boolean ``checks`` and become ``passed`` or ``failed``. Non-run stages contain
a ``reason`` instead; the aggregate ``sections`` stage contains ``reports``,
one worker envelope per unique section ID. ``global`` and ``material`` always
appear; ``boundary`` and ``sections`` appear only when ``diagnostics=True``;
``strict`` always appears but runs only for a solid with proven material
equality when ``strict_topology=True``.

Report schemas and units:

- ``global`` reports bounding-box and centroid distances in millimetres,
total surface area in square millimetres, aggregate volume in cubic
millimetres, topology counts, and dimensionless relative deltas.
- ``material`` reports the comparison method, directional missing/excess
volumes in cubic millimetres, Boolean and volume-balance validity, and the
derived ``strict_point_set_equal`` tri-state. Its
``relative_total_difference`` is dimensionless and diagnostic. For regular
solids, non-fuzzy bidirectional Cut residual volumes establish
tolerance-bounded material equivalence; this is not an aggregate
mass-property comparison and does not prove topology, representation, or
literal boundary identity.
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
edited stage envelopes must never be passed to classification. Aggregate
global properties, sampled boundary distances, and bounded section probes are
diagnostics and never affect classification. Only strict bidirectional
material residual evidence and, when requested, strict topology evidence are
acceptance gates.
