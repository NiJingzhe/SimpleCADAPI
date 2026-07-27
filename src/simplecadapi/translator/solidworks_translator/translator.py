"""SolidWorks backend facade for canonical model translation."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Set

from ...errors import ErrorGuidance
from ...topology import OperationGraph
from ..base import BaseTranslator
from ..errors import TranslationRequestError
from ..types import BackendCapabilities, SupportLevel, TranslationArtifact
from .capabilities import CAPABILITIES
from .compiler import SolidWorksScriptTranslator


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


class SolidWorksTranslator(BaseTranslator):
    """Translate canonical model JSON into a SolidWorks COM Python script."""

    def __init__(
        self,
        document_name: str = "SimpleCADModel",
        *,
        output_path: Optional[str] = None,
        visible: bool = False,
        source_kernel_fallback: bool = False,
    ) -> None:
        self.document_name = str(document_name)
        self.output_path = str(output_path) if output_path is not None else None
        self.visible = bool(visible)
        self.source_kernel_fallback = bool(source_kernel_fallback)

    @property
    def capabilities(self) -> BackendCapabilities:
        return CAPABILITIES

    def _result_ids(
        self, payload: Dict[str, Any], graph: OperationGraph
    ) -> Sequence[str]:
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
                "solidworks",
                "translate_model_payload",
                ErrorGuidance(
                    what_happened=f"The result graph uses unsupported SolidWorks operations: {joined}.",
                    possible_causes=(
                        "The model uses canonical operations not implemented by the contributed runtime.",
                    ),
                    how_to_fix=(
                        "Lower the model to operations declared by solidworks_translator.CAPABILITIES.",
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
                "SolidWorks translation requires a non-empty canonical graph"
            )
        self._preflight(payload, source_graph)
        return SolidWorksScriptTranslator(
            document_name=self.document_name,
            visible=self.visible,
            source_kernel_fallback=self.source_kernel_fallback,
        ).translate_model_payload_to_script(
            payload,
            graph=source_graph,
            output_path=self.output_path,
        )

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
            backend_id="solidworks",
            target_id="solidworks_script",
            media_type="text/x-python",
            suggested_suffix=".py",
            content=self.translate_model_payload_to_script(payload, graph=graph),
            metadata={
                "document_name": self.document_name,
                "output_path": self.output_path,
                "visible": self.visible,
                "source_kernel_fallback": self.source_kernel_fallback,
                "target_runtime_validated": False,
            },
        )


__all__ = ["SolidWorksTranslator"]
