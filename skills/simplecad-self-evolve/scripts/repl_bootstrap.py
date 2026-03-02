#!/usr/bin/env python3
"""Bootstrap skill import path inside a persistent Python process."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def activate(check: bool = False) -> int:
    script_path = Path(__file__).resolve()
    skill_root = script_path.parent.parent
    skill_src = skill_root / "assets" / "project_snapshot" / "src"

    if not skill_src.exists():
        print(f"Error: missing skill source path: {skill_src}", file=sys.stderr)
        return 1

    skill_src_str = str(skill_src)
    if skill_src_str not in sys.path:
        sys.path.insert(0, skill_src_str)

    os.environ["SIMPLECAD_SKILL_ROOT"] = str(skill_root)
    os.environ["SIMPLECAD_SKILL_SRC"] = skill_src_str

    current = os.environ.get("PYTHONPATH", "")
    paths = [item for item in current.split(os.pathsep) if item] if current else []
    if skill_src_str not in paths:
        os.environ["PYTHONPATH"] = (
            os.pathsep.join([skill_src_str, *paths]) if paths else skill_src_str
        )

    if check:
        try:
            import simplecadapi  # noqa: F401
        except Exception as exc:
            print(f"Path injected but import check failed: {exc}", file=sys.stderr)
            return 1

    print(f"Activated skill source: {skill_src_str}")
    print("You can now run: import simplecadapi as scad")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Activate SimpleCAD skill import path in current Python process"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Also check that `import simplecadapi` succeeds",
    )
    args = parser.parse_args()
    raise SystemExit(activate(check=args.check))


if __name__ == "__main__":
    main()
