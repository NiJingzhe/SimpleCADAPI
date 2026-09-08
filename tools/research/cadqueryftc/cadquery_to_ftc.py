"""Stage 2 — the translator: CadQuery trace JSON → FTC Python source.

Pure translation, no cadquery needed: the trace recorded at stage 1 fully
determines the output.  Unsupported trace content becomes notes in the block
comments and the meta sidecar — never silent drops, never in-source checks.

Usage:

    .venv/bin/python tools/research/cadquery/cadquery_to_ftc.py \
        --trace out/traces/sample.trace.json --out out/ftc
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from cqftc.replay import replay_trace_to_ftc  # noqa: E402
from cqftc.tracer.trace_schema import OperationTrace  # noqa: E402


def translate_trace_file(trace_path: Path, out_dir: Path) -> tuple[str, str, dict]:
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    stem = payload.pop("stem", trace_path.stem.replace(".trace", ""))
    family = payload.pop("family", "")
    trace = OperationTrace.from_dict(payload)
    source, meta = replay_trace_to_ftc(trace, stem=stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    ftc_path = out_dir / f"{stem}.ftc.py"
    ftc_path.write_text(source, encoding="utf-8")
    meta_payload = {"stem": stem, "family": family, **meta}
    meta_path = out_dir / f"{stem}.meta.json"
    meta_path.write_text(
        json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return stem, source, meta_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trace", help="single trace JSON from stage 1")
    parser.add_argument("--traces-dir", help="translate every *.trace.json in a directory")
    parser.add_argument("--out", default="tools/research/cadquery/out/ftc", help="output directory")
    args = parser.parse_args(argv)

    if not args.trace and not args.traces_dir:
        parser.error("one of --trace / --traces-dir is required")

    out_dir = Path(args.out)
    paths: list[Path] = []
    if args.trace:
        paths.append(Path(args.trace))
    if args.traces_dir:
        paths.extend(sorted(Path(args.traces_dir).glob("*.trace.json")))

    for trace_path in paths:
        stem, _source, meta = translate_trace_file(trace_path, out_dir)
        status = meta.get("status", "ok")
        notes = len(meta.get("unsupported", []))
        print(f"{stem}: {status} ({meta.get('feature_count', 0)} features, {notes} notes)")
    print(f"translated {len(paths)} trace(s) -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
