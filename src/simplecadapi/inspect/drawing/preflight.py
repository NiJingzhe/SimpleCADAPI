"""Coordinate preflight using independent rendered landmark observations."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .geometry import extract_drawing_primitives_rstrokes
from .text import extract_drawing_text_rwords
from .render import render_drawing_view_rpath
from ._provenance import digest


def inspect_drawing_coordinates_rreport(
    path: str | Path,
    page: int = 0,
    *,
    observations: Sequence[Mapping[str, Any]] = (),
    dpi: int = 150,
    rect: Sequence[float] | None = None,
    tolerance_px: float = 2.0,
    out_dir: str | Path = ".",
    stem: str = "coordinate_preflight",
) -> dict[str, Any]:
    """Check text and vector landmarks against independently observed image pixels.

    Writes a viewport and a preflight report with source/page/box/rotation facts.
    Each observation has kind (text/vector), object_id, point_index, pixel [x,y],
    source_id, page, dpi, rect_display, and evidence (review/crop reference).
    Text points are bbox corners TL,TR,BR,BL; vector points are extracted vertices
    or Bezier controls. Bezier controls need independently derived references,
    since they need not be on the rendered curve. Pixels use top-left pixel-edge
    coordinates of this exact viewport. Missing text/vector observations remain
    pending: inverse-transform consistency alone never proves visual alignment.
    """
    if not math.isfinite(tolerance_px) or tolerance_px <= 0:
        raise ValueError("tolerance_px must be finite and positive")
    text = extract_drawing_text_rwords(path, page)
    vectors = extract_drawing_primitives_rstrokes(path, page)
    png = render_drawing_view_rpath(
        path, page, dpi=dpi, rect=rect, out_dir=out_dir, stem=stem
    )
    metadata = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
    if (
        text.metadata["source_id"] != metadata["source_id"]
        or vectors.metadata["source_id"] != metadata["source_id"]
    ):
        raise ValueError("source changed between text/vector/render extraction")
    transform = np.asarray(metadata["page_to_pixel"])
    inverse = np.asarray(metadata["pixel_to_page"])
    checks = []
    for observation in observations:
        errors = []
        distance = None
        try:
            for key in ("source_id", "page", "dpi", "rect_display"):
                if observation.get(key) != metadata[key]:
                    errors.append(f"observation {key} differs from rendered source")
            if not observation.get("evidence"):
                errors.append("independent observation evidence missing")
            if observation["kind"] == "text":
                word = next(
                    w for w in text.words if w["id"] == observation["object_id"]
                )
                x0, y0, x1, y1 = word["box"]
                points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            elif observation["kind"] == "vector":
                points = next(
                    s["points"]
                    for s in vectors.strokes
                    if s["id"] == observation["object_id"]
                )
            else:
                raise ValueError("observation kind must be text or vector")
            index = observation["point_index"]
            if not isinstance(index, int) or not 0 <= index < len(points):
                raise ValueError("point_index out of range")
            point = np.array([*points[index], 1.0])
            pixel = np.asarray(observation["pixel"], dtype=float)
            if pixel.shape != (2,) or not np.isfinite(pixel).all():
                raise ValueError("observed pixel must be a finite 2D point")
            projected = transform @ point
            if not (
                0 <= projected[0] <= metadata["pixel_size"][0]
                and 0 <= projected[1] <= metadata["pixel_size"][1]
            ):
                errors.append("landmark lies outside viewport")
            distance = float(np.linalg.norm(projected[:2] - pixel))
            if distance > tolerance_px:
                errors.append("landmark differs from rendered observation")
            if not np.allclose(inverse @ projected, point, atol=1e-9, rtol=0):
                errors.append("coordinate inverse failed")
        except (KeyError, ValueError, TypeError, StopIteration) as exc:
            errors.append(f"invalid observation: {exc}")
        checks.append(
            {
                "observation": dict(observation),
                "error_px": distance,
                "status": "verified" if not errors else "failed",
                "errors": errors,
            }
        )
    statuses = {}
    for kind in ("text", "vector"):
        selected = [c for c in checks if c["observation"].get("kind") == kind]
        statuses[kind] = (
            (
                "verified"
                if all(c["status"] == "verified" for c in selected)
                else "failed"
            )
            if selected
            else "pending"
        )
    report = {
        "metadata": metadata,
        "checks": checks,
        "layers": statuses,
        "tolerance_px": tolerance_px,
        "viewport": str(png.resolve()),
        "status": (
            "failed"
            if any(c["status"] == "failed" for c in checks)
            else (
                "verified"
                if all(v == "verified" for v in statuses.values())
                else "pending"
            )
        ),
    }
    report["preflight_id"] = digest(report)
    report_path = Path(out_dir) / f"{stem}.preflight.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
