"""Stage 1 — runtime trace capture: CadQuery source → trace JSON.

Runs inside the CadQuery environment (``.venv-cq``, Python 3.11 +
cadquery 2.8).  Executes each program with the Workplane instrumentation
installed and writes one ``<stem>.trace.json`` per row; the trace carries the
operation steps, resolved plane frames, selection fingerprints, and the
ground-truth volume/bbox used later by the external validator.

Usage (from the repo root, with the cadquery venv active):

    .venv-cq/bin/python tools/research/cadquery/cadquery_trace.py \
        --input sample.cq.py --stem sample --out out/

    .venv-cq/bin/python tools/research/cadquery/cadquery_trace.py \
        --dataset /path/to/BenchCAD --out out/ --limit 20 --stride 7
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from cqftc.benchcad import iter_benchcad_rows  # noqa: E402
from cqftc.tracer.cq_runner import run_cadquery_traced  # noqa: E402


def write_trace(source: str, stem: str, family: str, out_dir: Path, *, timeout: float) -> dict:
    trace = run_cadquery_traced(source, timeout=timeout, use_subprocess=False)
    payload = trace.to_dict()
    payload["stem"] = stem
    payload["family"] = family
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{stem}.trace.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    steps = len(payload.get("steps", []))
    status = payload.get("cq_status", "ok")
    print(f"{stem}: {status} ({steps} steps)")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", help="single CadQuery source file")
    parser.add_argument("--stem", default="", help="row stem (defaults to input file stem)")
    parser.add_argument("--dataset", help="BenchCAD dataset root (code_gen/data parquet shards)")
    parser.add_argument("--out", default="tools/research/cadquery/out/traces", help="output directory")
    parser.add_argument("--limit", type=int, default=None, help="max rows to trace")
    parser.add_argument("--stride", type=int, default=1, help="sample every Nth row")
    parser.add_argument("--timeout", type=float, default=120.0, help="per-row trace timeout (s)")
    args = parser.parse_args(argv)

    if not args.input and not args.dataset:
        parser.error("one of --input / --dataset is required")

    out_dir = Path(args.out)
    done = 0
    if args.input:
        source = Path(args.input).read_text(encoding="utf-8")
        stem = args.stem or Path(args.input).stem
        write_trace(source, stem, "", out_dir, timeout=args.timeout)
        done += 1

    if args.dataset:
        count = 0
        for row in iter_benchcad_rows(args.dataset):
            count += 1
            if (count - 1) % args.stride:
                continue
            write_trace(row.code, row.stem, row.family, out_dir, timeout=args.timeout)
            done += 1
            if args.limit is not None and done >= args.limit:
                break

    print(f"traced {done} row(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
