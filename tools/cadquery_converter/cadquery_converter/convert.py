"""Orchestrate CadQuery → SFTC conversion and validation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .emit_sftc import emit_sftc
from .parse_cq import CadQueryParseError, parse_cadquery_source
from .validate import ValidationResult, validate_conversion


@dataclass
class ConversionReport:
    stem: str = ""
    graph_id: str = ""
    family: str = ""
    status: str = "ok"
    unsupported: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    feature_count: int = 0
    error: str = ""
    validation: Optional[Dict[str, Any]] = None
    quality: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def convert_cadquery_source(
    source: str,
    *,
    graph_id: str = "",
    stem: str = "",
    family: str = "",
    validate: bool = False,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
) -> tuple[str, ConversionReport]:
    report = ConversionReport(stem=stem, graph_id=graph_id or stem or "part", family=family)
    try:
        program = parse_cadquery_source(
            source,
            graph_id=graph_id or stem or "part",
            stem=stem,
            family=family,
        )
    except (CadQueryParseError, SyntaxError) as exc:
        report.status = "error"
        report.error = str(exc)
        if validate:
            validation = validate_conversion(
                source,
                f"# CONVERSION_ERROR: {exc}\n",
                conversion_status="error",
            )
            report.validation = validation.to_dict()
            report.quality = validation.quality
        return f"# CONVERSION_ERROR: {exc}\n", report

    report.graph_id = program.graph_id
    report.unsupported = list(program.unsupported)
    report.warnings = list(program.warnings)
    report.feature_count = len(program.steps)
    if program.unsupported:
        report.status = "partial"
    if not program.steps:
        report.status = "error"
        report.error = "no features lowered"

    code = emit_sftc(program)

    if validate:
        validation = validate_conversion(
            source,
            code,
            conversion_status=report.status,
            unsupported=report.unsupported,
            volume_threshold=volume_threshold,
            bbox_threshold=bbox_threshold,
        )
        report.validation = validation.to_dict()
        report.quality = validation.quality

    return code, report


def convert_cadquery_file(
    input_path: str | Path,
    output_path: str | Path,
    *,
    graph_id: str = "",
    stem: str = "",
    family: str = "",
    meta_path: str | Path | None = None,
    validate: bool = False,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
) -> ConversionReport:
    input_file = Path(input_path)
    source = input_file.read_text(encoding="utf-8")
    code, report = convert_cadquery_source(
        source,
        graph_id=graph_id or input_file.stem,
        stem=stem or input_file.stem,
        family=family,
        validate=validate,
        volume_threshold=volume_threshold,
        bbox_threshold=bbox_threshold,
    )
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(code, encoding="utf-8")

    if meta_path is not None:
        Path(meta_path).write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
