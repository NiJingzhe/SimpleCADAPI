"""Execute generated FreeCAD scripts and validate exported files."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Optional


def _json_ascii(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def discover_freecad_executable() -> Optional[str]:
    """Return the first available FreeCAD command-line executable."""

    candidates = [
        shutil.which("FreeCADCmd"),
        shutil.which("freecadcmd"),
        shutil.which("FreeCAD"),
        "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
        "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def export_freecad_script_to_fcstd(
    script: str,
    output_path: str,
    *,
    freecad_executable: str,
) -> str:
    """Execute a generated script and require a non-empty FCStd result."""

    resolved_output_path = os.path.abspath(output_path)
    save_tail = (
        f"\nOUTPUT_PATH = {_json_ascii(resolved_output_path)}\n"
        "_apply_result_visibility(RESULT_NODE_IDS)\n"
        "_set_active_result_object(RESULT_NODE_IDS)\n"
        "_restore_occurrence_tree_visibility()\n"
        "_save_fcstd_with_gui_visibility(OUTPUT_PATH)\n"
        "print(OUTPUT_PATH)\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_simplecad_freecad_export.py", delete=False
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)
        handle.write(save_tail)

    completed = subprocess.run(
        [freecad_executable, temp_script_path],
        check=True,
        text=True,
        capture_output=True,
    )
    if (
        not os.path.exists(resolved_output_path)
        or os.path.getsize(resolved_output_path) <= 0
    ):
        raise RuntimeError(
            "FreeCAD export completed without creating a non-empty .FCStd file. "
            f"stderr={completed.stderr.strip()!r}"
        )
    return output_path


__all__ = ["discover_freecad_executable", "export_freecad_script_to_fcstd"]
