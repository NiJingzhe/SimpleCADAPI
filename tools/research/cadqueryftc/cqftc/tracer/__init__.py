"""Runtime CadQuery tracer subpackage (runs under the cadquery venv)."""

from .cq_runner import run_cadquery_traced, run_cadquery_traced_inprocess
from .instrument import install_instrumentation, remove_instrumentation
from .trace_schema import GeoFingerprint, OperationTrace, TraceStep

__all__ = [
    "GeoFingerprint",
    "OperationTrace",
    "TraceStep",
    "install_instrumentation",
    "remove_instrumentation",
    "run_cadquery_traced",
    "run_cadquery_traced_inprocess",
]
