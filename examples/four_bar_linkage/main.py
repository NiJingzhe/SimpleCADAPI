"""Build the four-bar linkage and capture its product package."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import simplecadapi as scad

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assembly import build_four_bar_linkage  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "out"


def main() -> None:
    """Build the closed linkage and capture the durable `.scadpkg`."""

    start = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = build_four_bar_linkage()
    build_s = time.perf_counter() - start

    package_path = OUT_DIR / "four_bar_linkage.scadpkg"
    capture_start = time.perf_counter()
    scad.capture(result, package_path, include_scene=False)
    capture_s = time.perf_counter() - capture_start

    print(f"[stage] build: {build_s:.1f}s")
    print(f"[stage] capture: {capture_s:.1f}s bytes={package_path.stat().st_size}")
    print(f"product_package={package_path}")


if __name__ == "__main__":
    main()
