"""CLI for CadQuery → SFTC conversion."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .benchcad import iter_benchcad_rows
from .benchcad_edit import iter_benchcad_edit_rows
from .benchcad_qa import iter_benchcad_qa_rows
from .convert import convert_cadquery_file, convert_cadquery_source
from .scoring.code_qa import score_code_qa
from .scoring.edit import score_edit
from .traced_convert import convert_cadquery_traced_source


def _cmd_convert(args: argparse.Namespace) -> int:
    if args.input:
        report = convert_cadquery_file(
            args.input,
            args.output,
            graph_id=args.graph_id or "",
            stem=args.stem or "",
            family=args.family or "",
            meta_path=args.meta,
            validate=args.validate,
            volume_threshold=args.volume_threshold,
            bbox_threshold=args.bbox_threshold,
        )
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.quality in {"", "accepted", "partial"} and report.status != "error" else 1

    raise SystemExit("--input is required for convert")


def _cmd_benchcad(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    quality_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for row in iter_benchcad_rows(args.dataset, limit=args.limit):
        code, report = convert_cadquery_source(
            row.code,
            graph_id=row.stem,
            stem=row.stem,
            family=row.family,
            validate=args.validate,
            volume_threshold=args.volume_threshold,
            bbox_threshold=args.bbox_threshold,
        )

        quality = report.quality or ("partial" if report.status == "partial" else report.status)
        if args.filter_quality and quality not in args.filter_quality:
            continue

        (output_dir / f"{row.stem}.sftc.py").write_text(code, encoding="utf-8")
        meta = report.to_dict()
        meta.update(
            {
                "variant": row.variant,
                "difficulty": row.difficulty,
                "base_plane": row.base_plane,
                "standard": row.standard,
            }
        )
        (output_dir / f"{row.stem}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        reports.append(meta)
        quality_counts[quality] += 1
        status_counts[report.status] += 1

    summary = {
        "total_written": len(reports),
        "conversion_status": dict(status_counts),
        "quality": dict(quality_counts),
        "validate": args.validate,
        "filter_quality": args.filter_quality,
        "items": reports,
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "total_written": summary["total_written"],
                "conversion_status": summary["conversion_status"],
                "quality": summary["quality"],
            },
            indent=2,
        )
    )
    return 0


def _write_traced_artifacts(
    output_dir: Path,
    stem: str,
    code: str,
    model_json: str | None,
    report,
    extra_meta: dict | None = None,
) -> dict:
    (output_dir / f"{stem}.sftc.py").write_text(code, encoding="utf-8")
    if model_json is not None:
        (output_dir / f"{stem}.model.json").write_text(model_json, encoding="utf-8")
    if report.trace is not None:
        (output_dir / f"{stem}.trace.json").write_text(
            json.dumps(report.trace, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if report.feature_manifest is not None:
        (output_dir / f"{stem}.feature_manifest.json").write_text(
            json.dumps(report.feature_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    meta = report.to_dict()
    if extra_meta:
        meta.update(extra_meta)
    meta_for_disk = {key: value for key, value in meta.items() if key != "trace"}
    (output_dir / f"{stem}.meta.json").write_text(
        json.dumps(meta_for_disk, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return meta


def _cmd_benchcad_traced(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    quality_counts: Counter[str] = Counter()
    tier_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()

    for row in iter_benchcad_rows(args.dataset, limit=args.limit):
        export_model_json = args.emit == "both"
        code, model_json, report = convert_cadquery_traced_source(
            row.code,
            graph_id=row.stem,
            stem=row.stem,
            family=row.family,
            validate=args.validate,
            export_model_json=export_model_json,
            write_trace=True,
            use_subprocess=args.subprocess,
            volume_threshold=args.volume_threshold,
            bbox_threshold=args.bbox_threshold,
        )

        quality = report.quality or ("partial" if report.status == "partial" else report.status)
        if args.filter_quality and quality not in args.filter_quality:
            continue
        if args.filter_tier and report.training_tier and report.training_tier not in args.filter_tier:
            continue

        meta = _write_traced_artifacts(
            output_dir,
            row.stem,
            code,
            model_json,
            report,
            extra_meta={
                "variant": row.variant,
                "difficulty": row.difficulty,
                "base_plane": row.base_plane,
                "standard": row.standard,
            },
        )
        reports.append(meta)
        quality_counts[quality] += 1
        tier_counts[report.training_tier or "unknown"] += 1
        status_counts[report.status] += 1

    summary = {
        "total_written": len(reports),
        "conversion_status": dict(status_counts),
        "quality": dict(quality_counts),
        "training_tier": dict(tier_counts),
        "validate": args.validate,
        "emit": args.emit,
        "subprocess": args.subprocess,
        "filter_quality": args.filter_quality,
        "filter_tier": args.filter_tier,
        "items": reports,
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "total_written": summary["total_written"],
                "conversion_status": summary["conversion_status"],
                "quality": summary["quality"],
                "training_tier": summary["training_tier"],
            },
            indent=2,
        )
    )
    return 0


def _cmd_benchcad_qa_eval(args: argparse.Namespace) -> int:
    items = []
    answerable = 0
    matched = 0
    in_scope = 0
    in_scope_matched = 0
    by_type: dict[str, Counter[str]] = {}

    for row in iter_benchcad_qa_rows(args.dataset, limit=args.limit):
        code, _, report = convert_cadquery_traced_source(
            row.gt_code,
            graph_id=row.stem,
            stem=row.stem,
            family=row.family,
            validate=args.validate,
            export_model_json=False,
            write_trace=False,
            use_subprocess=args.subprocess,
        )
        qa_score = score_code_qa(
            sftc_source=code,
            question=row.question,
            answer=row.answer,
            qa_type=row.qa_type,
            feature_manifest=report.feature_manifest,
        )
        if qa_score.answerable:
            answerable += 1
        if qa_score.match:
            matched += 1
        if qa_score.scope != "cq_structure":
            in_scope += 1
            if qa_score.match:
                in_scope_matched += 1
        qa_type = qa_score.qa_type or row.qa_type or "unknown"
        by_type.setdefault(qa_type, Counter())
        by_type[qa_type]["total"] += 1
        if qa_score.scope == "cq_structure":
            by_type[qa_type]["cq_structure"] += 1
        if qa_score.answerable:
            by_type[qa_type]["answerable"] += 1
        if qa_score.match:
            by_type[qa_type]["match"] += 1

        items.append(
            {
                "stem": row.stem,
                "family": row.family,
                "qa_id": row.qa_id,
                "qa_type": qa_type,
                "level": row.level,
                "question": row.question,
                "answer": row.answer,
                "training_tier": report.training_tier,
                "quality": report.quality,
                "feature_coverage": (report.structure or {}).get("feature_coverage"),
                "code_qa": qa_score.to_dict(),
            }
        )

    total = len(items)
    summary = {
        "total": total,
        "code_qa_answerable_rate": answerable / total if total else 0.0,
        "code_qa_match_rate": matched / total if total else 0.0,
        "code_qa_in_scope": in_scope,
        "code_qa_in_scope_match_rate": in_scope_matched / in_scope if in_scope else 0.0,
        "by_qa_type": {key: dict(value) for key, value in sorted(by_type.items())},
        "items": items,
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "total": summary["total"],
                "code_qa_answerable_rate": summary["code_qa_answerable_rate"],
                "code_qa_match_rate": summary["code_qa_match_rate"],
                "code_qa_in_scope_match_rate": summary["code_qa_in_scope_match_rate"],
                "by_qa_type": summary["by_qa_type"],
            },
            indent=2,
        )
    )
    return 0


def _cmd_benchcad_edit_eval(args: argparse.Namespace) -> int:
    items = []
    align_count = 0
    by_type: dict[str, Counter[str]] = {}

    for row in iter_benchcad_edit_rows(args.dataset, limit=args.limit):
        orig_code, _, orig_report = convert_cadquery_traced_source(
            row.orig_code,
            graph_id=f"{row.record_id}_orig",
            stem=f"{row.record_id}_orig",
            family=row.family,
            validate=args.validate,
            export_model_json=False,
            write_trace=False,
            use_subprocess=args.subprocess,
        )
        gt_code, _, gt_report = convert_cadquery_traced_source(
            row.gt_code,
            graph_id=f"{row.record_id}_gt",
            stem=f"{row.record_id}_gt",
            family=row.family,
            validate=args.validate,
            export_model_json=False,
            write_trace=False,
            use_subprocess=args.subprocess,
        )
        geometry_ok = None
        if args.validate:
            geometry_ok = gt_report.quality in {"accepted", "partial"} and bool(
                (gt_report.validation or {}).get("scad", {}).get("valid")
            )
        edit_score = score_edit(
            orig_sftc=orig_code,
            gt_sftc=gt_code,
            instruction=row.instruction,
            edit_geometry_ok=geometry_ok,
            category_label=row.category_label,
        )
        if edit_score.edit_instruction_align:
            align_count += 1
        key = row.category_label or row.edit_type or "unknown"
        by_type.setdefault(key, Counter())
        by_type[key]["total"] += 1
        if edit_score.edit_instruction_align:
            by_type[key]["align"] += 1
        if edit_score.edit_param_diff_count:
            by_type[key]["has_param_diff"] += 1

        items.append(
            {
                "record_id": row.record_id,
                "family": row.family,
                "edit_type": row.edit_type,
                "category_label": row.category_label,
                "instruction": row.instruction,
                "orig_tier": orig_report.training_tier,
                "gt_tier": gt_report.training_tier,
                "edit": edit_score.to_dict(),
            }
        )

    total = len(items)
    summary = {
        "total": total,
        "edit_instruction_align_rate": align_count / total if total else 0.0,
        "by_edit_type": {key: dict(value) for key, value in sorted(by_type.items())},
        "items": items,
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "total": summary["total"],
                "edit_instruction_align_rate": summary["edit_instruction_align_rate"],
                "by_edit_type": summary["by_edit_type"],
            },
            indent=2,
        )
    )
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    import sys

    tools_root = Path(__file__).resolve().parents[1]
    if str(tools_root) not in sys.path:
        sys.path.insert(0, str(tools_root))
    from stats_report import _iter_meta_files, _load_items, summarize_items

    if args.report:
        items = _load_items(Path(args.report))
    elif args.output_dir:
        items = list(_iter_meta_files(Path(args.output_dir)))
    else:
        raise SystemExit("stats requires --report or --output-dir")

    summary = summarize_items(items)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.write:
        Path(args.write).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="CadQuery → SimpleCAD SFTC converter")
    sub = parser.add_subparsers(dest="command", required=True)

    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--validate",
        action="store_true",
        help="execute CadQuery + SimpleCAD and compare volume/bbox",
    )
    parent.add_argument(
        "--volume-threshold",
        type=float,
        default=0.02,
        help="max relative volume error for accepted quality",
    )
    parent.add_argument(
        "--bbox-threshold",
        type=float,
        default=0.05,
        help="max relative bbox dimension error for accepted quality",
    )

    convert = sub.add_parser("convert", parents=[parent], help="convert one CadQuery file")
    convert.add_argument("--input", required=True)
    convert.add_argument("--output", required=True)
    convert.add_argument("--graph-id", default="")
    convert.add_argument("--stem", default="")
    convert.add_argument("--family", default="")
    convert.add_argument("--meta", default=None)
    convert.set_defaults(func=_cmd_convert)

    benchcad = sub.add_parser("benchcad", parents=[parent], help="convert BenchCAD parquet shards")
    benchcad.add_argument("--dataset", required=True)
    benchcad.add_argument("--output-dir", required=True)
    benchcad.add_argument("--limit", type=int, default=None)
    benchcad.add_argument("--report", default=None)
    benchcad.add_argument(
        "--filter-quality",
        nargs="+",
        choices=["accepted", "partial", "rejected"],
        default=None,
        help="write only rows matching quality tiers",
    )
    benchcad.set_defaults(func=_cmd_benchcad)

    benchcad_traced = sub.add_parser(
        "benchcad-traced",
        parents=[parent],
        help="convert BenchCAD parquet shards via runtime tracer",
    )
    benchcad_traced.add_argument("--dataset", required=True)
    benchcad_traced.add_argument("--output-dir", required=True)
    benchcad_traced.add_argument("--limit", type=int, default=None)
    benchcad_traced.add_argument("--report", default=None)
    benchcad_traced.add_argument(
        "--emit",
        choices=["sftc", "both"],
        default="both",
        help="write SFTC only, or SFTC + model.json sidecar (default: both)",
    )
    benchcad_traced.add_argument(
        "--subprocess",
        action="store_true",
        help="run CadQuery tracer in an isolated subprocess",
    )
    benchcad_traced.add_argument(
        "--filter-quality",
        nargs="+",
        choices=["accepted", "partial", "rejected"],
        default=None,
        help="write only rows matching quality tiers",
    )
    benchcad_traced.add_argument(
        "--filter-tier",
        nargs="+",
        choices=["A", "B", "C", "reject"],
        default=None,
        help="write only rows matching training_tier (requires --validate for geometry tiers)",
    )
    benchcad_traced.set_defaults(func=_cmd_benchcad_traced)

    qa_eval = sub.add_parser(
        "benchcad-qa-eval",
        parents=[parent],
        help="score BenchCAD QA code-answerability (exploration, no JSONL export)",
    )
    qa_eval.add_argument("--dataset", required=True)
    qa_eval.add_argument("--limit", type=int, default=None)
    qa_eval.add_argument("--report", default=None)
    qa_eval.add_argument("--subprocess", action="store_true")
    qa_eval.set_defaults(func=_cmd_benchcad_qa_eval)

    edit_eval = sub.add_parser(
        "benchcad-edit-eval",
        parents=[parent],
        help="score BenchCAD edit-bench param diffs (exploration, no JSONL export)",
    )
    edit_eval.add_argument("--dataset", required=True)
    edit_eval.add_argument("--limit", type=int, default=None)
    edit_eval.add_argument("--report", default=None)
    edit_eval.add_argument("--subprocess", action="store_true")
    edit_eval.set_defaults(func=_cmd_benchcad_edit_eval)

    stats = sub.add_parser("stats", help="summarize traced conversion meta/reports")
    stats.add_argument("--report", default=None)
    stats.add_argument("--output-dir", default=None)
    stats.add_argument("--write", default=None)
    stats.set_defaults(func=_cmd_stats)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
