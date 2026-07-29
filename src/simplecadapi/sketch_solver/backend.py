"""Backend protocol and process-local sketch solver selection."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterator, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..sketch import Sketch, SketchSolveResult


@dataclass(frozen=True)
class SketchSolverOptions:
    """Backend-neutral options for one solve request.

    A backend may not support every numerical hint.  It must still preserve
    the result/status contract and must not silently invoke another backend.
    """

    tolerance: float = 1e-7
    max_iterations: int = 80


@runtime_checkable
class SketchSolverBackend(Protocol):
    """Boundary implemented by a sketch constraint solver backend."""

    @property
    def name(self) -> str:
        """Stable backend identifier persisted in solve evidence."""
        ...

    @property
    def version(self) -> str:
        """Backend implementation/package version."""
        ...

    def solve(
        self,
        sketch: "Sketch",
        *,
        options: SketchSolverOptions,
    ) -> "SketchSolveResult":
        """Solve a backend-neutral sketch document without mutating it."""
        ...


_BACKENDS: Dict[str, SketchSolverBackend] = {}
_DEFAULT_BACKEND_NAME = "py-slvs"


def register_sketch_solver_backend(
    backend: SketchSolverBackend,
    *,
    replace: bool = False,
) -> None:
    """Register a backend instance under its stable ``name``."""

    name = str(backend.name).strip()
    if not name:
        raise ValueError("A sketch solver backend requires a non-empty name")
    if name in _BACKENDS and not replace:
        raise ValueError(f"Sketch solver backend '{name}' is already registered")
    _BACKENDS[name] = backend


def _ensure_builtin_backend(name: str) -> None:
    if name == "py-slvs" and name not in _BACKENDS:
        from .py_slvs_backend import PySlvsSketchSolverBackend

        register_sketch_solver_backend(PySlvsSketchSolverBackend())


def get_sketch_solver_backend(name: str | None = None) -> SketchSolverBackend:
    """Resolve a registered backend; omitted ``name`` selects the default."""

    selected = str(name or _DEFAULT_BACKEND_NAME)
    _ensure_builtin_backend(selected)
    try:
        return _BACKENDS[selected]
    except KeyError as exc:
        available = ", ".join(sorted(_BACKENDS)) or "none"
        raise ValueError(
            f"Unknown sketch solver backend '{selected}'; registered backends: {available}"
        ) from exc


def get_default_sketch_solver_backend() -> SketchSolverBackend:
    """Return the process-wide default sketch solver backend."""

    return get_sketch_solver_backend(_DEFAULT_BACKEND_NAME)


def set_default_sketch_solver_backend(backend: str | SketchSolverBackend) -> None:
    """Set the process-wide default by registered name or backend instance."""

    global _DEFAULT_BACKEND_NAME
    if isinstance(backend, str):
        selected = get_sketch_solver_backend(backend)
    else:
        register_sketch_solver_backend(backend, replace=True)
        selected = backend
    _DEFAULT_BACKEND_NAME = selected.name


@contextmanager
def sketch_solver_backend(
    backend: str | SketchSolverBackend,
) -> Iterator[SketchSolverBackend]:
    """Temporarily select a default backend and restore it afterwards."""

    previous = _DEFAULT_BACKEND_NAME
    set_default_sketch_solver_backend(backend)
    try:
        yield get_default_sketch_solver_backend()
    finally:
        set_default_sketch_solver_backend(previous)


__all__ = [
    "SketchSolverBackend",
    "SketchSolverOptions",
    "get_default_sketch_solver_backend",
    "get_sketch_solver_backend",
    "register_sketch_solver_backend",
    "set_default_sketch_solver_backend",
    "sketch_solver_backend",
]
