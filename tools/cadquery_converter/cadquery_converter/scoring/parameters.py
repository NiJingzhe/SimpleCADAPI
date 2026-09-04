"""Parameter-layer scoring: scad.var defaults vs feature_manifest provenance."""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParameterScore:
    declared_count: int = 0
    referenced_count: int = 0
    param_match_rate: float = 0.0
    unreferenced: List[str] = field(default_factory=list)
    declared_names: List[str] = field(default_factory=list)
    manifest_param_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_VAR_ASSIGN = re.compile(
    r"^(\w+)\s*=\s*scad\.var\s*\(\s*name\s*=\s*['\"](\w+)['\"]\s*,\s*default\s*=\s*([-+eE0-9.]+)",
    re.MULTILINE,
)


def extract_scad_vars(sftc_source: str) -> Dict[str, float]:
    """Parse `name = scad.var(name=..., default=...)` declarations."""
    found: Dict[str, float] = {}
    for match in _VAR_ASSIGN.finditer(sftc_source):
        py_name, var_name, default = match.group(1), match.group(2), match.group(3)
        try:
            found[py_name] = float(default)
        except ValueError:
            found[py_name] = float("nan")
        if var_name != py_name:
            found[var_name] = found[py_name]
    return found


def _names_referenced_in_feature_tree(sftc_source: str, names: List[str]) -> List[str]:
    if not names:
        return []
    try:
        tree = ast.parse(sftc_source)
    except SyntaxError:
        # Fallback: substring search inside build_model body
        body = sftc_source
        return [name for name in names if re.search(rf"\b{re.escape(name)}\b", body)]

    referenced: set[str] = set()
    name_set = set(names)

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if node.id in name_set:
                referenced.add(node.id)

    Visitor().visit(tree)
    return sorted(referenced)


def score_parameters(
    sftc_source: str,
    feature_manifest: Optional[Dict[str, Any]] = None,
) -> ParameterScore:
    declared = extract_scad_vars(sftc_source)
    names = sorted(declared.keys())
    referenced = _names_referenced_in_feature_tree(sftc_source, names)
    unreferenced = [name for name in names if name not in referenced]

    manifest_params: List[str] = []
    for unit in (feature_manifest or {}).get("feature_units") or []:
        for param in unit.get("params") or []:
            if param not in manifest_params:
                manifest_params.append(param)

    # Match rate: fraction of declared vars that are referenced in the feature tree.
    # When manifest lists params, also require those names to be declared.
    if not names:
        match_rate = 1.0 if not manifest_params else 0.0
    else:
        match_rate = len(referenced) / len(names)

    if manifest_params:
        declared_set = set(names)
        hit = sum(1 for param in manifest_params if param in declared_set)
        manifest_rate = hit / len(manifest_params)
        match_rate = min(match_rate, manifest_rate) if names else manifest_rate

    return ParameterScore(
        declared_count=len(names),
        referenced_count=len(referenced),
        param_match_rate=match_rate,
        unreferenced=unreferenced,
        declared_names=names,
        manifest_param_count=len(manifest_params),
    )
