"""Public FreeCAD translator entrypoints."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Optional

from ...errors import raise_harness_error
from .script_translator import FreeCADScriptTranslator


def _json_ascii(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _discover_freecad_executable() -> Optional[str]:
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


def translate_model_json_to_freecad_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
) -> str:
    """Translate exported model JSON into a FreeCAD Python script.

    Part/Assembly product nodes are emitted as editable FreeCAD document
    structure: parts use `App::Part`, assemblies use native
    `Assembly::AssemblyObject`, part components use `App::Link`, and
    subassembly components use `Assembly::AssemblyLink` when the Assembly
    workbench module is available.
    """

    return FreeCADScriptTranslator(
        document_name=document_name
    ).translate_model_json_to_script(json_str)


def translate_model_json_to_fcstd(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    freecad_cmd: Optional[str] = None,
) -> str:
    """Translate canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD.

    Functional sketch promotions are written as visible `Sketcher::SketchObject`
    nodes with mapped/skipped constraint evidence. Exact B-spline edges are
    exported to FreeCAD using `Part.BSplineCurve().buildFromPolesMultsKnots(...)`.
    Safe single-use profile transforms such as section rotate/translate chains are
    folded into the section object's placement so downstream `Part::Loft` receives
    already-positioned sections instead of placement-bearing `App::Link` proxies.
    Part/Assembly product nodes are written as editable FreeCAD assembly structure:
    parts use `App::Part`, assemblies use native `Assembly::AssemblyObject`, part
    components use `App::Link`, and nested assembly components use
    `Assembly::AssemblyLink`. Explicit assembly-to-compound projections remain in
    the document for geometry workflows but do not replace the visible assembly
    tree.
    """

    freecad_exe = freecad_cmd or _discover_freecad_executable()
    if not freecad_exe:
        raise_harness_error(
            operation="translate_model_json_to_fcstd",
            what_happened="Could not locate a FreeCAD command-line executable.",
            possible_causes=[
                "FreeCADCmd is not installed or not available on PATH.",
                "Only the GUI app is installed and no CLI entrypoint is reachable.",
            ],
            how_to_fix=[
                "Install FreeCAD with FreeCADCmd, or pass freecad_cmd=... explicitly.",
                "Make sure FreeCADCmd or FreeCAD is on PATH.",
            ],
            error=FileNotFoundError("FreeCADCmd/FreeCAD not found"),
        )

    script = translate_model_json_to_freecad_script(
        json_str, document_name=document_name
    )
    resolved_output_path = os.path.abspath(output_path)
    save_tail = (
        f"\nOUTPUT_PATH = {_json_ascii(resolved_output_path)}\n"
        "_apply_result_visibility(RESULT_NODE_IDS)\n"
        "_set_active_result_object(RESULT_NODE_IDS)\n"
        "_save_fcstd_with_gui_visibility(OUTPUT_PATH)\n"
        "print(OUTPUT_PATH)\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_simplecad_freecad_export.py", delete=False
    ) as handle:
        temp_script_path = handle.name
        handle.write(script)
        handle.write(save_tail)

    try:
        completed = subprocess.run(
            [freecad_exe, temp_script_path],
            check=True,
            text=True,
            capture_output=True,
        )
        if not os.path.exists(resolved_output_path) or os.path.getsize(resolved_output_path) <= 0:
            raise RuntimeError(
                "FreeCAD export completed without creating a non-empty .FCStd file. "
                f"stderr={completed.stderr.strip()!r}"
            )
        return output_path
    except Exception as e:
        raise_harness_error(
            operation="translate_model_json_to_fcstd",
            what_happened="Failed to execute the generated FreeCAD export script.",
            possible_causes=[
                "FreeCADCmd started but the generated script hit an unsupported API call.",
                "The output path is invalid or not writable.",
                "The installed FreeCAD build lacks Part or Spreadsheet support needed by the translator.",
            ],
            how_to_fix=[
                "Inspect the generated script first with translate_model_json_to_freecad_script().",
                "Use a writable .FCStd output path.",
                "Run the same script manually inside a matching FreeCAD environment to isolate runtime differences.",
            ],
            error=e,
        )
