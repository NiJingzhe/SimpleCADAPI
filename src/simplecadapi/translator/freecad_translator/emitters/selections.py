"""FreeCAD operation emitters for one canonical graph domain."""

from __future__ import annotations

from typing import List, Optional

from ....topology import OperationNode
from ..codegen import *


class SelectionEmitterMixin:
    def _emit_selections(
        self,
        node: OperationNode,
        *,
        var_name: str,
        object_name: str,
        tags_literal: str,
        context_literal: str,
        param_exprs_literal: str,
        semantic_delta_literal: str,
        topo_delta_literal: str,
    ) -> Optional[List[str]]:
        graph = self._source_graph
        if graph is None:
            return None

        rp = f"{var_name}_params"
        re = f"{var_name}_param_exprs"
        inputs = [inp.node_id for inp in node.inputs]

        def finish() -> List[str]:
            return [
                f"_attach_simplecad_metadata({var_name}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})",
                f"GRAPH_NODES[{_json_ascii(node.node_id)}] = {var_name}",
                f"GRAPH_METADATA[{_json_ascii(node.node_id)}] = {{'op': {_json_ascii(node.op)}, 'params': {rp}, 'inputs': {var_name}_inputs, 'context': {context_literal}, 'tags': {tags_literal}}}",
                f"GRAPH_OUTPUTS[{_json_ascii(node.node_id)}] = [{var_name}]",
            ]

        def finish_ir() -> List[str]:
            return [
                f"{var_name} = _register_ir_node({_json_ascii(object_name)}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]

        def finish_alias(source_node_id: str) -> List[str]:
            return [
                f"{var_name} = _register_graph_alias(node_id={_json_ascii(node.node_id)}, source_node_id={_json_ascii(source_node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]

        if node.op in {
            "make_select_rvertex",
            "make_select_redge",
            "make_select_rwire",
            "make_select_rface",
            "make_select_rsolid",
        } and len(inputs) == 1:
            return [
                f"{var_name} = _register_geo_selection_node(node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
        if node.op == "apply_tag_rselection" and len(inputs) == 1:
            return [
                f"{var_name} = _register_tag_selection_node({_json_ascii(object_name)}, node_id={_json_ascii(node.node_id)}, op={_json_ascii(node.op)}, params={rp}, inputs={var_name}_inputs, tags={tags_literal}, context={context_literal}, output_count={node.output_count}, param_exprs={param_exprs_literal}, semantic_delta={semantic_delta_literal}, topo_delta={topo_delta_literal})"
            ]
        return None


__all__ = ["SelectionEmitterMixin"]
