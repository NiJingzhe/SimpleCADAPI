"""Rerun section evidence against a STEP model and a separately reviewed ledger.

Usage: python tools/verify_drawing_evidence.py --model part.step
       --evidence evidence.json --out verification.json

Input JSON: plane, ledger (all DIM rows), annotations, output_reviews (DIM ID
to independent layout/association review). Reviews retain their original DIM,
measurement/model/section IDs and render_artifact file paths plus SHA-256 values.
They are checked against current measurements and exact image/sidecar bytes;
current IDs are never written into old reviews. Exit 0 only for all three
gates on every ledger DIM; 1 means failed or incomplete evidence.
Each ledger row supplies independent section_checks; reports expose the separate
section_validation with failure ownership (definition, intersection, display or
independent model evidence). No center-of-mass/mass/inertia/volume-equivalence
acceptance criteria are introduced by this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from simplecadapi.inspect import drawing


def verify(model, evidence):
    plane = evidence["plane"]
    ledger = evidence["ledger"]
    annotations = evidence["annotations"]
    validation = drawing.validate_section_annotations_rreport(
        model, plane, annotations, ledger
    )
    bindings = {row["dim_id"]: row for row in validation["dimensions"]}
    annotations_by_dim = {row["dim_id"]: row for row in annotations}
    measurement_cache = {}
    verdicts = []
    for row in ledger:
        annotation = annotations_by_dim.get(row["dim_id"], {})
        record = {}
        if annotation.get("configuration"):
            configuration = dict(annotation["configuration"])
            configuration.pop("contour_method", None)
            key = json.dumps(configuration, sort_keys=True)
            if key not in measurement_cache:
                measurement_cache[key] = drawing.measure_model_section_rdimensions(
                    model, plane, **configuration
                )
            record = next(
                (
                    m
                    for m in measurement_cache[key].measurements
                    if m["measurement_id"] == annotation.get("measurement_id")
                ),
                {},
            )
        review = dict(evidence.get("output_reviews", {}).get(row["dim_id"], {}))
        binding = bindings.get(row["dim_id"], {})
        verdicts.append(
            drawing.assess_dimension_rverdict(
                row,
                record,
                error_assessment=annotation.get("error_assessment") or None,
                output_evidence=review,
                output_annotation=annotation,
                binding_validation=binding,
            )
        )
        verdicts[-1]["section_validation"] = record.get(
            "section_validation", {"status": "pending"}
        )
    return {
        "binding_validation": validation,
        "dimensions": verdicts,
        "coverage": drawing.summarize_dimension_coverage_rreport(
            verdicts, expected_dim_ids=[r["dim_id"] for r in ledger]
        ),
        "status": (
            "passed"
            if verdicts
            and validation["status"] == "verified"
            and all(v["status"] == "passed" for v in verdicts)
            else "incomplete_or_failed"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    try:
        report = verify(args.model, evidence)
    except (ValueError, KeyError, TypeError) as exc:
        report = {"status": "incomplete_or_failed", "error": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"{report['status']}: {args.out}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
