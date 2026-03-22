#!/usr/bin/env python3
"""Bootstrap runtime package in a persistent Python REPL/kernel."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


PACKAGE_SPEC = "simplecadapi==2.0.6"
CASES_MODULE = "simplecad_self_evolve_cases"


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _cases_root() -> Path:
    return _script_dir().parent / "cases"


def _activate_cases_path() -> None:
    cases_root = str(_cases_root())
    os.environ["SIMPLECAD_CASES_ROOT"] = cases_root
    os.environ["SIMPLECAD_CASES_MODULE"] = CASES_MODULE

    current_pythonpath = os.environ.get("PYTHONPATH", "")
    parts = [item for item in current_pythonpath.split(os.pathsep) if item]
    if cases_root not in parts:
        parts.insert(0, cases_root)
        os.environ["PYTHONPATH"] = os.pathsep.join(parts)

    if cases_root not in sys.path:
        sys.path.insert(0, cases_root)


def _install(with_jupyter: bool = False) -> None:
    cmd = [str(_script_dir() / "install.sh")]
    if with_jupyter:
        cmd.append("--with-jupyter")
    env = os.environ.copy()
    env.setdefault("PYTHON_BIN", sys.executable)
    subprocess.run(cmd, check=True, env=env)


def _has_simplecadapi() -> bool:
    try:
        import simplecadapi  # noqa: F401
    except Exception:
        return False
    return True


def _has_jupyter_deps() -> bool:
    try:
        import jupyterlab  # noqa: F401
        import ipykernel  # noqa: F401
    except Exception:
        return False
    return True


def activate(check: bool = False, with_jupyter: bool = False) -> int:
    skill_root = _script_dir().parent
    os.environ["SIMPLECAD_SKILL_ROOT"] = str(skill_root)
    _activate_cases_path()

    if not _has_simplecadapi():
        print(f"Installing runtime package {PACKAGE_SPEC} ...")
        _install(with_jupyter=with_jupyter)

    if with_jupyter and not _has_jupyter_deps():
        print("Installing Jupyter dependencies ...")
        _install(with_jupyter=True)

    if check and not _has_simplecadapi():
        print("Runtime install failed: cannot import simplecadapi", file=sys.stderr)
        return 1

    print(f"Skill runtime activated from site-packages: {PACKAGE_SPEC}")
    print(f"Skill cases module ready: {CASES_MODULE}.evolve")
    print("You can now run: import simplecadapi as scad")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap SimpleCAD runtime in persistent Python process"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that import simplecadapi succeeds after bootstrap",
    )
    parser.add_argument(
        "--with-jupyter",
        action="store_true",
        help="Also ensure jupyterlab and ipykernel are installed",
    )
    args = parser.parse_args()
    raise SystemExit(activate(check=args.check, with_jupyter=args.with_jupyter))


if __name__ == "__main__":
    main()
