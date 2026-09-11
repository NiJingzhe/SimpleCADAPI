# assess_dimension_rverdict

## API Definition

```python
def assess_dimension_rverdict(ledger: Mapping[str, Any], measurement: Mapping[str, Any], *, error_assessment: Mapping[str, Any] | None = None, output_evidence: Mapping[str, Any] | None = None, output_annotation: Mapping[str, Any] | None = None, binding_validation: Mapping[str, Any] | None = None) -> dict[str, Any]
```

*Source: inspect/drawing/evidence.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.assess_dimension_rverdict(...)`; unavailable inside GraphSession

## Description

Assess original interpretation, model conformance and output independently.

Ledger fields: dim_id, feature_id, view, source_id, raw_word_ids,
association_evidence, datum, tolerance_basis, tolerance_min/max, and
coordinate_status/value_status/association_status (all ``verified``).
An independently reviewed ``measurement_contract`` must specify kind,
definition, normalized local direction (or null), line point (or null),
units and coordinate_space. A shared contour does not identify an observable.
Ledger section_checks must independently match the measurement configuration;
section validity, ring topology, frame and material/void/display probes must
pass before a DIM can pass model measurement.
An external uncertainty assessment needs measurement_id, bound_mm, basis
and evidence; it must bound total measurement error, not just fit residual.
Unknown bounds or intervals crossing a tolerance boundary remain pending.
Output needs the current ``output_annotation`` and the corresponding per-DIM
``binding_validation`` from validate_section_annotations_rreport. The unchanged
``output_evidence`` review records layout_status=reviewed, association_status=
verified, evidence and the DIM/measurement/model/section IDs seen at review time.
Its render_artifact contains absolute image_path/sidecar_path and the reviewed
image_sha256/sidecar_sha256. Current files, source IDs and annotation content
must match; stale reviews are never relabeled. This checks evidence contracts;
it does not independently establish the truth of a caller's review or bound.
