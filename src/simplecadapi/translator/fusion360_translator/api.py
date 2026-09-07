"""Public Fusion 360 product translator entrypoint."""

from __future__ import annotations

from ..package_units import ProductPackageInput
from .translator import Fusion360Translator


def translate_product_package_to_fusion360_script(
    data: ProductPackageInput,
    document_name: str = "SimpleCADProduct",
    *,
    selection_mode: str = "gsm",
    source_kernel_fallback: bool = False,
) -> str:
    """Translate one validated `.scadpkg` closure into a Fusion 360 script."""

    artifact = Fusion360Translator(
        document_name=document_name,
        selection_mode=selection_mode,
        source_kernel_fallback=source_kernel_fallback,
    ).translate_product_package(data)
    assert isinstance(artifact.content, str)
    return artifact.content


__all__ = ["translate_product_package_to_fusion360_script"]
