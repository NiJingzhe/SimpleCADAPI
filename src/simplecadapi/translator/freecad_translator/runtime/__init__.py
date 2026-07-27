"""Runtime source embedded in generated FreeCAD scripts."""

from functools import lru_cache
from pathlib import Path

_FRAGMENT_NAMES = (
    "metadata.py",
    "assemblies.py",
    "products.py",
    "persistence.py",
    "geometry.py",
    "selections.py",
    "curves.py",
    "sketches.py",
    "expressions.py",
)


@lru_cache(maxsize=1)
def assemble_runtime_source() -> str:
    runtime_dir = Path(__file__).resolve().parent
    return "".join(
        (runtime_dir / name).read_text(encoding="utf-8")
        for name in _FRAGMENT_NAMES
    )


__all__ = ["assemble_runtime_source"]
