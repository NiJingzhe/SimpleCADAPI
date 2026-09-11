"""Execute generated SolidWorks scripts and export STEP files."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from typing import Optional


def export_solidworks_script_to_step(
    script: str,
    output_path: str,
    *,
    python_exe: Optional[str] = None,
) -> str:
    """Run one generated SolidWorks script and return the STEP output path."""

    resolved_output_path = os.path.abspath(output_path)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="_simplecad_solidworks_export.py",
        delete=False,
        encoding="utf-8",
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)

    env = os.environ.copy()
    src_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env["PYTHONPATH"] = (
        src_root
        if not env.get("PYTHONPATH")
        else src_root + os.pathsep + env["PYTHONPATH"]
    )

    try:
        try:
            completed = subprocess.run(
                [python_exe or sys.executable, temp_script_path],
                check=True,
                text=True,
                capture_output=True,
                env=env,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "SolidWorks export script failed. "
                f"stdout={exc.stdout!r} stderr={exc.stderr!r}"
            ) from exc
        if (
            not os.path.exists(resolved_output_path)
            or os.path.getsize(resolved_output_path) <= 0
        ):
            raise RuntimeError(
                "SolidWorks export completed without creating a non-empty STEP file. "
                f"stdout={completed.stdout.strip()!r} "
                f"stderr={completed.stderr.strip()!r}"
            )
        return output_path
    finally:
        try:
            os.unlink(temp_script_path)
        except OSError:
            pass


__all__ = ["export_solidworks_script_to_step"]
