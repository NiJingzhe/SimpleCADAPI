"""Public SolidWorks translator entrypoints."""

from __future__ import annotations

from typing import Optional

from ...errors import raise_harness_error
from .exporter import export_solidworks_script_to_step
from .translator import SolidWorksTranslator
from .versions import SUPPORTED_SOLIDWORKS_VERSIONS, normalize_solidworks_version


def translate_model_json_to_solidworks_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
    *,
    output_path: Optional[str] = None,
    visible: bool = False,
    solidworks_version: str = "2025",
) -> str:
    """Translate canonical model JSON into a SolidWorks automation script.

    The generated script contains one ``runtime.emit_node(...)`` call per
    canonical graph node and drives SolidWorks through its COM automation
    API, mirroring the FreeCAD backend's generated-script layout.
    """

    return SolidWorksTranslator(
        document_name=document_name,
        output_path=output_path,
        visible=visible,
        solidworks_version=solidworks_version,
    ).translate_model_json_to_script(json_str, output_path=output_path)


def export_model_json_to_solidworks_step(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    visible: bool = False,
    solidworks_version: str = "2025",
    python_exe: Optional[str] = None,
) -> str:
    """Execute SolidWorks COM automation and export a STEP file."""

    solidworks_version = normalize_solidworks_version(solidworks_version)
    script = translate_model_json_to_solidworks_script(
        json_str,
        document_name=document_name,
        output_path=output_path,
        visible=visible,
        solidworks_version=solidworks_version,
    )
    try:
        return export_solidworks_script_to_step(
            script, output_path, python_exe=python_exe
        )
    except Exception as exc:
        raise_harness_error(
            operation="export_model_json_to_solidworks_step",
            what_happened="Failed to execute the generated SolidWorks export script.",
            possible_causes=[
                "SolidWorks is not installed, not licensed, or its COM server is not registered.",
                "pywin32 is unavailable in the Python interpreter used for the export.",
                "The model JSON contains an operation not yet mapped to a stable SolidWorks COM call.",
                "SolidWorks rejected a native feature, geometric selection, body boolean, or STEP SaveAs call.",
            ],
            how_to_fix=[
                "Open SolidWorks once interactively and confirm it can create and save parts.",
                "Inspect the generated script with translate_model_json_to_solidworks_script().",
                "Run the same script manually with the same Python interpreter to inspect COM errors.",
            ],
            error=exc,
        )


translate_model_json_to_solidworks_step = export_model_json_to_solidworks_step


def translate_product_package_to_solidworks_script(
    data,
    document_name: str = "SimpleCADProduct",
    *,
    output_path: Optional[str] = None,
    visible: bool = False,
    solidworks_version: str = "2025",
) -> str:
    """Translate one validated `.scadpkg` closure into SolidWorks automation."""

    artifact = SolidWorksTranslator(
        document_name=document_name,
        output_path=output_path,
        visible=visible,
        solidworks_version=solidworks_version,
    ).translate_product_package(data)
    assert isinstance(artifact.content, str)
    return artifact.content


__all__ = [
    "SUPPORTED_SOLIDWORKS_VERSIONS",
    "translate_product_package_to_solidworks_script",
]
