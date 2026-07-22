"""Best-effort source callsites for recorded operation nodes."""

from __future__ import annotations

import ast
import dis
import hashlib
import inspect
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_CALL_OPS = {
    "CALL",
    "CALL_FUNCTION",
    "CALL_FUNCTION_EX",
    "CALL_FUNCTION_KW",
    "CALL_KW",
    "CALL_METHOD",
}
_SOURCE_MODULE = Path(__file__).resolve()
_PACKAGE_ROOT = _SOURCE_MODULE.parent


def capture_source_provenance() -> Optional[Dict[str, Any]]:
    """Capture provenance for the first non-SimpleCAD caller frame.

    Source discovery is intentionally failure-tolerant.  Interactive shells,
    generated code, frozen applications, and deleted source files can all
    produce a valid CAD graph without a source mapping.
    """

    frame = inspect.currentframe()
    try:
        frame = frame.f_back if frame is not None else None
        while frame is not None:
            filename = frame.f_code.co_filename
            if not _is_internal_filename(filename):
                return _capture_frame(frame)
            frame = frame.f_back
    finally:
        # Do not retain a reference cycle through frame locals.
        del frame
    return None


def canonical_source_payload(source: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the portable form stored in graph JSON.

    ``local_path`` is a runtime-only hint.  A source file outside the detected
    project cannot be assigned a truthful project-relative path, so its
    absolute path is also removed at the interchange boundary.
    """

    if source is None:
        return None
    payload = dict(source)
    payload.pop("local_path", None)
    if payload.get("path_kind") == "absolute":
        payload["path"] = None
        payload["path_kind"] = "unresolved"
    return payload


def _is_internal_filename(filename: str) -> bool:
    if not filename or filename.startswith("<"):
        return True
    try:
        path = Path(filename).resolve()
        path.relative_to(_PACKAGE_ROOT)
        return True
    except (OSError, ValueError):
        return False


def _capture_frame(frame: Any) -> Optional[Dict[str, Any]]:
    try:
        path = Path(frame.f_code.co_filename).resolve()
        source, _tree = _read_source(path)
    except (OSError, SyntaxError, UnicodeError):
        return None

    calls, parents = _indexed_calls(
        path,
        frame.f_code.co_name,
        int(getattr(frame.f_code, "co_firstlineno", frame.f_lineno)),
    )
    if not calls:
        return None

    selected = _select_call(calls, frame)
    if selected is None:
        return None
    call = selected

    path_value, path_kind = _portable_path(path)
    call_text = ast.get_source_segment(source, call) or ""
    start_line = int(getattr(call, "lineno", frame.f_lineno))
    end_line = int(getattr(call, "end_lineno", start_line))
    start_column = _character_column(source, start_line, int(call.col_offset))
    end_column = _character_column(
        source,
        end_line,
        int(getattr(call, "end_col_offset", call.col_offset)),
    )
    return {
        "schema_version": "1.0",
        "path": path_value,
        "path_kind": path_kind,
        "local_path": str(path),
        "line": start_line,
        "column": start_column,
        "end_line": end_line,
        "end_column": end_column,
        "call_text": call_text,
        "callsite_id": _callsite_id(
            path_value=path_value if path_kind == "project_relative" else None,
            start_line=start_line,
            start_column=start_column,
            end_line=end_line,
            end_column=end_column,
            call_text=call_text,
        ),
        "assignment_targets": _assignment_targets(call, source, parents),
    }


def _read_source(path: Path) -> Tuple[str, ast.AST]:
    stat = path.stat()
    return _read_source_version(
        path,
        int(stat.st_mtime_ns),
        int(stat.st_size),
        int(getattr(stat, "st_ino", 0)),
    )


@lru_cache(maxsize=128)
def _read_source_version(
    path: Path, _mtime_ns: int, _size: int, _inode: int
) -> Tuple[str, ast.AST]:
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path))


def _portable_path(path: Path) -> Tuple[Optional[str], str]:
    root = _project_root(path)
    if root is None:
        return str(path), "absolute"
    return path.relative_to(root).as_posix(), "project_relative"


def _project_root(path: Path) -> Optional[Path]:
    for parent in (path.parent, *path.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    return None


def _find_scope(
    tree: ast.AST, code_name: str, first_line: int
) -> Tuple[ast.AST, Optional[str]]:
    if code_name == "<module>":
        return tree, None

    candidates: List[ast.AST] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != code_name:
            continue
        decorator_lines = [
            int(decorator.lineno) for decorator in node.decorator_list
        ]
        start_line = min([int(node.lineno), *decorator_lines])
        end_line = int(getattr(node, "end_lineno", node.lineno))
        if start_line <= first_line <= end_line:
            candidates.append(node)
    if not candidates:
        return tree, code_name
    scope = min(
        candidates,
        key=lambda node: int(getattr(node, "end_lineno", node.lineno)) - node.lineno,
    )
    return scope, code_name


def _indexed_calls(
    path: Path, code_name: str, first_line: int
) -> Tuple[List[ast.Call], Dict[int, ast.AST]]:
    stat = path.stat()
    return _indexed_calls_version(
        path,
        code_name,
        first_line,
        int(stat.st_mtime_ns),
        int(stat.st_size),
        int(getattr(stat, "st_ino", 0)),
    )


@lru_cache(maxsize=256)
def _indexed_calls_version(
    path: Path,
    code_name: str,
    first_line: int,
    _mtime_ns: int,
    _size: int,
    _inode: int,
) -> Tuple[List[ast.Call], Dict[int, ast.AST]]:
    _source, tree = _read_source(path)
    scope, _function_name = _find_scope(tree, code_name, first_line)
    return _collect_calls(scope, root_is_module=scope is tree)


class _CallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: List[ast.Call] = []
        self.parents: Dict[int, ast.AST] = {}

    def visit(self, node: ast.AST) -> Any:
        for child in ast.iter_child_nodes(node):
            self.parents[id(child)] = node
        return super().visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        # Calls are appended after their children, matching Python's normal
        # evaluation order for nested calls and disassembled CALL opcodes.
        self.generic_visit(node)
        self.calls.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return None

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        return None


def _collect_calls(
    scope: ast.AST, *, root_is_module: bool
) -> Tuple[List[ast.Call], Dict[int, ast.AST]]:
    collector = _CallCollector()
    if root_is_module:
        for node in getattr(scope, "body", ()):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            collector.visit(node)
    else:
        for node in getattr(scope, "body", ()):
            collector.visit(node)
    # The visitor's post-order append is the execution order within a source
    # statement, while statement traversal already preserves file order.
    return collector.calls, collector.parents


def _select_call(
    calls: List[ast.Call], frame: Any
) -> Optional[ast.Call]:
    line = int(frame.f_lineno)
    line_calls = [call for call in calls if int(call.lineno) == line]
    if not line_calls:
        nearest_distance = min(abs(int(call.lineno) - line) for call in calls)
        line_calls = [
            call for call in calls if abs(int(call.lineno) - line) == nearest_distance
        ]
    if len(line_calls) == 1:
        return line_calls[0]

    ordinal = _call_ordinal(frame, line)
    if ordinal is None or ordinal < 1 or ordinal > len(line_calls):
        return None
    return line_calls[ordinal - 1]


def _call_ordinal(frame: Any, line: int) -> Optional[int]:
    current_offset = int(frame.f_lasti)
    call_offsets = _call_offsets_by_line(frame.f_code).get(line, ())
    if current_offset not in call_offsets:
        return None
    return call_offsets.index(current_offset) + 1


@lru_cache(maxsize=128)
def _call_offsets_by_line(code: Any) -> Dict[int, Tuple[int, ...]]:
    line_by_offset = dict(dis.findlinestarts(code))
    offsets_by_line: Dict[int, List[int]] = {}
    for instruction in dis.get_instructions(code):
        if instruction.opname not in _CALL_OPS:
            continue
        line = _instruction_line(instruction.offset, line_by_offset, 0)
        offsets_by_line.setdefault(line, []).append(instruction.offset)
    return {line: tuple(offsets) for line, offsets in offsets_by_line.items()}


def _instruction_line(offset: int, line_by_offset: Dict[int, int], fallback: int) -> int:
    starts = [start for start in line_by_offset if start <= offset]
    return line_by_offset[max(starts)] if starts else int(fallback)


def _assignment_targets(
    call: ast.Call, source: str, parents: Dict[int, ast.AST]
) -> List[str]:
    parent = parents.get(id(call))
    targets: List[ast.AST] = []
    if isinstance(parent, ast.Assign) and parent.value is call:
        targets = list(parent.targets)
    elif isinstance(parent, ast.AnnAssign) and parent.value is call:
        targets = [parent.target]
    elif isinstance(parent, ast.NamedExpr) and parent.value is call:
        targets = [parent.target]

    return [
        expression
        for target in targets
        for expression in _target_expressions(target, source)
        if expression
    ]


def _target_expressions(target: ast.AST, source: str) -> List[str]:
    if isinstance(target, (ast.Tuple, ast.List)):
        return [
            expression
            for item in target.elts
            for expression in _target_expressions(item, source)
        ]
    if isinstance(target, ast.Starred):
        return _target_expressions(target.value, source)
    expression = ast.get_source_segment(source, target)
    return [expression] if expression else []


def _character_column(source: str, line: int, byte_column: int) -> int:
    lines = source.splitlines()
    if line < 1 or line > len(lines):
        return byte_column
    prefix = lines[line - 1].encode("utf-8")[:byte_column]
    return len(prefix.decode("utf-8", errors="ignore"))


def _callsite_id(
    *,
    path_value: Optional[str],
    start_line: int,
    start_column: int,
    end_line: int,
    end_column: int,
    call_text: str,
) -> str:
    material = "\x1f".join(
        [
            path_value or "",
            str(start_line),
            str(start_column),
            str(end_line),
            str(end_column),
            call_text,
        ]
    )
    return "callsite_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
