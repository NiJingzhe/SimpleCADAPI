"""Public Fusion 360 translator entrypoints."""

from __future__ import annotations

from typing import Optional, Sequence

from .translator import Fusion360Translator


def translate_model_json_to_fusion360_script(
    json_str: str,
    document_name: str = "SimpleCADModel",
    result_node_ids: Optional[Sequence[str]] = None,
    *,
    selection_mode: str = "gsm",
    source_kernel_fallback: bool = False,
) -> str:
    """Translate canonical model JSON into a Fusion 360 Python script."""

    return Fusion360Translator(
        document_name=document_name,
        result_node_ids=result_node_ids,
        selection_mode=selection_mode,
        source_kernel_fallback=source_kernel_fallback,
    ).translate_model_json_to_script(json_str)


__all__ = ["translate_model_json_to_fusion360_script"]
