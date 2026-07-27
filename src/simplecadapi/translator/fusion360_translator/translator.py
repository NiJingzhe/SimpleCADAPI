"""Fusion 360 backend facade for canonical model translation."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Set

from ...errors import ErrorGuidance
from ...topology import OperationGraph
from ..base import BaseTranslator
from ..errors import TranslationRequestError
from ..types import BackendCapabilities, SupportLevel, TranslationArtifact
from .capabilities import CAPABILITIES
from .compiler import Fusion360ScriptTranslator


def _dependency_node_ids(
    graph: OperationGraph, result_node_ids: Sequence[str]
) -> Set[str]:
    needed: Set[str] = set()
    pending = [str(node_id) for node_id in result_node_ids]
    while pending:
        node_id = pending.pop()
        if node_id in needed:
            continue
        node = graph.get_node(node_id)
        if node is None:
            raise ValueError(f"Result node {node_id!r} is not present in the graph")
        needed.add(node_id)
        pending.extend(input_ref.node_id for input_ref in node.inputs)
        for key in ("selected_edge_node_ids", "selected_face_node_ids"):
            pending.extend(str(value) for value in node.params.get(key, []) or [])
    return needed


class Fusion360Translator(BaseTranslator):
    """Translate canonical model JSON into a Fusion 360 Python script."""

    def __init__(
        self,
        document_name: str = "SimpleCADModel",
        result_node_ids: Optional[Sequence[str]] = None,
        *,
        selection_mode: str = "gsm",
        source_kernel_fallback: bool = False,
    ) -> None:
        self.document_name = str(document_name)
        self.result_node_ids = (
            tuple(str(node_id) for node_id in result_node_ids)
            if result_node_ids is not None
            else None
        )
        self.selection_mode = str(selection_mode)
        self.source_kernel_fallback = bool(source_kernel_fallback)

    @property
    def capabilities(self) -> BackendCapabilities:
        return CAPABILITIES

    def _result_ids(
        self, payload: Dict[str, Any], graph: OperationGraph
    ) -> Sequence[str]:
        if self.result_node_ids is not None:
            return self.result_node_ids
        leaf_ids = payload.get("leaf_ids")
        if isinstance(leaf_ids, list) and leaf_ids:
            return [str(node_id) for node_id in leaf_ids]
        return [node.node_id for node in graph.leaf_nodes()]

    def _preflight(self, payload: Dict[str, Any], graph: OperationGraph) -> None:
        needed = _dependency_node_ids(graph, self._result_ids(payload, graph))
        unsupported = sorted(
            {
                node.op
                for node_id in needed
                for node in [graph.get_node(node_id)]
                if node is not None
                and (
                    node.op not in CAPABILITIES.operations
                    or CAPABILITIES.operations[node.op].level
                    is SupportLevel.UNSUPPORTED
                )
            }
        )
        if unsupported:
            joined = ", ".join(unsupported)
            raise TranslationRequestError(
                "fusion360",
                "translate_model_payload",
                ErrorGuidance(
                    what_happened=f"The result graph uses unsupported Fusion 360 operations: {joined}.",
                    possible_causes=(
                        "The model uses canonical operations not implemented by the contributed runtime.",
                    ),
                    how_to_fix=(
                        "Lower the model to operations declared by fusion360_translator.CAPABILITIES.",
                        "Use another translator backend for this model.",
                    ),
                ),
            )

    def translate_model_payload_to_script(
        self,
        payload: Dict[str, Any],
        *,
        graph: Optional[OperationGraph] = None,
    ) -> str:
        source_graph = graph or payload.get("graph")
        if not isinstance(source_graph, OperationGraph) or source_graph.node_count == 0:
            raise ValueError(
                "Fusion 360 translation requires a non-empty canonical graph"
            )
        self._preflight(payload, source_graph)
        return Fusion360ScriptTranslator(
            document_name=self.document_name,
            result_node_ids=self.result_node_ids,
            selection_mode=self.selection_mode,
            source_kernel_fallback=self.source_kernel_fallback,
        ).translate_model_payload_to_script(payload, graph=source_graph)

    def translate_model_json_to_script(self, json_str: str) -> str:
        artifact = self.translate_model_json(json_str)
        assert isinstance(artifact.content, str)
        return artifact.content

    def translate_model_payload(
        self,
        payload: Dict[str, Any],
        *,
        graph: Optional[OperationGraph] = None,
    ) -> TranslationArtifact:
        return TranslationArtifact(
            backend_id="fusion360",
            target_id="fusion360_script",
            media_type="text/x-python",
            suggested_suffix=".py",
            content=self.translate_model_payload_to_script(payload, graph=graph),
            metadata={
                "document_name": self.document_name,
                "result_node_ids": self.result_node_ids,
                "selection_mode": self.selection_mode,
                "source_kernel_fallback": self.source_kernel_fallback,
                "target_runtime_validated": False,
            },
        )


__all__ = ["Fusion360Translator"]
