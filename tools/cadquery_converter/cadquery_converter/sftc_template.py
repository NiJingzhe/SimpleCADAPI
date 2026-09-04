"""Shared SFTC / Feature Tree Convention (FTC) module emission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .ir import ParameterSpec, fmt_num

# Paper FTC → SimpleCAD API → CAD feature manager
FTC_FEATURE_MAP: Dict[str, str] = {
    "box": "Primitive + Extrude equivalent",
    "cylinder": "Primitive solid",
    "sphere": "Primitive solid",
    "extrude circle": "Sketch + Extrude",
    "extrude profile": "Sketch + Extrude",
    "extrude rectangle": "Sketch + Extrude",
    "revolve": "Revolve",
    "loft": "Loft",
    "through hole": "Hole",
    "blind cut": "Cut / Pocket",
    "through cut": "Cut / Through-all",
    "boolean cut": "Cut",
    "boolean union": "Join / Combine",
    "boolean intersect": "Intersect",
    "fillet": "Fillet",
    "chamfer": "Chamfer",
    "pattern pocket cut": "Pattern + Cut",
}


@dataclass
class ParameterProvenance:
    name: str
    feature_index: int = 0
    kind: str = ""
    source_trace_ops: List[str] = field(default_factory=list)


@dataclass
class ParameterRegistry:
    """Collect tunable dimensions for the Parameters section."""

    _params: Dict[str, ParameterSpec] = field(default_factory=dict)
    _counters: Dict[str, int] = field(default_factory=dict)
    _provenance: Dict[str, ParameterProvenance] = field(default_factory=dict)
    _active_feature_index: int = 0
    _active_kind: str = ""
    _active_trace_ops: List[str] = field(default_factory=list)

    def set_active_feature(
        self,
        index: int,
        *,
        kind: str = "",
        trace_ops: Optional[Sequence[str]] = None,
    ) -> None:
        self._active_feature_index = index
        self._active_kind = kind
        self._active_trace_ops = list(trace_ops or [])

    def define(
        self,
        name: str,
        value: float,
        *,
        comment: str = "",
        unit: str = "mm",
    ) -> str:
        if name in self._params:
            return name
        self._params[name] = ParameterSpec(
            name=name,
            default=float(value),
            unit=unit,
            comment=comment,
        )
        if self._active_feature_index:
            self._provenance[name] = ParameterProvenance(
                name=name,
                feature_index=self._active_feature_index,
                kind=self._active_kind,
                source_trace_ops=list(self._active_trace_ops),
            )
        return name

    def auto(self, stem: str, value: float, *, comment: str = "") -> str:
        """Allocate a unique parameter name from a semantic stem."""
        count = self._counters.get(stem, 0) + 1
        self._counters[stem] = count
        name = stem if count == 1 else f"{stem}_{count}"
        return self.define(name, value, comment=comment)

    def items(self) -> List[ParameterSpec]:
        return list(self._params.values())

    def provenance_items(self) -> List[ParameterProvenance]:
        return list(self._provenance.values())

    def params_for_feature(self, feature_index: int) -> List[str]:
        return [
            item.name
            for item in self._provenance.values()
            if item.feature_index == feature_index
        ]


def feature_comment(index: int, description: str) -> str:
    return f"    # Feature {index}: {description}"


def result_tag(index: int, slug: str) -> str:
    import re

    safe = re.sub(r"[^a-z0-9_-]", "_", slug.lower())
    safe = re.sub(r"_+", "_", safe).strip("_") or "op"
    if not safe[0].isalpha():
        safe = f"op_{safe}"
    return f"feature.{safe}.n{index}"


def emit_sftc_module(
    *,
    graph_id: str,
    header: str,
    feature_lines: Sequence[str],
    parameters: Optional[ParameterRegistry] = None,
    unsupported: Optional[Sequence[str]] = None,
    body: Optional[str] = None,
    include_ql_import: bool = False,
) -> str:
    """Emit a complete SFTC Python module (Parameters / Feature Tree / Export)."""
    lines: List[str] = [
        f'"""{header}."""',
        "",
        "from pathlib import Path",
        "",
        "import math",
        "import simplecadapi as scad",
    ]
    if include_ql_import:
        lines.append("from simplecadapi import ql")
    lines.extend(["", "# -- Parameters --"])

    registry = parameters or ParameterRegistry()
    if registry.items():
        for param in registry.items():
            comment = f", comment={param.comment!r}" if param.comment else ""
            lines.append(
                f"{param.name} = scad.var(name={param.name!r}, default={fmt_num(param.default)}, "
                f"unit={param.unit!r}{comment})"
            )
    else:
        lines.append("# (no extracted parameters)")

    lines.extend(
        [
            "",
            "OUT = Path('out')",
            "",
            "# -- Feature Tree --",
            f"@scad.model(graph_id={graph_id!r})",
            "def build_model():",
            *feature_lines,
        ]
    )

    for note in unsupported or ():
        lines.append(f"    # SFTC_UNSUPPORTED: {note}")

    if body:
        lines.extend(
            [
                f"    print('volume', round({body}.get_volume(), 3))",
                f"    scad.capture_result(value={body})",
                f"    return {body}",
            ]
        )
    else:
        lines.extend(
            [
                "    raise RuntimeError('feature tree produced no solid')",
                "    return None  # unreachable",
            ]
        )

    lines.extend(
        [
            "",
            "",
            "# -- Export --",
            "def main() -> None:",
            "    OUT.mkdir(parents=True, exist_ok=True)",
            "    result = build_model()",
            f"    scad.export_step(shapes=result.value, filename=str(OUT / '{graph_id}.step'))",
            "",
            "",
            "if __name__ == '__main__':",
            "    main()",
            "",
        ]
    )
    return "\n".join(lines)
