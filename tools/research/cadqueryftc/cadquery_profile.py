"""Stage 4 — dataset / trace coverage survey.

Answers "what is in the data" before any conversion decision: op histograms,
coverage of the replayer's supported op set, unsupported-op frequency, and
per-family traces of the committing ops.  Read-only; runs on trace JSONs from
stage 1 (no cadquery needed) or on the BenchCAD parquet directly with
``--dataset`` (needs pyarrow).

Usage:

    .venv/bin/python tools/research/cadquery/cadquery_profile.py \
        --traces-dir out/traces --report out/profile.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from cqftc.op_map import SUPPORTED_TRACE_OPS  # noqa: E402


def profile_traces(traces_dir: Path) -> dict:
    op_counter: Counter[str] = Counter()
    selector_counter: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    stems = 0
    unsupported_rows = 0
    for trace_path in sorted(traces_dir.glob("*.trace.json")):
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
        stems += 1
        statuses[str(payload.get("cq_status", "ok"))] += 1
        row_unsupported = False
        for step in payload.get("steps", []):
            op = str(step.get("op", ""))
            op_counter[op] += 1
            if op not in SUPPORTED_TRACE_OPS and op != "Workplane":
                row_unsupported = True
            selector = step.get("selector")
            if selector:
                selector_counter[str(selector)] += 1
        if row_unsupported:
            unsupported_rows += 1

    return {
        "traces": stems,
        "cq_status": dict(statuses),
        "op_histogram": dict(op_counter.most_common()),
        "selector_histogram": dict(selector_counter.most_common()),
        "rows_with_unsupported_ops": unsupported_rows,
        "supported_op_coverage": {
            op: (op in SUPPORTED_TRACE_OPS) for op in sorted(op_counter)
        },
    }


def profile_dataset(dataset_root: str) -> dict:
    from cqftc.benchcad import iter_benchcad_rows

    families: Counter[str] = Counter()
    difficulties: Counter[str] = Counter()
    total = 0
    for row in iter_benchcad_rows(dataset_root):
        total += 1
        families[row.family] += 1
        difficulties[row.difficulty] += 1
    return {
        "rows": total,
        "families": dict(families.most_common()),
        "difficulties": dict(difficulties.most_common()),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--traces-dir", default="", help="profile every *.trace.json in a directory")
    parser.add_argument("--dataset", default="", help="profile BenchCAD parquet rows (needs pyarrow)")
    parser.add_argument("--report", default="", help="write a report JSON to this path")
    args = parser.parse_args(argv)

    if not args.traces_dir and not args.dataset:
        parser.error("one of --traces-dir / --dataset is required")

    report: dict = {}
    if args.traces_dir:
        report["traces"] = profile_traces(Path(args.traces_dir))
        print(json.dumps(report["traces"]["op_histogram"], indent=2))
        print(f"rows with unsupported ops: {report['traces']['rows_with_unsupported_ops']}")
    if args.dataset:
        report["dataset"] = profile_dataset(args.dataset)
        print(json.dumps(report["dataset"], indent=2))

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
