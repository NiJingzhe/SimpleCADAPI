"""Compatibility import for the modular SolidWorks script compiler."""

from __future__ import annotations

from typing import Optional

from .translator import _SolidWorksCompiler


class SolidWorksScriptTranslator(_SolidWorksCompiler):
    """Backward-compatible class name for the SolidWorks script compiler."""

    def __init__(
        self,
        document_name: str = "SimpleCADModel",
        *,
        visible: bool = False,
        source_kernel_fallback: bool = False,  # ignored: native-only rebuild
        solidworks_version: str = "2025",
    ) -> None:
        if source_kernel_fallback:
            raise ValueError(
                "source_kernel_fallback is no longer supported; the SolidWorks "
                "translator always rebuilds natively"
            )
        super().__init__(
            document_name,
            visible=visible,
            solidworks_version=solidworks_version,
        )


__all__ = ["SolidWorksScriptTranslator"]
