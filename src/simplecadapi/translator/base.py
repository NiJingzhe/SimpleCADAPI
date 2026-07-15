"""Base contract for canonical model translators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..serializer import import_model_json
from ..topology import OperationGraph
from .types import BackendCapabilities, TranslationArtifact


class BaseTranslator(ABC):
    """Translate canonical model JSON into an in-memory backend artifact."""

    @property
    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Return the backend's static capability declaration."""

    def translate_model_json(self, json_str: str) -> TranslationArtifact:
        """Parse canonical model JSON and translate its payload."""

        payload = import_model_json(json_str)
        graph = payload.get("graph")
        if not isinstance(graph, OperationGraph):
            raise ValueError(
                "Translation requires model JSON with a canonical low-level graph"
            )
        if graph.node_count == 0:
            raise ValueError(
                "Translation requires model JSON with a non-empty canonical low-level graph"
            )
        return self.translate_model_payload(payload, graph=graph)

    @abstractmethod
    def translate_model_payload(
        self,
        payload: Dict[str, Any],
        *,
        graph: Optional[OperationGraph] = None,
    ) -> TranslationArtifact:
        """Translate an already-imported canonical model payload."""


__all__ = ["BaseTranslator"]
