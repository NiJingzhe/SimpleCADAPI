"""Orchestrate traced CadQuery → SFTC (+ optional model.json) conversion."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .replay.trace_replay import replay_trace_to_sftc
from .scoring import score_conversion, validate_traced_conversion
from .scoring.feature_semantics import empty_manifest
from .tracer.cq_runner import run_cadquery_traced
from .tracer.trace_schema import OperationTrace


@dataclass
class TracedConversionReport:
    stem: str = ""
    graph_id: str = ""
    family: str = ""
    status: str = "ok"
    unsupported: List[str] = field(default_factory=list)
    feature_count: int = 0
    error: str = ""
    trace_steps: int = 0
    validation: Optional[Dict[str, Any]] = None
    quality: str = ""
    training_tier: str = ""
    structure: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    feature_manifest: Optional[Dict[str, Any]] = None
    replay_ok: bool = False
    trace: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def convert_cadquery_traced_source(
    source: str,
    *,
    graph_id: str = "",
    stem: str = "",
    family: str = "",
    validate: bool = False,
    export_model_json: bool = False,
    write_trace: bool = False,
    use_subprocess: bool = True,
    volume_threshold: float = 0.02,
    bbox_threshold: float = 0.05,
    partial_volume_threshold: float = 0.10,
) -> tuple[str, Optional[str], TracedConversionReport]:
    report = TracedConversionReport(
        stem=stem,
        graph_id=graph_id or stem or "part",
        family=family,
    )
    want_model_json = export_model_json or validate
    trace = run_cadquery_traced(source, use_subprocess=use_subprocess)
    report.trace_steps = len(trace.steps)
    if write_trace or validate:
        report.trace = trace.to_dict()

    if trace.cq_status != "ok":
        report.status = "error"
        report.error = trace.error or "cadquery trace failed"
        report.feature_manifest = empty_manifest()
        if validate:
            validation = validate_traced_conversion(
                source,
                f"# TRACE_ERROR: {report.error}\n",
                conversion_status="error",
            )
            scored = score_conversion(
                conversion_status="error",
                unsupported=[],
                replay_ok=False,
                validation=validation,
                feature_manifest=report.feature_manifest,
                sftc_source="",
                has_model_json=False,
            )
            report.validation = scored["validation"]
            report.quality = scored["quality"]
            report.training_tier = scored["training_tier"]
            report.structure = scored["structure"]
            report.parameters = scored["parameters"]
        return f"# TRACE_ERROR: {report.error}\n", None, report

    code, replay_meta = replay_trace_to_sftc(trace, graph_id=report.graph_id)
    report.unsupported = list(replay_meta.get("unsupported", []))
    report.feature_count = int(replay_meta.get("feature_count", 0))
    report.feature_manifest = replay_meta.get("feature_manifest") or empty_manifest()
    if replay_meta.get("status") == "error":
        report.status = "error"
        report.error = str(replay_meta.get("error", "replay failed"))
    elif report.unsupported:
        report.status = "partial"
    else:
        report.status = "ok"

    model_json: Optional[str] = None
    if want_model_json and report.status != "error":
        try:
            namespace: dict = {}
            exec(compile(code, "<sftc_replay>", "exec"), namespace, namespace)
            result = namespace["build_model"]()
            model_json = result.model_json
            from simplecadapi import replay_model_json

            replay_model_json(model_json, strict=True)
            report.replay_ok = True
        except Exception as exc:
            report.replay_ok = False
            if report.status == "ok":
                report.status = "partial"
            report.unsupported.append(f"model_json export failed: {exc}")

    if validate:
        validation = validate_traced_conversion(
            source,
            code,
            model_json=model_json,
            conversion_status=report.status,
            unsupported=report.unsupported,
            replay_ok=report.replay_ok,
            volume_threshold=volume_threshold,
            bbox_threshold=bbox_threshold,
            partial_volume_threshold=partial_volume_threshold,
        )
        scored = score_conversion(
            conversion_status=report.status,
            unsupported=report.unsupported,
            replay_ok=report.replay_ok,
            validation=validation,
            feature_manifest=report.feature_manifest,
            sftc_source=code,
            has_model_json=model_json is not None,
            volume_threshold=volume_threshold,
            bbox_threshold=bbox_threshold,
            partial_volume_threshold=partial_volume_threshold,
        )
        report.validation = scored["validation"]
        report.quality = scored["quality"]
        report.training_tier = scored["training_tier"]
        report.structure = scored["structure"]
        report.parameters = scored["parameters"]
    else:
        from .scoring.feature_semantics import score_feature_semantics
        from .scoring.parameters import score_parameters

        structure = score_feature_semantics(report.feature_manifest, unsupported=report.unsupported)
        parameters = score_parameters(code, report.feature_manifest)
        report.structure = structure.to_dict()
        report.parameters = parameters.to_dict()
        report.quality = report.quality or ("partial" if report.unsupported else ("error" if report.status == "error" else ""))
        # Geometry-dependent tier left empty until --validate
        report.training_tier = "reject" if report.status == "error" else ""


    return code, model_json, report


def write_traced_conversion(
    source: str,
    output_dir: str | Path,
    *,
    stem: str,
    family: str = "",
    validate: bool = False,
    export_model_json: bool = True,
    write_trace: bool = True,
    write_manifest: bool = True,
) -> TracedConversionReport:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    code, model_json, report = convert_cadquery_traced_source(
        source,
        graph_id=stem,
        stem=stem,
        family=family,
        validate=validate,
        export_model_json=export_model_json,
        write_trace=write_trace,
    )
    (output / f"{stem}.sftc.py").write_text(code, encoding="utf-8")
    if model_json is not None:
        (output / f"{stem}.model.json").write_text(model_json, encoding="utf-8")
    if report.trace is not None:
        (output / f"{stem}.trace.json").write_text(
            json.dumps(report.trace, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if write_manifest and report.feature_manifest is not None:
        (output / f"{stem}.feature_manifest.json").write_text(
            json.dumps(report.feature_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    meta = report.to_dict()
    meta.pop("trace", None)
    (output / f"{stem}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
