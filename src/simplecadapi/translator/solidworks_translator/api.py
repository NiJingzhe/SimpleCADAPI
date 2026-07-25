"""Public SolidWorks translator entrypoints."""

from __future__ import annotations

from typing import Optional

from .compiler import translate_model_json_to_solidworks_step as _export_step
from .translator import SolidWorksTranslator


def translate_model_json_to_solidworks_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
    *,
    output_path: Optional[str] = None,
    visible: bool = False,
    source_kernel_fallback: bool = False,
) -> str:
    """Translate canonical model JSON into a SolidWorks automation script."""

    return SolidWorksTranslator(
        document_name=document_name,
        output_path=output_path,
        visible=visible,
        source_kernel_fallback=source_kernel_fallback,
    ).translate_model_json_to_script(json_str)


def export_model_json_to_solidworks_step(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    visible: bool = False,
    python_exe: Optional[str] = None,
    source_kernel_fallback: bool = False,
) -> str:
    """Execute SolidWorks COM automation and export a STEP file."""

    return _export_step(
        json_str,
        output_path,
        document_name=document_name,
        visible=visible,
        python_exe=python_exe,
        source_kernel_fallback=source_kernel_fallback,
    )


translate_model_json_to_solidworks_step = export_model_json_to_solidworks_step

__all__ = [
    "export_model_json_to_solidworks_step",
    "translate_model_json_to_solidworks_script",
    "translate_model_json_to_solidworks_step",
]
