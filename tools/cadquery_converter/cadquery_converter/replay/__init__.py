"""Replay package for traced CadQuery programs."""

from .op_map import CONTEXT_ONLY_OPS, SUPPORTED_TRACE_OPS

__all__ = [
    "CONTEXT_ONLY_OPS",
    "SUPPORTED_TRACE_OPS",
    "filter_meaningful_steps",
    "replay_trace_to_sftc",
]


def __getattr__(name: str):
    if name in {"filter_meaningful_steps", "replay_trace_to_sftc"}:
        from .emit_from_trace import filter_meaningful_steps, replay_trace_to_sftc

        return {
            "filter_meaningful_steps": filter_meaningful_steps,
            "replay_trace_to_sftc": replay_trace_to_sftc,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
