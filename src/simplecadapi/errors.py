"""Shared error types and formatting for LLM-facing SDK feedback."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import inspect
from typing import Any, Iterable, Optional, Sequence, Tuple, NoReturn


_TECHNICAL_DETAIL_TRANSLATIONS = {
    "宽度、高度和深度必须大于0": "width, height, and depth must be greater than zero.",
    "如果传入线框作为拉伸对象，那么线框必须是闭合的, 而你的线框没有闭合，请检查构成线框的点是否正确": (
        "wire profiles must be closed before extrusion; check the points that form the wire."
    ),
}


def _contains_cjk(value: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff" for char in value)


def _normalize_lines(values: Iterable[str]) -> Tuple[str, ...]:
    return tuple(str(value).strip() for value in values if str(value).strip())


def _technical_details_from_error(error: BaseException) -> str:
    message = str(error).strip()
    if message:
        for source, target in _TECHNICAL_DETAIL_TRANSLATIONS.items():
            message = message.replace(source, target)
        if _contains_cjk(message):
            message = "The underlying validation failed; use the structured guidance above to repair the operation."
        return f"{type(error).__name__}: {message}"
    return type(error).__name__


@dataclass(frozen=True)
class ErrorGuidance:
    what_happened: str
    possible_causes: Tuple[str, ...]
    how_to_fix: Tuple[str, ...]
    technical_details: Optional[str] = None
    signature: Optional[str] = None
    documentation_hint: Optional[str] = None


def _resolve_operation_callable(operation: str) -> Any:
    op = str(operation).strip()
    if not op:
        return None

    if "." in op:
        module_name, attr_path = op.rsplit(".", 1)
        try:
            obj = importlib.import_module(module_name)
        except Exception:
            obj = None
        if obj is not None:
            for part in attr_path.split("."):
                if not hasattr(obj, part):
                    obj = None
                    break
                obj = getattr(obj, part)
            if obj is not None:
                return obj

        try:
            scad = importlib.import_module("simplecadapi")
        except Exception:
            return None
        obj = scad
        for part in op.split("."):
            if not hasattr(obj, part):
                return None
            obj = getattr(obj, part)
        return obj

    try:
        scad = importlib.import_module("simplecadapi")
    except Exception:
        return None
    return getattr(scad, op, None)


def _operation_signature(operation: str) -> Optional[str]:
    obj = _resolve_operation_callable(operation)
    if obj is None:
        return None
    try:
        return f"{operation}{inspect.signature(obj)}"
    except (TypeError, ValueError):
        return None


def _documentation_hint(operation: str) -> str:
    op = str(operation).strip()
    if not op:
        return "For full usage details, run help(...) on the failing operation."
    if "." in op:
        return f"For full usage details, run help({op})."
    return f"For full usage details, run help(simplecadapi.{op})."


def format_llm_error(operation: str, guidance: ErrorGuidance) -> str:
    lines = [f"Operation: {operation}"]
    if guidance.signature:
        lines.append(f"Signature: {guidance.signature}")
    if guidance.documentation_hint:
        lines.append(f"Documentation: {guidance.documentation_hint}")
    lines.append(f"What happened: {guidance.what_happened}")
    lines.append("Possible causes:")
    lines.extend(f"- {item}" for item in guidance.possible_causes)
    lines.append("How to fix:")
    lines.extend(f"- {item}" for item in guidance.how_to_fix)
    if guidance.technical_details:
        lines.append(f"Technical details: {guidance.technical_details}")
    return "\n".join(lines)


class SimpleCADError(ValueError):
    """Structured ValueError variant for LLM-oriented repair guidance."""

    def __init__(self, operation: str, guidance: ErrorGuidance):
        self.operation = str(operation)
        self.guidance = guidance
        super().__init__(format_llm_error(self.operation, self.guidance))

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "what_happened": self.guidance.what_happened,
            "possible_causes": list(self.guidance.possible_causes),
            "how_to_fix": list(self.guidance.how_to_fix),
            "technical_details": self.guidance.technical_details,
            "signature": self.guidance.signature,
            "documentation_hint": self.guidance.documentation_hint,
        }


def raise_harness_error(
    *,
    operation: str,
    what_happened: str,
    possible_causes: Sequence[str],
    how_to_fix: Sequence[str],
    technical_details: Optional[str] = None,
    error: Optional[BaseException] = None,
) -> NoReturn:
    if isinstance(error, SimpleCADError):
        raise error

    resolved_details = technical_details
    if resolved_details is None and error is not None:
        resolved_details = _technical_details_from_error(error)

    guidance = ErrorGuidance(
        what_happened=str(what_happened).strip(),
        possible_causes=_normalize_lines(possible_causes),
        how_to_fix=_normalize_lines(how_to_fix),
        technical_details=(
            str(resolved_details).strip()
            if resolved_details is not None and str(resolved_details).strip()
            else None
        ),
        signature=_operation_signature(str(operation)),
        documentation_hint=_documentation_hint(str(operation)),
    )
    raise SimpleCADError(str(operation), guidance) from error
