"""Aggregate BenchCAD traced conversion reports into coverage statistics."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _load_items(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "items" in payload:
        return list(payload["items"])
    if isinstance(payload, list):
        return payload
    raise ValueError(f"unsupported report format in {path}")


def _iter_meta_files(output_dir: Path) -> Iterable[Dict[str, Any]]:
    for meta_path in sorted(output_dir.glob("*.meta.json")):
        yield json.loads(meta_path.read_text(encoding="utf-8"))


def _iter_trace_ops(trace: Optional[Dict[str, Any]]) -> Iterable[str]:
    if not trace:
        return
    for step in trace.get("steps", []):
        op = step.get("op")
        if isinstance(op, str):
            yield op


def summarize_items(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(items)
    quality_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    family_quality: Dict[str, Counter[str]] = defaultdict(Counter)
    difficulty_quality: Dict[str, Counter[str]] = defaultdict(Counter)
    rejection_reasons: Counter[str] = Counter()
    trace_ops: Counter[str] = Counter()
    unsupported_ops: Counter[str] = Counter()
    replay_ok = 0
    has_model_json = 0
    feature_coverages: List[float] = []
    param_match_rates: List[float] = []

    for item in items:
        quality = item.get("quality") or "unknown"
        status = item.get("status") or "unknown"
        quality_counts[quality] += 1
        status_counts[status] += 1
        tier_counts[str(item.get("training_tier") or "unknown")] += 1

        family = str(item.get("family") or "unknown")
        difficulty = str(item.get("difficulty") or "unknown")
        family_quality[family][quality] += 1
        difficulty_quality[difficulty][quality] += 1

        if item.get("replay_ok"):
            replay_ok += 1
        validation = item.get("validation") or {}
        if validation.get("json_replay", {}).get("valid"):
            has_model_json += 1

        for reason in item.get("validation", {}).get("reasons", []):
            rejection_reasons[str(reason).split("=")[0]] += 1

        for op in _iter_trace_ops(item.get("trace")):
            trace_ops[op] += 1

        for note in item.get("unsupported", []):
            unsupported_ops[str(note).split(":")[0]] += 1

        structure = item.get("structure") or {}
        if "feature_coverage" in structure:
            try:
                feature_coverages.append(float(structure["feature_coverage"]))
            except (TypeError, ValueError):
                pass
        elif item.get("feature_manifest") and "feature_coverage" in item["feature_manifest"]:
            try:
                feature_coverages.append(float(item["feature_manifest"]["feature_coverage"]))
            except (TypeError, ValueError):
                pass

        parameters = item.get("parameters") or {}
        if "param_match_rate" in parameters:
            try:
                param_match_rates.append(float(parameters["param_match_rate"]))
            except (TypeError, ValueError):
                pass

    accepted = quality_counts.get("accepted", 0)
    partial = quality_counts.get("partial", 0)
    rejected = quality_counts.get("rejected", 0)
    traced_ok = sum(1 for item in items if item.get("trace_steps", 0) > 0 and item.get("status") != "error")

    return {
        "total": total,
        "trace_success_rate": traced_ok / total if total else 0.0,
        "accepted_rate": accepted / total if total else 0.0,
        "partial_rate": partial / total if total else 0.0,
        "rejected_rate": rejected / total if total else 0.0,
        "quality": dict(quality_counts),
        "training_tier": dict(tier_counts),
        "conversion_status": dict(status_counts),
        "replay_ok_count": replay_ok,
        "json_replay_valid_count": has_model_json,
        "mean_feature_coverage": (
            sum(feature_coverages) / len(feature_coverages) if feature_coverages else None
        ),
        "mean_param_match_rate": (
            sum(param_match_rates) / len(param_match_rates) if param_match_rates else None
        ),
        "family_quality": {key: dict(value) for key, value in sorted(family_quality.items())},
        "difficulty_quality": {key: dict(value) for key, value in sorted(difficulty_quality.items())},
        "top_rejection_reasons": dict(rejection_reasons.most_common(20)),
        "top_trace_ops": dict(trace_ops.most_common(30)),
        "top_unsupported": dict(unsupported_ops.most_common(20)),
    }



def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize BenchCAD traced conversion reports")
    parser.add_argument(
        "--report",
        help="benchcad-traced --report JSON file",
    )
    parser.add_argument(
        "--output-dir",
        help="directory containing *.meta.json sidecars",
    )
    parser.add_argument(
        "--write",
        help="optional path to write summary JSON",
    )
    args = parser.parse_args(argv)

    if args.report:
        items = _load_items(Path(args.report))
    elif args.output_dir:
        items = list(_iter_meta_files(Path(args.output_dir)))
    else:
        parser.error("one of --report or --output-dir is required")

    summary = summarize_items(items)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.write:
        Path(args.write).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
