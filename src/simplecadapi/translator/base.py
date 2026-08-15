"""Base contract for validated product-package translators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .package_units import ProductPackageInput
from .types import BackendCapabilities, TranslationArtifact


class BaseTranslator(ABC):
    """Translate one validated `.scadpkg` closure into a backend artifact."""

    @property
    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Return the backend's static capability declaration."""

    @abstractmethod
    def translate_product_package(
        self,
        data: ProductPackageInput,
        **options: Any,
    ) -> TranslationArtifact:
        """Translate one complete durable product-definition closure."""


__all__ = ["BaseTranslator"]
