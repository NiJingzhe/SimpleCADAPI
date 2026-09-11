"""Subprocess worker: execute traced CadQuery and emit OperationTrace JSON on stdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .cq_runner import run_cadquery_traced_inprocess


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python -m cqftc.tracer._trace_worker <source.py>", file=sys.stderr)
        return 2

    source = Path(args[0]).read_text(encoding="utf-8")
    trace = run_cadquery_traced_inprocess(source)
    sys.stdout.write(json.dumps(trace.to_dict(), ensure_ascii=False))
    return 0 if trace.cq_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
