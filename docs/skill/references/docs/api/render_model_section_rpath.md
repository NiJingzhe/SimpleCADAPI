# render_model_section_rpath

## API Definition

```python
def render_model_section_rpath(model: Any, plane: Mapping[str, Sequence[float]], *, dimensions: Sequence[Mapping[str, Any]] | None = None, hatch: bool = True, dpi: int = 200, margin_mm: float = 8.0, target_size_pt: tuple[float, float] = (1100.0, 850.0), out_dir: str | Path = '.', stem: str | None = None, validation_ledger: Sequence[Mapping[str, Any]] | None = None, section_strategy: str = 'auto', section_checks: Mapping[str, Any] | None = None, samples_per_edge: int = 64) -> Path
```

*Source: inspect/drawing/section.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.render_model_section_rpath(...)`; unavailable inside GraphSession

## Description

Render the model section at one plane as an annotated evidence image.

Fixed output: ``<stem>.png`` (the annotated model-section render), plus
``<stem>.json`` (sidecar with plane, dimension echo, and file list).
``dimensions`` entries carry ``dim_id``, ``kind``, ``measured`` and
optional ``nominal`` / ``tol`` / ``anchor`` (plane-space ``[x, y]``);
values are caller-supplied data, not proof of correct measurement.
``validation_ledger`` enables formal evidence: independently remeasure and
validate bound annotations before writing files; invalid bindings raise.
Sidecars retain unrounded values, target/result/model/section IDs, complete
local-to-canvas-to-pixel transforms, text boxes and leader paths. Readability
and feature association are separate review fields. Missing anchors are
placeholders, never feature-association evidence.
Each annotation receives a content-derived annotation_id. The sidecar records
the PNG's image_sha256; a visual reviewer must retain both file hashes and the
reviewed measurement/model/section IDs for subsequent acceptance.
``section_strategy`` has the same meanings as in measurement; ``samples_per_edge``
controls the actual displayed polygons. ``section_checks`` is explicit or,
for formal output, read from the unanimous independently reviewed ledger
contract. Formal output rejects open contours, invalid material faces, missing
ring/probe coverage, wrong frames, and solid/section/display disagreements.
Raw rendering is allowed for diagnostics and is labeled diagnostic_only in
the sidecar. Check section definition/intersection/display before considering
model changes, and require independent solid evidence of any geometry error.
