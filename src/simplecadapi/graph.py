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
from contextvars import ContextVar, Token
from typing import Any, Callable, Dict, Iterable, List, Optional, Set
import uuid

from .expr import ExpressionGraph, ScalarLike, ToleranceLike, canonicalize_params
from .units import UnitLike
from .frame import FrameGraph
from .tolerance import (
    ToleranceGraph,
    ToleranceMethod,
    ToleranceReport,
    ToleranceRequirement,
)
from .topology import (
    OperationGraph,
    OperationNode,
    TopoDelta,
    TopoEntry,
    TopoEvent,
    TopoRoleEntry,
)
from .topology import SemanticDelta
from .topology import TopoKind, TopoRef, topo_ref_to_dict
from .core import Compound, Edge, Face, Solid, Vertex, Wire, get_current_cs


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

_active_session_var: ContextVar[Optional["GraphSession"]] = ContextVar(
    "simplecadapi_active_graph_session", default=None
)
_recording_suspend_depth_var: ContextVar[int] = ContextVar(
    "simplecadapi_recording_suspend_depth", default=0
)


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
        self.tolerance_graph = ToleranceGraph(self.expression_graph)
        self.frame_graph = FrameGraph()
        self._active_session_token: Optional[Token[Optional["GraphSession"]]] = None

    def start(self) -> None:
        if self._active_session_token is not None:
            raise RuntimeError("GraphSession is already active")
        self._active_session_token = _active_session_var.set(self)

    def stop(self) -> None:
        if self._active_session_token is not None:
            _active_session_var.reset(self._active_session_token)
            self._active_session_token = None

    def __enter__(self) -> "GraphSession":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def require_tolerance(
        self,
        value: ScalarLike,
        tolerance: ToleranceLike,
        *,
        method: ToleranceMethod = "worst_case",
        name: str | None = None,
        requirement_id: str | None = None,
        tolerance_unit: UnitLike | None = None,
    ) -> ToleranceRequirement:
        """Declare a persisted Length or Angle manufacturing requirement.

        ``tolerance_unit`` defaults to the target's canonical unit for
        unit-aware expressions. The requirement is validated immediately and at
        session/model export, import, replay, and translation boundaries.
        """

        return self.tolerance_graph.require(
            value,
            tolerance,
            method=method,
            name=name,
            requirement_id=requirement_id,
            tolerance_unit=tolerance_unit,
        )

    def validate_tolerances(
        self, *, raise_on_failure: bool = False
    ) -> ToleranceReport:
        """Validate every declared dimension-chain requirement."""

        return self.tolerance_graph.validate(raise_on_failure=raise_on_failure)


def get_active_session() -> Optional[GraphSession]:
    """Return the currently active GraphSession, or None."""
    return _active_session_var.get()


@contextmanager
def suspend_graph_recording():
    """Temporarily suspend automatic graph recording for internal API composition."""

    token = _recording_suspend_depth_var.set(_recording_suspend_depth_var.get() + 1)
    try:
        yield
    finally:
        _recording_suspend_depth_var.reset(token)


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
    if isinstance(shape, Compound):
        return TopoKind.COMPOUND
    return None


def _wrapped_shape(shape: Any) -> Any:
    if isinstance(shape, (Vertex, Edge, Wire, Face, Solid, Compound)):
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


def _kernel_topo_id(shape: Any) -> str:
    wrapped = _wrapped_shape(shape)
    if wrapped is None:
        return f"obj_{id(shape)}"
    try:
        return str(wrapped.HashCode(1000000))
    except AttributeError:
        return str(hash(wrapped))


def _topology_wrappers(shape: Any) -> List[Any]:
    result: List[Any] = []
    seen_wrappers: Set[int] = set()
    queue = [shape]
    while queue:
        current = queue.pop(0)
        marker = id(current)
        if marker in seen_wrappers:
            continue
        seen_wrappers.add(marker)
        if _shape_kind(current) is not None:
            result.append(current)
        children = getattr(current, "get_children", None)
        if callable(children):
            queue.extend(children())
    return result


def _unique_ref_index(
    shapes: Iterable[Any],
    *,
    ref_factory: Optional[Callable[[Any], TopoRef]] = None,
) -> Dict[tuple[TopoKind, str], TopoRef]:
    candidates: Dict[tuple[TopoKind, str], List[TopoRef]] = {}
    for shape in shapes:
        for wrapper in _topology_wrappers(shape):
            kind = _shape_kind(wrapper)
            if kind is None:
                continue
            if ref_factory is None:
                ref = getattr(wrapper, "_get_runtime", lambda *_args: None)("topo.ref")
                if not isinstance(ref, TopoRef):
                    continue
            else:
                ref = ref_factory(wrapper)
            key = (kind, _kernel_topo_id(wrapper))
            candidates.setdefault(key, []).append(ref)

    result: Dict[tuple[TopoKind, str], TopoRef] = {}
    for key, refs in candidates.items():
        unique = set(refs)
        if len(unique) > 1:
            raise ValueError(
                f"ambiguous topology identity for {key[0].name}:{key[1]}"
            )
        result[key] = next(iter(unique))
    return result


def _canonicalize_recorded_topo_delta(
    delta: Optional[TopoDelta],
    *,
    graph_id: str,
    node_id: str,
    outputs: List[Any],
    inputs: Optional[Iterable[Any]],
) -> Optional[TopoDelta]:
    if delta is None:
        return None

    def output_ref_factory(slot: int):
        return lambda wrapper: TopoRef(
            graph_id=graph_id,
            node_id=node_id,
            output_slot=slot,
            kind=_shape_kind(wrapper),
            topo_id=_shape_topo_id(wrapper),
        )

    output_index: Dict[tuple[TopoKind, str], TopoRef] = {}
    for slot, output in enumerate(outputs):
        slot_index = _unique_ref_index(
            [output], ref_factory=output_ref_factory(slot)
        )
        for key, ref in slot_index.items():
            existing = output_index.get(key)
            if existing is not None and existing != ref:
                raise ValueError(
                    f"topology entity {key[0].name}:{key[1]} appears in multiple output slots"
                )
            output_index[key] = ref
    source_index = _unique_ref_index(inputs or ())

    def resolve(ref: TopoRef, *, source: bool, required: bool = True) -> TopoRef:
        index = source_index if source else output_index
        resolved = index.get((ref.kind, ref.topo_id))
        if resolved is None:
            if ref.graph_id not in {"", "pending"} and ref.node_id not in {"", "pending"}:
                return ref
            if required:
                side = "source" if source else "result"
                raise ValueError(
                    f"complete topology witness cannot resolve {side} {ref.kind.name}:{ref.topo_id}"
                )
            return ref
        return resolved

    entries = []
    for entry in delta.entries:
        complete = (
            str(entry.metadata.get("coverage", "complete")) == "complete"
            and str(entry.metadata.get("status", "proven")) == "proven"
        )
        entries.append(
            TopoEntry(
                ref=resolve(
                    entry.ref,
                    source=entry.event == TopoEvent.DELETED,
                    required=complete,
                ),
                event=entry.event,
                origin_role=entry.origin_role,
                parent_refs=tuple(
                    resolve(ref, source=True, required=complete)
                    for ref in entry.parent_refs
                ),
                metadata=dict(entry.metadata),
            )
        )

    roles = []
    for role in delta.roles:
        complete = (
            str(role.metadata.get("coverage", "complete")) == "complete"
            and str(role.metadata.get("status", "proven")) == "proven"
        )
        roles.append(
            TopoRoleEntry(
                ref=resolve(role.ref, source=False, required=complete),
                role=role.role,
                origin_role=role.origin_role,
                parent_refs=tuple(
                    resolve(ref, source=True, required=complete)
                    for ref in role.parent_refs
                ),
                metadata=dict(role.metadata),
            )
        )

    return TopoDelta(
        preserved=tuple(resolve(ref, source=False) for ref in delta.preserved),
        modified=tuple(resolve(ref, source=False) for ref in delta.modified),
        generated=tuple(resolve(ref, source=False) for ref in delta.generated),
        deleted=tuple(resolve(ref, source=True) for ref in delta.deleted),
        section_edges=tuple(resolve(ref, source=False) for ref in delta.section_edges),
        entries=tuple(entries),
        roles=tuple(roles),
        raw_event=dict(delta.raw_event),
    )


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


def attach_semantic_graph_node(
    output: Any,
    node: OperationNode,
    output_slot: int = 0,
    graph_id: Optional[str] = None,
) -> Any:
    """Attach semantic graph lineage without replacing geometry topology refs."""

    if output is None:
        return output

    setter = getattr(output, "_set_runtime", None)
    if callable(setter):
        setter("graph.node", node)
        setter("graph.node_id", node.node_id)
        setter("graph.output_slot", output_slot)

    effective_graph_id = graph_id
    if effective_graph_id is None:
        active = get_active_session()
        effective_graph_id = active.graph.graph_id if active is not None else ""

    set_metadata = getattr(output, "set_metadata", None)
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
    Users keep calling `make_box_rsolid(...)` or `cut_rsolid(...)`; when a
    graph session exists, the operation is recorded automatically and its
    outputs are annotated with hidden lineage state.
    """

    session = get_active_session()
    if session is None or _recording_suspend_depth_var.get() > 0:
        return None

    numeric_params = dict(params) if params else {}
    param_exprs: Dict[str, Any] = {}
    if params:
        numeric_params, param_exprs = canonicalize_params(
            params, session.expression_graph
        )

    output_list = _normalize_output_shapes(outputs)
    input_list = list(input_shapes or ())
    input_nodes = _extract_input_nodes(input_list)
    node_id = f"node_{uuid.uuid4().hex[:8]}"
    canonical_topo_delta = _canonicalize_recorded_topo_delta(
        topo_delta,
        graph_id=session.graph.graph_id,
        node_id=node_id,
        outputs=output_list,
        inputs=input_list,
    )
    node = session.graph.add_node(
        op=op,
        params=numeric_params,
        param_exprs=param_exprs or None,
        inputs=input_nodes or None,
        node_id=node_id,
        output_count=max(len(output_list), 1),
        semantic_delta=semantic_delta,
        topo_delta=canonical_topo_delta,
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
