"""Public FreeCAD product translator entrypoints."""

from __future__ import annotations

from typing import Optional

from ...errors import raise_harness_error
from ..package_units import ProductPackageInput
from .exporter import discover_freecad_executable, export_freecad_script_to_fcstd
from .translator import FreeCADTranslator


def translate_product_package_to_freecad_script(
    data: ProductPackageInput,
    document_name: str = "SimpleCADProduct",
) -> str:
    """Translate one validated `.scadpkg` closure into a FreeCAD script."""

    artifact = FreeCADTranslator(document_name=document_name).translate_product_package(
        data
    )
    assert isinstance(artifact.content, str)
    return artifact.content


def translate_product_package_to_fcstd(
    data: ProductPackageInput,
    output_path: str,
    *,
    document_name: str = "SimpleCADProduct",
    freecad_cmd: Optional[str] = None,
) -> str:
    """Translate one validated `.scadpkg` closure into an editable `.FCStd`."""

    freecad_exe = freecad_cmd or discover_freecad_executable()
    if not freecad_exe:
        raise_harness_error(
            operation="translate_product_package_to_fcstd",
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
    script = translate_product_package_to_freecad_script(
        data, document_name=document_name
    )
    try:
        return export_freecad_script_to_fcstd(
            script,
            output_path,
            freecad_executable=freecad_exe,
        )
    except Exception as exc:
        raise_harness_error(
            operation="translate_product_package_to_fcstd",
            what_happened="Failed to execute the generated FreeCAD package script.",
            possible_causes=[
                "A definition-owned Feature Graph used an unsupported FreeCAD operation.",
                "A package reference did not resolve to an earlier definition.",
                "The output path is invalid or not writable.",
            ],
            how_to_fix=[
                "Inspect the generated package script.",
                "Use a writable .FCStd output path.",
                "Check the package definition closure and Feature Graph support.",
            ],
            error=exc,
        )


__all__ = [
    "translate_product_package_to_fcstd",
    "translate_product_package_to_freecad_script",
]
