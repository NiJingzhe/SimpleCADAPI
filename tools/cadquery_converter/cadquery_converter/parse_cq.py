"""Parse CadQuery Python source into feature IR."""

from __future__ import annotations

import ast
import re
from typing import List

from .ir import FeatureProgram, ParameterSpec
from .lower import CadQueryParseError, ChainLowerer, unwrap_chain


def _slug(name: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "part"


def _param_name(base: str, used: set[str]) -> str:
    candidate = _slug(base)
    index = 2
    while candidate in used:
        candidate = f"{_slug(base)}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _find_result_chain(tree: ast.Module):
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "result":
                return unwrap_chain(node.value)
    raise CadQueryParseError("expected assignment to result = (...)")


def _collect_numeric_literals(program: FeatureProgram) -> None:
    used: set[str] = set()
    values: List[float] = []
    for step in program.steps:
        for value in _walk_numbers(step.params):
            if value not in values:
                values.append(value)
    for index, value in enumerate(values[:32]):
        pname = _param_name(f"dim_{index + 1}", used)
        program.parameters.append(ParameterSpec(name=pname, default=value))


def _walk_numbers(value):
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_numbers(item)


def parse_cadquery_source(
    source: str,
    *,
    graph_id: str = "",
    stem: str = "",
    family: str = "",
) -> FeatureProgram:
    tree = ast.parse(source)
    chain, _root = _find_result_chain(tree)
    program = FeatureProgram(
        graph_id=graph_id or _slug(stem or family or "part"),
        stem=stem,
        family=family,
    )

    if not chain or chain[0].name != "Workplane":
        raise CadQueryParseError("result chain must start with Workplane(...)")

    program.source_plane = str(chain[0].args[0]).upper() if chain[0].args else "XY"
    lowerer = ChainLowerer(program)
    body = lowerer.lower_ops(chain[1:], initial_plane=program.source_plane, result_prefix="body")
    if body is None or not program.steps:
        program.unsupported.append("no features lowered")

    _collect_numeric_literals(program)
    return program
