"""DAG session recorder for building operation graphs.

Usage::

    from simplecadapi.graph import GraphSession, record_operation

    with GraphSession() as session:
        line_a = record_operation(
            "make_line_redge", {"start": (0, 0, 0), "end": (10, 0, 0)}
        )
        line_b = record_operation(
            "make_line_redge", {"start": (10, 0, 0), "end": (10, 5, 0)}
        )
        wire = record_operation(
            "make_wire_from_edges_rwire", {"edge_count": 2}, inputs=[line_a, line_b]
        )

    # Session graph is now available
    assert session.graph.node_count == 3
    json_str = session.graph.to_json()
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional, Set

from .expr import ExpressionGraph, canonicalize_params
from .frame import FrameGraph
from .topology import OperationGraph, OperationNode, TopoDelta
from .topology import SemanticDelta
from .topology import TopoKind, TopoRef, topo_ref_to_dict
from .core import Edge, Face, Solid, Vertex, Wire, get_current_cs


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

_active_session: Optional[GraphSession] = None
_recording_suspend_depth: int = 0


class GraphSession:
    """Context manager that records CAD operations into a DAG.

    Usage::

        with GraphSession() as session:
            n1 = record_operation(
                "make_line_redge", {"start": (0, 0, 0), "end": (1, 0, 0)}
            )
            n2 = record_operation(
                "make_line_redge", {"start": (1, 0, 0), "end": (1, 1, 0)}
            )
            record_operation(
                "make_wire_from_edges_rwire", {"edge_count": 2}, inputs=[n1, n2]
            )

        # Access the graph after the session
        print(session.graph.topological_order())
    """

    def __init__(self, graph_id: Optional[str] = None) -> None:
        self.graph = OperationGraph(graph_id=graph_id)
        self.expression_graph = ExpressionGraph()
        self.frame_graph = FrameGraph()

    def start(self) -> None:
        global _active_session
        _active_session = self

    def stop(self) -> None:
        global _active_session
        if _active_session is self:
            _active_session = None

    def __enter__(self) -> "GraphSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


def get_active_session() -> Optional[GraphSession]:
    """Return the currently active GraphSession, or None."""
    return _active_session


@contextmanager
def suspend_graph_recording():
    """Temporarily suspend automatic graph recording for internal API composition."""

    global _recording_suspend_depth
    _recording_suspend_depth += 1
    try:
        yield
    finally:
        _recording_suspend_depth -= 1


def _normalize_output_shapes(outputs: Any) -> List[Any]:
    if outputs is None:
        return []
    if isinstance(outputs, (list, tuple)):
        return list(outputs)
    return [outputs]


def _extract_input_nodes(inputs: Optional[Iterable[Any]]) -> List[OperationNode]:
    if not inputs:
        return []

    nodes: List[OperationNode] = []
    seen: Set[str] = set()
    for obj in inputs:
        if obj is None:
            continue
        node = getattr(obj, "_get_runtime", lambda *_args, **_kwargs: None)(
            "graph.node"
        )
        if node is None:
            continue
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        nodes.append(node)
    return nodes


def _current_context_snapshot() -> Dict[str, Any]:
    cs = get_current_cs()
    return {
        "origin": tuple(float(v) for v in cs.origin),
        "x_axis": tuple(float(v) for v in cs.x_axis),
        "y_axis": tuple(float(v) for v in cs.y_axis),
        "z_axis": tuple(float(v) for v in cs.z_axis),
    }


def _register_current_frame(session: GraphSession, node_id: str) -> None:
    cs = get_current_cs()
    session.frame_graph.ensure_frame(
        f"frame:{node_id}",
        origin=tuple(float(v) for v in cs.origin),
        x_axis=tuple(float(v) for v in cs.x_axis),
        y_axis=tuple(float(v) for v in cs.y_axis),
        z_axis=tuple(float(v) for v in cs.z_axis),
        metadata={"node_id": node_id},
    )


def _shape_kind(shape: Any) -> Optional[TopoKind]:
    if isinstance(shape, Vertex):
        return TopoKind.VERTEX
    if isinstance(shape, Edge):
        return TopoKind.EDGE
    if isinstance(shape, Wire):
        return TopoKind.WIRE
    if isinstance(shape, Face):
        return TopoKind.FACE
    if isinstance(shape, Solid):
        return TopoKind.SOLID
    return None


def _wrapped_shape(shape: Any) -> Any:
    if isinstance(shape, (Vertex, Edge, Wire, Face, Solid)):
        return shape.wrapped
    return None


def _shape_topo_id(shape: Any) -> str:
    topo_id = getattr(shape, "topo_id", None)
    if topo_id is not None:
        kind = _shape_kind(shape)
        prefix = kind.name.lower() if kind is not None else "shape"
        return f"{prefix}_{topo_id}"
    wrapped = _wrapped_shape(shape)
    if wrapped is None:
        return f"obj_{id(shape)}"
    kind = _shape_kind(shape)
    prefix = kind.name.lower() if kind is not None else "shape"
    try:
        return f"{prefix}_{wrapped.HashCode(1000000)}"
    except AttributeError:
        return f"{prefix}_{hash(wrapped)}"


def _attach_topo_refs_recursive(
    shape: Any,
    *,
    graph_id: str,
    node: OperationNode,
    output_slot: int,
) -> None:
    kind = _shape_kind(shape)
    if kind is None:
        return

    topo_ref = TopoRef(
        graph_id=graph_id,
        node_id=node.node_id,
        output_slot=output_slot,
        kind=kind,
        topo_id=_shape_topo_id(shape),
    )

    setter = getattr(shape, "_set_runtime", None)
    if callable(setter):
        setter("topo.ref", topo_ref)
        setter("topo.kind", kind.name)
        setter("topo.id", topo_ref.topo_id)

    set_metadata = getattr(shape, "set_metadata", None)
    if callable(set_metadata):
        set_metadata("topo_ref", topo_ref_to_dict(topo_ref))

    children = getattr(shape, "get_children", None)
    if callable(children):
        for child in children():
            _attach_topo_refs_recursive(
                child,
                graph_id=graph_id,
                node=node,
                output_slot=output_slot,
            )


def attach_graph_node(
    output: Any,
    node: OperationNode,
    output_slot: int = 0,
    graph_id: Optional[str] = None,
) -> Any:
    """Attach graph-node lineage to a shape-like object.

    The attachment is intentionally stored in runtime state plus lightweight
    metadata so later operations can discover upstream node identity without
    changing the public API.
    """

    if output is None:
        return output

    setter = getattr(output, "_set_runtime", None)
    if callable(setter):
        setter("graph.node", node)
        setter("graph.node_id", node.node_id)
        setter("graph.output_slot", output_slot)

    set_metadata = getattr(output, "set_metadata", None)
    effective_graph_id = graph_id
    if effective_graph_id is None:
        active = get_active_session()
        effective_graph_id = active.graph.graph_id if active is not None else ""

    if callable(set_metadata):
        set_metadata(
            "graph",
            {
                "graph_id": effective_graph_id or None,
                "node_id": node.node_id,
                "op": node.op,
                "output_slot": output_slot,
            },
        )

    if effective_graph_id:
        _attach_topo_refs_recursive(
            output,
            graph_id=effective_graph_id,
            node=node,
            output_slot=output_slot,
        )

    return output


def record_operation_if_active(
    op: str,
    params: Optional[Dict[str, Any]] = None,
    outputs: Any = None,
    input_shapes: Optional[Iterable[Any]] = None,
    semantic_delta: Optional[SemanticDelta] = None,
    topo_delta: Optional[TopoDelta] = None,
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[Set[str]] = None,
) -> Optional[OperationNode]:
    """Record an operation only when a session is active.

    This is the seamless bridge used by the original modeling APIs.
    Users keep calling `make_box_rsolid(...)` or `cut_rsolidlist(...)`; when a
    graph session exists, the operation is recorded automatically and its
    outputs are annotated with hidden lineage state.
    """

    session = get_active_session()
    if session is None or _recording_suspend_depth > 0:
        return None

    numeric_params = dict(params) if params else {}
    param_exprs: Dict[str, Any] = {}
    if params:
        numeric_params, param_exprs = canonicalize_params(
            params, session.expression_graph
        )

    output_list = _normalize_output_shapes(outputs)
    input_nodes = _extract_input_nodes(input_shapes)
    node = session.graph.add_node(
        op=op,
        params=numeric_params,
        param_exprs=param_exprs or None,
        inputs=input_nodes or None,
        output_count=max(len(output_list), 1),
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
        context=context or _current_context_snapshot(),
        tags=tags,
    )

    _register_current_frame(session, node.node_id)

    for idx, output in enumerate(output_list):
        attach_graph_node(
            output, node, output_slot=idx, graph_id=session.graph.graph_id
        )

    return node


def record_operation(
    op: str,
    params: Optional[Dict[str, Any]] = None,
    inputs: Optional[List[OperationNode]] = None,
    node_id: Optional[str] = None,
    output_count: int = 1,
    semantic_delta: Optional[SemanticDelta] = None,
    topo_delta: Optional[TopoDelta] = None,
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[Set[str]] = None,
) -> OperationNode:
    """Record an operation to the active graph session.

    Args:
        op: Operation type (e.g. ``"make_box"``, ``"cut"``).
        params: Operation parameters (serialisable).
        inputs: Upstream nodes whose outputs feed into this node.
        node_id: Optional explicit node id.
        output_count: Number of output shapes.
        topo_delta: Optional topological change set from tracking.
        context: Optional work-plane / coordinate-system snapshot.
        tags: Optional free-form labels.

    Returns:
        The created :class:`OperationNode`.

    Raises:
        RuntimeError: If no active session exists.
    """
    session = get_active_session()
    if session is None:
        raise RuntimeError(
            "No active GraphSession. Use `with GraphSession() as session:` "
            "or call `session.start()` before recording."
        )
    numeric_params = dict(params) if params else {}
    param_exprs: Dict[str, Any] = {}
    if params:
        numeric_params, param_exprs = canonicalize_params(
            params, session.expression_graph
        )

    node = session.graph.add_node(
        op=op,
        params=numeric_params,
        param_exprs=param_exprs or None,
        inputs=inputs,
        node_id=node_id,
        output_count=output_count,
        semantic_delta=semantic_delta,
        topo_delta=topo_delta,
        context=context,
        tags=tags,
    )
    _register_current_frame(session, node.node_id)
    return node
