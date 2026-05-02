"""Minimal expression graph support for SimpleCADAPI 2.0.

The goal of this module is to provide a low-intrusion parametric layer:

- users explicitly create variables with ``var(name, default)``
- plain numeric literals are automatically lifted to constants when needed
- arithmetic on variables/expressions builds a small expression DAG
- public modeling APIs can keep their existing pure-function signatures while
  accepting expression values transparently
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Mapping, Tuple, Union, cast
import uuid


def _make_expr_id(prefix: str = "expr") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class ScalarExprBase:
    """Base class for scalar expression nodes."""

    expr_id: str

    def evaluate(self, bindings: Mapping[str, float] | None = None) -> float:
        raise NotImplementedError

    def __float__(self) -> float:
        return float(self.evaluate())

    def __bool__(self) -> bool:
        raise TypeError(
            "Expression objects do not define truthiness. Evaluate them explicitly first."
        )

    def _binary_expr(self, op: str, other: ScalarLike) -> Expr:
        return Expr(op=op, args=(lift_scalar(self), lift_scalar(other)))

    def _rbinary_expr(self, op: str, other: ScalarLike) -> Expr:
        return Expr(op=op, args=(lift_scalar(other), lift_scalar(self)))

    def __add__(self, other: ScalarLike) -> Expr:
        return self._binary_expr("add", other)

    def __radd__(self, other: ScalarLike) -> Expr:
        return self._rbinary_expr("add", other)

    def __sub__(self, other: ScalarLike) -> Expr:
        return self._binary_expr("sub", other)

    def __rsub__(self, other: ScalarLike) -> Expr:
        return self._rbinary_expr("sub", other)

    def __mul__(self, other: ScalarLike) -> Expr:
        return self._binary_expr("mul", other)

    def __rmul__(self, other: ScalarLike) -> Expr:
        return self._rbinary_expr("mul", other)

    def __truediv__(self, other: ScalarLike) -> Expr:
        return self._binary_expr("div", other)

    def __rtruediv__(self, other: ScalarLike) -> Expr:
        return self._rbinary_expr("div", other)

    def __pow__(self, other: ScalarLike) -> Expr:
        return self._binary_expr("pow", other)

    def __rpow__(self, other: ScalarLike) -> Expr:
        return self._rbinary_expr("pow", other)

    def __neg__(self) -> Expr:
        return Expr(op="neg", args=(lift_scalar(self),))

    def __abs__(self) -> Expr:
        return Expr(op="abs", args=(lift_scalar(self),))


@dataclass(frozen=True)
class Const(ScalarExprBase):
    """Immutable constant node used in the v2 expression graph."""

    value: float
    expr_id: str = field(default_factory=lambda: _make_expr_id("const"))

    def evaluate(self, bindings: Mapping[str, float] | None = None) -> float:
        return float(self.value)


@dataclass(frozen=True)
class Var(ScalarExprBase):
    """Named scalar parameter with a default fallback value."""

    name: str
    default: float
    comment: str | None = None
    expr_id: str = field(default_factory=lambda: _make_expr_id("var"))

    def evaluate(self, bindings: Mapping[str, float] | None = None) -> float:
        if bindings is not None and self.name in bindings:
            return float(bindings[self.name])
        return float(self.default)


@dataclass(frozen=True)
class Expr(ScalarExprBase):
    """Derived scalar expression node built from one or more operands."""

    op: str
    args: Tuple[ScalarExpr, ...]
    expr_id: str = field(default_factory=lambda: _make_expr_id("expr"))

    def evaluate(self, bindings: Mapping[str, float] | None = None) -> float:
        values = [arg.evaluate(bindings) for arg in self.args]
        if self.op == "add":
            return values[0] + values[1]
        if self.op == "sub":
            return values[0] - values[1]
        if self.op == "mul":
            return values[0] * values[1]
        if self.op == "div":
            return values[0] / values[1]
        if self.op == "pow":
            return values[0] ** values[1]
        if self.op == "neg":
            return -values[0]
        if self.op == "abs":
            return abs(values[0])
        if self.op == "sin":
            return math.sin(values[0])
        if self.op == "cos":
            return math.cos(values[0])
        if self.op == "tan":
            return math.tan(values[0])
        if self.op == "sqrt":
            return math.sqrt(values[0])
        if self.op == "acos":
            return math.acos(values[0])
        if self.op == "asin":
            return math.asin(values[0])
        if self.op == "atan":
            return math.atan(values[0])
        if self.op == "atan2":
            return math.atan2(values[0], values[1])
        raise ValueError(f"Unsupported expression op '{self.op}'")


ScalarExpr = Union[Const, Var, Expr]
ScalarLike = Union[int, float, ScalarExpr]


def const(value: int | float) -> Const:
    """Create a constant scalar node for parameterized modeling."""

    return Const(float(value))


def var(name: str, default: int | float, comment: str | None = None) -> Var:
    """Create a named variable node for v2 expression-driven parameters."""

    if not isinstance(name, str) or not name:
        raise ValueError("Variable name must be a non-empty string")
    if comment is not None and not isinstance(comment, str):
        raise ValueError("Variable comment must be a string when provided")
    return Var(name=name, default=float(default), comment=comment)


def lift_scalar(value: ScalarLike) -> ScalarExpr:
    if isinstance(value, (Const, Var, Expr)):
        return value
    if isinstance(value, bool):
        raise TypeError("Boolean values are not valid scalar expression inputs")
    if isinstance(value, (int, float)):
        return Const(float(value))
    raise TypeError(f"Unsupported scalar expression value: {type(value)!r}")


def evaluate_scalar(
    value: ScalarLike, bindings: Mapping[str, float] | None = None
) -> float:
    return float(lift_scalar(value).evaluate(bindings))


def sin(value: ScalarLike) -> Expr:
    return Expr(op="sin", args=(lift_scalar(value),))


def cos(value: ScalarLike) -> Expr:
    return Expr(op="cos", args=(lift_scalar(value),))


def tan(value: ScalarLike) -> Expr:
    return Expr(op="tan", args=(lift_scalar(value),))


def sqrt(value: ScalarLike) -> Expr:
    return Expr(op="sqrt", args=(lift_scalar(value),))


def acos(value: ScalarLike) -> Expr:
    return Expr(op="acos", args=(lift_scalar(value),))


def asin(value: ScalarLike) -> Expr:
    return Expr(op="asin", args=(lift_scalar(value),))


def atan(value: ScalarLike) -> Expr:
    return Expr(op="atan", args=(lift_scalar(value),))


def atan2(y: ScalarLike, x: ScalarLike) -> Expr:
    return Expr(op="atan2", args=(lift_scalar(y), lift_scalar(x)))


def evaluate_value(value: Any, bindings: Mapping[str, float] | None = None) -> Any:
    if isinstance(value, tuple):
        return tuple(evaluate_value(item, bindings) for item in value)
    if isinstance(value, list):
        return [evaluate_value(item, bindings) for item in value]
    if isinstance(value, dict):
        return {key: evaluate_value(item, bindings) for key, item in value.items()}
    if isinstance(value, (Const, Var, Expr, int, float)) and not isinstance(
        value, bool
    ):
        return evaluate_scalar(value, bindings)
    return value


def _expr_to_node_payload(expr: ScalarExpr) -> Dict[str, Any]:
    if isinstance(expr, Const):
        return {
            "expr_id": expr.expr_id,
            "kind": "const",
            "value": float(expr.value),
        }
    if isinstance(expr, Var):
        payload = {
            "expr_id": expr.expr_id,
            "kind": "var",
            "name": expr.name,
            "default": float(expr.default),
        }
        if expr.comment:
            payload["comment"] = expr.comment
        return payload
    return {
        "expr_id": expr.expr_id,
        "kind": "expr",
        "op": expr.op,
        "args": [arg.expr_id for arg in expr.args],
    }


class ExpressionGraph:
    """A lightweight registry of expression DAG nodes."""

    def __init__(self) -> None:
        self._nodes: Dict[str, ScalarExpr] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def get(self, expr_id: str) -> ScalarExpr | None:
        return self._nodes.get(expr_id)

    def register(self, value: ScalarLike) -> ScalarExpr:
        expr = lift_scalar(value)
        self._register_recursive(expr)
        return expr

    def _register_recursive(self, expr: ScalarExpr) -> None:
        if expr.expr_id in self._nodes:
            return
        if isinstance(expr, Expr):
            for arg in expr.args:
                self._register_recursive(arg)
        self._nodes[expr.expr_id] = expr

    def _topological_expr_ids(self) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()

        def visit(expr: ScalarExpr) -> None:
            if expr.expr_id in seen:
                return
            if isinstance(expr, Expr):
                for arg in expr.args:
                    visit(arg)
            seen.add(expr.expr_id)
            ordered.append(expr.expr_id)

        for expr in list(self._nodes.values()):
            visit(expr)
        return ordered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [
                _expr_to_node_payload(self._nodes[expr_id])
                for expr_id in self._topological_expr_ids()
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpressionGraph":
        graph = cls()
        node_map: Dict[str, ScalarExpr] = {}
        for node in data.get("nodes", []):
            kind = node.get("kind")
            expr_id = str(node["expr_id"])
            if kind == "const":
                expr = Const(value=float(node["value"]), expr_id=expr_id)
            elif kind == "var":
                expr = Var(
                    name=str(node["name"]),
                    default=float(node["default"]),
                    comment=str(node["comment"]) if node.get("comment") else None,
                    expr_id=expr_id,
                )
            elif kind == "expr":
                args = tuple(node_map[arg_id] for arg_id in node.get("args", []))
                expr = Expr(op=str(node["op"]), args=args, expr_id=expr_id)
            else:
                raise ValueError(f"Unknown expression node kind: {kind!r}")
            graph._nodes[expr_id] = expr
            node_map[expr_id] = expr
        return graph


def _canonicalize_param_value(
    value: Any, expression_graph: ExpressionGraph
) -> Tuple[Any, Any | None]:
    if isinstance(value, tuple):
        numeric_items: List[Any] = []
        expr_items: List[Any] = []
        has_expr = False
        for item in value:
            numeric_item, expr_item = _canonicalize_param_value(item, expression_graph)
            numeric_items.append(numeric_item)
            expr_items.append(expr_item)
            has_expr = has_expr or expr_item is not None
        return tuple(numeric_items), expr_items if has_expr else None

    if isinstance(value, list):
        numeric_items = []
        expr_items = []
        has_expr = False
        for item in value:
            numeric_item, expr_item = _canonicalize_param_value(item, expression_graph)
            numeric_items.append(numeric_item)
            expr_items.append(expr_item)
            has_expr = has_expr or expr_item is not None
        return numeric_items, expr_items if has_expr else None

    if isinstance(value, dict):
        numeric_dict: Dict[str, Any] = {}
        expr_dict: Dict[str, Any] = {}
        for key, item in value.items():
            numeric_item, expr_item = _canonicalize_param_value(item, expression_graph)
            numeric_dict[str(key)] = numeric_item
            if expr_item is not None:
                expr_dict[str(key)] = expr_item
        return numeric_dict, expr_dict or None

    if isinstance(value, (Const, Var, Expr)):
        expr = expression_graph.register(cast(ScalarLike, value))
        return float(expr.evaluate()), {"expr_id": expr.expr_id}

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), None

    return value, None


def _is_discrete_param_name(key: str) -> bool:
    key_lower = key.lower()
    return key_lower.endswith("_indices") or key_lower in {
        "edge_count",
        "face_count",
        "removed_face_count",
        "profile_count",
        "count",
        "output_count",
    }


def canonicalize_params(
    params: Dict[str, Any] | None,
    expression_graph: ExpressionGraph,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not params:
        return {}, {}

    numeric_params: Dict[str, Any] = {}
    param_exprs: Dict[str, Any] = {}
    for key, value in params.items():
        if _is_discrete_param_name(key):
            numeric_params[key] = value
            continue
        numeric_value, expr_value = _canonicalize_param_value(value, expression_graph)
        numeric_params[key] = numeric_value
        if expr_value is not None:
            param_exprs[key] = expr_value
    return numeric_params, param_exprs
