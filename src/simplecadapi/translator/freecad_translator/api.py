"""Public FreeCAD translator entrypoints."""

from __future__ import annotations

from typing import Optional

from ...errors import raise_harness_error
from .exporter import discover_freecad_executable, export_freecad_script_to_fcstd
from .translator import FreeCADTranslator


def translate_model_json_to_freecad_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
) -> str:
    """Translate exported model JSON into a FreeCAD Python script.

    Geometry is emitted as FreeCAD occurrence trees. Serialized source assignment
    targets name native design objects, shared DAG inputs are copied per consuming
    result, and feature links preserve dependencies. Booleans are emitted as native
    recomputable `Part::Cut`, `Part::Fuse`, and `Part::Common` features. Stable node
    ids remain available as internal metadata.
    `apply_tag_rselection` nodes do not create FreeCAD features. Their canonical
    bindings and source node ids are attached to traceable geometry and visible
    result objects as `SimpleCADAppliedTags`, `SimpleCADTagBindings`, and
    `SimpleCADTagNodeIds`.
    The Tree View exposes only resolved product or standalone-geometry roots.
    Assembly projection compounds and link source definitions remain available
    for recomputation but are hidden from the user-facing document tree.
    """

    return FreeCADTranslator(
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
    Geometry results use FreeCAD objects directly: assignment targets name design
    objects and shared inputs receive independent occurrences per consumer. Native
    features preserve recomputing dependencies, including surface-dependent
    Booleans. Their classifications may vary across FreeCAD/OCCT versions. No
    presentation proxy, duplicate history tree, or hidden graph-object archive is
    created.
    `apply_tag_rselection` remains graph metadata rather than a FreeCAD feature;
    traceable geometry and visible result objects expose `SimpleCADAppliedTags`,
    `SimpleCADTagBindings`, and `SimpleCADTagNodeIds`.
    Part/Assembly product nodes are written as editable FreeCAD assembly structure:
    parts use `App::Part`, assemblies use native `Assembly::AssemblyObject`, part
    components use `App::Link`, and nested assembly components use
    `Assembly::AssemblyLink`. Explicit assembly-to-compound projections remain
    available for geometry workflows without creating a second user-facing root.
    Link source definitions remain in the document for recomputation, but the
    Tree View exposes only the resolved product or standalone-geometry roots.
    """

    freecad_exe = freecad_cmd or discover_freecad_executable()
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
    try:
        return export_freecad_script_to_fcstd(
            script,
            output_path,
            freecad_executable=freecad_exe,
        )
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


def export_model_json_to_fcstd(
    json_str: str,
    output_path: str,
    *,
    document_name: str = "SimpleCADModel",
    freecad_cmd: Optional[str] = None,
) -> str:
    """Export canonical model JSON to `.FCStd` via FreeCADCmd/FreeCAD."""

    return translate_model_json_to_fcstd(
        json_str,
        output_path,
        document_name=document_name,
        freecad_cmd=freecad_cmd,
    )
