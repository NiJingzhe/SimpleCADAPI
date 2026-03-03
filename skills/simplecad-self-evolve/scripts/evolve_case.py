#!/usr/bin/env python3
"""Extract and append a new case function into skill-local evolve module."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


CASES_MODULE = "simplecad_self_evolve_cases"
SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = SKILL_ROOT / "cases" / CASES_MODULE / "evolve.py"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _node_source(lines: list[str], node: ast.AST) -> str:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start)
    return "\n".join(lines[start - 1 : end])


def _extract_header_imports(tree: ast.Module, lines: list[str]) -> list[str]:
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(_node_source(lines, node).strip())
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            break
    return [item for item in imports if item]


def _find_import_insert_index(lines: list[str]) -> int:
    if len(lines) <= 1:
        return len(lines)

    index = 1
    while index < len(lines) and not lines[index].strip():
        index += 1

    if index >= len(lines):
        return 1

    triple_double = '"' * 3
    triple_single = "'" * 3

    stripped = lines[index].strip()
    if not (stripped.startswith(triple_double) or stripped.startswith(triple_single)):
        return 1

    quote = triple_double if stripped.startswith(triple_double) else triple_single
    if stripped.count(quote) >= 2 and len(stripped) > len(quote) * 2:
        return index + 1

    index += 1
    while index < len(lines):
        if quote in lines[index]:
            return index + 1
        index += 1

    return 1


def _combine_imports(imports: list[str], function_source: str) -> str:
    if not imports:
        return function_source

    lines = function_source.splitlines()
    if not lines:
        return function_source

    insert_at = _find_import_insert_index(lines)
    import_lines = [f"    {item}" for item in imports]
    merged = lines[:insert_at] + [""] + import_lines + [""] + lines[insert_at:]
    return "\n".join(merged)


def _ensure_target(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return

    path.write_text(
        "\n".join(
            [
                '"""Skill-local evolved case functions."""',
                "",
                "__all__: list[str] = []",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _select_function(tree: ast.Module, name: str | None) -> ast.FunctionDef:
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if not functions:
        raise ValueError("No top-level function found in source file")

    if name is None:
        return functions[0]

    for node in functions:
        if node.name == name:
            return node

    raise ValueError(f"Function '{name}' not found in source file")


def _append_case(target: Path, function_source: str, function_name: str, allow_duplicate: bool) -> None:
    content = _read_text(target)
    if not allow_duplicate and f"def {function_name}(" in content:
        raise ValueError(f"Function '{function_name}' already exists in {target}")

    with target.open("a", encoding="utf-8") as stream:
        stream.write("\n\n" + function_source.strip() + "\n")
        if f'__all__.append("{function_name}")' not in content:
            stream.write(f'\n__all__.append("{function_name}")\n')

    ast.parse(_read_text(target), filename=str(target))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add a new evolved case function into this skill package"
    )
    parser.add_argument("source_file", type=Path, help="Python file containing new function")
    parser.add_argument(
        "--function",
        default=None,
        help="Specific function name to extract (default: first top-level function)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help="Target evolve module path",
    )
    parser.add_argument(
        "--allow-duplicate",
        action="store_true",
        help="Allow appending function even if same name already exists",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.source_file.exists():
        raise SystemExit(f"Source file not found: {args.source_file}")

    source_text = _read_text(args.source_file)
    if not source_text.strip():
        raise SystemExit(f"Source file is empty: {args.source_file}")

    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        raise SystemExit(f"Cannot parse source file: {exc}") from exc

    function_node = _select_function(tree, args.function)
    lines = source_text.splitlines()
    function_source = _node_source(lines, function_node)
    imports = _extract_header_imports(tree, lines)
    merged_source = _combine_imports(imports, function_source)

    _ensure_target(args.target)
    try:
        _append_case(
            target=args.target,
            function_source=merged_source,
            function_name=function_node.name,
            allow_duplicate=args.allow_duplicate,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Added function '{function_node.name}' to {args.target}")
    print("Import with:")
    print(f"  from {CASES_MODULE}.evolve import {function_node.name}")


if __name__ == "__main__":
    main()
