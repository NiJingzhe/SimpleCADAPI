"""Runtime source embedded in generated SolidWorks scripts."""

from functools import lru_cache
from pathlib import Path

_FRAGMENT_NAMES = (
    "geometry.py",
    "com_compat.py",
    "selections.py",
    "metadata.py",
    "sketches.py",
    "features.py",
    "booleans.py",
    "products.py",
    "assemblies.py",
    "persistence.py",
    "model.py",
)


@lru_cache(maxsize=1)
def assemble_runtime_source() -> str:
    runtime_dir = Path(__file__).resolve().parent
    shared = (runtime_dir.parent.parent / "geometry_signature.py").read_text(encoding="utf-8")
    versions = (runtime_dir.parent / "versions.py").read_text(encoding="utf-8")
    return versions + "\n" + shared + "\n" + "".join(
        (runtime_dir / name).read_text(encoding="utf-8") for name in _FRAGMENT_NAMES
    )


__all__ = ["assemble_runtime_source"]
