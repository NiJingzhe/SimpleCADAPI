"""CadQuery → FTC translation toolkit (tools/research/cadquery).

Four-stage structure mirroring tools/research/histjson:

1. ``cadquery_trace.py``    — runtime capture (runs inside the cadquery venv)
2. ``cadquery_to_ftc.py``   — the translator: trace JSON → FTC source
3. ``cadquery_validate.py`` — external acceptance: volume/bbox reconciliation
4. ``cadquery_profile.py``  — dataset / trace coverage survey

The translator only translates; correctness questions live in the external
tools.
"""

from .benchcad import BenchCADRow, iter_benchcad_rows
from .replay import replay_trace_to_ftc
from .tracer.trace_schema import GeoFingerprint, OperationTrace, TraceStep

__all__ = [
    "BenchCADRow",
    "GeoFingerprint",
    "OperationTrace",
    "TraceStep",
    "iter_benchcad_rows",
    "replay_trace_to_ftc",
]
