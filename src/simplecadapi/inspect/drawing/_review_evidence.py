"""Validate the exact files and annotation state seen by a visual reviewer."""

import json
import hashlib
from pathlib import Path
from collections.abc import Mapping

from ._provenance import digest, file_hash
from ._section_layout import label_rows


def validate_review(review, ledger, measurement, annotation, binding):
    if not review:
        return {"status": "pending", "errors": ["visual review missing"]}
    errors = []
    try:
        annotation_id = digest(annotation)
    except (TypeError, ValueError) as exc:
        return {
            "status": "rejected",
            "errors": [f"invalid current annotation: {exc}"],
            "identity_verified": False,
        }
    if not annotation or binding.get("annotation_id") != annotation_id:
        errors.append("current binding was not computed for this annotation")
    if binding.get("status") != "verified":
        errors.append("current independent annotation binding is not verified")
    for key, current in {
        "dim_id": ledger.get("dim_id"),
        **{
            k: measurement.get(k)
            for k in ("measurement_id", "model_hash", "section_id")
        },
    }.items():
        if not current or review.get(key) != current:
            errors.append(f"review {key} is missing or stale")
        if current != binding.get(key):
            errors.append(f"independent binding {key} differs from current measurement")
    artifact = review.get("render_artifact")
    if not isinstance(artifact, Mapping):
        errors.append("reviewed render_artifact is missing")
    elif not annotation:
        errors.append("current output annotation is missing")
    else:
        try:
            image_path = Path(artifact["image_path"])
            sidecar_path = Path(artifact["sidecar_path"])
            # Paths are recorded at review time, not silently rebased or replaced.
            if not image_path.is_absolute() or not sidecar_path.is_absolute():
                raise ValueError("review artifact paths must be absolute")
            image_hash = file_hash(image_path)
            if image_hash != artifact.get("image_sha256"):
                errors.append("reviewed image SHA-256 differs from current file")
            sidecar_bytes = sidecar_path.read_bytes()
            if hashlib.sha256(sidecar_bytes).hexdigest() != artifact.get(
                "sidecar_sha256"
            ):
                errors.append("reviewed sidecar SHA-256 differs from current file")
            sidecar = json.loads(sidecar_bytes.decode("utf-8"))
            if not isinstance(sidecar, Mapping):
                raise ValueError("sidecar must be an object")
            if sidecar.get("image_sha256") != image_hash:
                errors.append("sidecar is not bound to the reviewed image bytes")
            for key in ("model_hash", "section_id"):
                if sidecar.get(key) != measurement.get(key):
                    errors.append(f"rendered {key} differs from current measurement")
            rendered = [
                d
                for d in sidecar.get("dimensions", [])
                if d.get("dim_id") == ledger.get("dim_id")
            ]
            if len(rendered) != 1:
                errors.append("reviewed render must contain exactly one matching DIM")
            else:
                rendered = rendered[0]
                if rendered.get("annotation_id") != annotation_id:
                    errors.append(
                        "reviewed annotation differs from current annotation content/layout inputs"
                    )
                for key, value in annotation.items():
                    if rendered.get(key) != value:
                        errors.append(
                            f"rendered annotation {key} differs from current annotation"
                        )
                if rendered.get("unrounded_value") != measurement.get("value"):
                    errors.append(
                        "rendered number does not come from current measurement"
                    )
                rows, _, _ = label_rows([annotation])
                if rendered.get("display_text") != rows[0]["lines"]:
                    errors.append(
                        "rendered text differs from the current formatted annotation"
                    )
            if sidecar.get("binding_validation", {}).get("status") != "verified":
                errors.append("reviewed render was not generated as verified evidence")
            if sidecar.get("layout", {}).get("automatic_status") != "passed":
                errors.append("reviewed render has failed automatic layout checks")
            if sidecar.get("section_validation", {}).get("status") != "passed":
                errors.append("reviewed render has incomplete or failed section checks")
            if sidecar.get("section_checks") != ledger.get("section_checks"):
                errors.append("reviewed section contract differs from current ledger")
            if sidecar.get("contour_method") != annotation.get("configuration", {}).get(
                "contour_method"
            ):
                errors.append("rendered section method differs from bound measurement")
        except (OSError, KeyError, TypeError, ValueError, AttributeError) as exc:
            errors.append(f"invalid reviewed artifact: {exc}")
    complete = (
        review.get("layout_status") == "reviewed"
        and review.get("association_status") == "verified"
        and bool(review.get("evidence"))
    )
    rejected = any(
        review.get(k) in ("failed", "rejected")
        for k in ("layout_status", "association_status")
    )
    return {
        "status": (
            "rejected" if errors or rejected else "verified" if complete else "pending"
        ),
        "errors": errors,
        "identity_verified": not errors,
    }
