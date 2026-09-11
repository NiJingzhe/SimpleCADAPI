"""Subprocess worker: constraint recovery with a wall-clock escape hatch.

SolveSpace's redundancy analysis (``FindWhichToRemoveToFixJacobian``) can be
combinatorially explosive on large freeform snapshots; a single pathological
candidate solve can run for minutes inside the C extension where Python-level
timeouts cannot reach.  Large sketches therefore recover in this worker so
the parent can enforce a timeout and degrade honestly to "no constraints"
instead of hanging the translator.
"""

from __future__ import annotations

import json
import sys

from .constraints import recover_constraints


def main() -> int:
    snapshot = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    report = recover_constraints(snapshot)
    sys.stdout.write(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
