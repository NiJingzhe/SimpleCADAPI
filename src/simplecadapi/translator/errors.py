"""Shared translator backend exceptions."""

from __future__ import annotations

from typing import Any, Dict

from ..errors import ErrorGuidance, SimpleCADError


class TranslatorError(SimpleCADError):
    """Base structured error raised by translator backends."""

    code = "translator_error"

    def __init__(
        self,
        backend_id: str,
        operation: str,
        guidance: ErrorGuidance,
    ) -> None:
        self.backend_id = str(backend_id)
        super().__init__(operation, guidance)

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload["backend_id"] = self.backend_id
        payload["code"] = self.code
        return payload


class TranslationRequestError(TranslatorError):
    code = "invalid_translation_request"


class UnsupportedTargetError(TranslatorError):
    code = "unsupported_translation_target"


class BackendUnavailableError(TranslatorError):
    code = "translator_backend_unavailable"


class BackendExecutionError(TranslatorError):
    code = "translator_backend_execution_failed"


__all__ = [
    "BackendExecutionError",
    "BackendUnavailableError",
    "TranslationRequestError",
    "TranslatorError",
    "UnsupportedTargetError",
]
