"""Public SolidWorks product translator entrypoint."""

from __future__ import annotations

from ..package_units import ProductPackageInput
from .translator import SolidWorksTranslator


def translate_product_package_to_solidworks_script(
    data: ProductPackageInput,
    document_name: str = "SimpleCADProduct",
    *,
    output_path: str | None = None,
    visible: bool = False,
    source_kernel_fallback: bool = False,
) -> str:
    """Translate one validated `.scadpkg` closure into SolidWorks automation."""

    artifact = SolidWorksTranslator(
        document_name=document_name,
        output_path=output_path,
        visible=visible,
        source_kernel_fallback=source_kernel_fallback,
    ).translate_product_package(data)
    assert isinstance(artifact.content, str)
    return artifact.content


__all__ = ["translate_product_package_to_solidworks_script"]
