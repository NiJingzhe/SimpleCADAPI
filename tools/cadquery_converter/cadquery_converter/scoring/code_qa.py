"""Code-QA answerability scoring (BenchCAD QA exploration)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .parameters import extract_scad_vars


@dataclass
class CodeQAScore:
    answerable: bool = False
    derived_answer: Optional[str] = None
    match: Optional[bool] = None
    qa_type: str = ""
    method: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    scope: str = "sftc"  # sftc | cq_structure | unknown

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

# Questions about CadQuery source structure — not expected from SFTC alone.
_CQ_STRUCTURE_HINTS = (
    "workplane() calls",
    "sketch workplanes",
    "1-indexed line",
    "along which axis",
    "primary extrusion occur",
    "delete the last",
    "if you delete",
)


def _normalize_answer(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return str(int(value))
        return f"{float(value):.6g}"
    text = str(value).strip()
    try:
        num = float(text)
        if num.is_integer():
            return str(int(num))
        return f"{num:.6g}"
    except ValueError:
        return text.lower()


def _answers_equal(expected: Any, derived: Any, *, tol: float = 0.05) -> bool:
    """BenchCAD QA uses ±5% for ratios; keep same default for dims."""
    a = _normalize_answer(expected)
    b = _normalize_answer(derived)
    try:
        fa, fb = float(a), float(b)
        return abs(fa - fb) <= tol * max(1.0, abs(fa))
    except ValueError:
        return a == b


def _candidate_magnitudes(vars_map: Dict[str, float]) -> List[Tuple[str, float, str]]:
    """(label, value, role) including diameter↔radius duals."""
    out: List[Tuple[str, float, str]] = []
    for name, value in vars_map.items():
        out.append((name, value, "raw"))
        lower = name.lower()
        if "radius" in lower and "diameter" not in lower:
            out.append((f"{name}*2", value * 2.0, "as_diameter"))
        if "diameter" in lower:
            out.append((f"{name}/2", value / 2.0, "as_radius"))
    return out


def _value_recover_ratio(
    vars_map: Dict[str, float],
    answer: Any,
    *,
    tol: float = 0.05,
) -> Optional[Tuple[str, float, Dict[str, Any]]]:
    """Search numeric pairs in SFTC vars that recover the gold ratio (±5%)."""
    try:
        target = float(_normalize_answer(answer))
    except ValueError:
        return None
    if abs(target) < 1e-12:
        return None
    cands = _candidate_magnitudes(vars_map)
    best = None
    for i, (n0, a, _r0) in enumerate(cands):
        for n1, b, _r1 in cands[i + 1 :]:
            if abs(b) < 1e-12:
                continue
            for num, den, label in ((a, b, f"{n0}/{n1}"), (b, a, f"{n1}/{n0}")):
                if abs(den) < 1e-12:
                    continue
                derived = num / den
                if abs(derived - target) <= tol * max(1.0, abs(target)):
                    err = abs(derived - target)
                    if best is None or err < best[0]:
                        best = (err, label, derived, {"pair": [n0, n1], "values": [num, den]})
    if best is None:
        return None
    _, label, derived, details = best
    return label, derived, details


def _value_recover_dim(
    vars_map: Dict[str, float],
    answer: Any,
    *,
    tol: float = 0.05,
) -> Optional[Tuple[str, float]]:
    try:
        target = float(_normalize_answer(answer))
    except ValueError:
        return None
    cands = _candidate_magnitudes(vars_map)
    # Prefer exact raw vars, then duals
    for name, value, role in cands:
        if abs(value - target) <= tol * max(1.0, abs(target)):
            return f"{name}:{role}", value
    # Sum of depths
    depths = [v for n, v in vars_map.items() if any(t in n.lower() for t in ("extrude_distance", "cut_depth", "depth"))]
    if depths and abs(sum(depths) - target) <= tol * max(1.0, abs(target)):
        return "sum_depths", sum(depths)
    return None


def _find_params_for_keywords(
    vars_map: Dict[str, float],
    keywords: List[str],
) -> List[Tuple[str, float]]:
    hits: List[Tuple[str, float]] = []
    seen: set[str] = set()
    for key in keywords:
        key_l = key.lower().replace(" ", "_")
        for name, value in vars_map.items():
            if name in seen:
                continue
            if key_l in name.lower():
                hits.append((name, value))
                seen.add(name)
    return hits


def _keyword_aliases(question: str) -> List[str]:
    q = question.lower()
    aliases: List[str] = []
    mapping = [
        (("od", "outer diameter", "outer radius", "barrel", "across-flats", "across flats", "hex"), ["outer_radius", "cylinder_radius", "polygon", "width", "rect_width"]),
        (("thread", "id", "inner", "bore", "hole"), ["hole_diameter", "inner", "cylinder_radius"]),
        (("thickness", "depth", "extrude", "cutblind", "flange", "seat"), ["extrude_distance", "cut_depth", "depth", "height", "rect_height"]),
        (("width", "plate width", "block length", "leg", "length", "tabletop"), ["width", "rect_width", "depth"]),
        (("height", "arm height", "fin height", "base height"), ["height", "rect_height", "cylinder_height", "extrude_distance"]),
        (("chamfer",), ["chamfer_distance"]),
        (("fillet",), ["fillet_radius"]),
        (("radius", "cylinder", "rim", "rod"), ["cylinder_radius", "outer_radius", "sphere_radius"]),
        (("diameter",), ["hole_diameter", "cylinder_radius", "outer_radius"]),
        (("pitch",), ["pitch", "extrude_distance", "height"]),
        (("angle", "gap"), ["angle", "revolve_angle"]),
    ]
    for keys, stems in mapping:
        if any(k in q for k in keys):
            aliases.extend(stems)
    return aliases


def score_code_qa(
    *,
    sftc_source: str,
    question: str,
    answer: Any,
    qa_type: str = "",
    feature_manifest: Optional[Dict[str, Any]] = None,
) -> CodeQAScore:
    """Best-effort: derive answer from scad.var / feature counts.

    BenchCAD emits CQ with *inlined literals* and asks engineering-named questions
    (barrel OD, across-flats, …). Name-based matching is therefore weak; we also
    attempt value recovery (±5%, matching BenchCAD's ratio tolerance).
    """
    qa_type = (qa_type or "").lower()
    vars_map = extract_scad_vars(sftc_source)
    q = question.lower()
    feature_manifest = feature_manifest or {}
    units = feature_manifest.get("feature_units") or []

    if any(hint in q for hint in _CQ_STRUCTURE_HINTS):
        return CodeQAScore(
            answerable=False,
            qa_type=qa_type or "integer",
            method="cq_structure_out_of_scope",
            scope="cq_structure",
            details={"reason": "requires CadQuery source structure"},
        )

    if not qa_type:
        if any(word in q for word in ("how many", "number of", "count")):
            qa_type = "integer"
        elif "ratio" in q or " / " in q:
            qa_type = "ratio"
        else:
            qa_type = "dim"

    if "opening gap angle" in q or ("angle" in q and "degree" in q):
        angles = [(n, v) for n, v in vars_map.items() if "angle" in n.lower()]
        if angles:
            name, value = angles[0]
            return CodeQAScore(
                answerable=True,
                derived_answer=_normalize_answer(value),
                match=_answers_equal(answer, value),
                qa_type="dim",
                method=f"param:{name}",
                details={"param": name, "value": value},
            )
        recovered = _value_recover_dim(vars_map, answer)
        if recovered:
            label, value = recovered
            return CodeQAScore(
                answerable=True,
                derived_answer=_normalize_answer(value),
                match=True,
                qa_type="dim",
                method=f"value_recover:{label}",
                details={"note": "angle not named; value present in vars"},
            )
        return CodeQAScore(answerable=False, qa_type="dim", method="no_angle_param")

    if "sum" in q and ("extrude" in q or "cutblind" in q or "depth" in q):
        depths = [
            value
            for name, value in vars_map.items()
            if any(tok in name.lower() for tok in ("extrude_distance", "cut_depth", "depth"))
        ]
        if depths:
            derived = sum(depths)
            return CodeQAScore(
                answerable=True,
                derived_answer=_normalize_answer(derived),
                match=_answers_equal(answer, derived),
                qa_type="dim",
                method="sum_depths",
                details={"depths": depths},
            )

    if qa_type in {"integer", "int"}:
        if q.startswith("is ") or q.startswith("does ") or " less than" in q or " at least" in q:
            if "cylinder radius" in q:
                radii = [
                    (value / 2.0) if "diameter" in name.lower() else value
                    for name, value in vars_map.items()
                    if "radius" in name.lower() or "diameter" in name.lower()
                ]
                if len(radii) >= 2:
                    smallest, largest = min(radii), max(radii)
                    if "less than half" in q:
                        derived = 1 if smallest < 0.5 * largest else 0
                    elif "at least half" in q:
                        derived = 1 if smallest >= 0.5 * largest else 0
                    else:
                        derived = None
                    if derived is not None:
                        return CodeQAScore(
                            answerable=True,
                            derived_answer=str(derived),
                            match=_answers_equal(answer, derived, tol=0.0),
                            qa_type="integer",
                            method="cylinder_radius_compare",
                            details={"radii": radii},
                        )
            return CodeQAScore(
                answerable=False,
                qa_type="integer",
                method="boolean_unhandled",
                details={"question": question[:160]},
            )

        if "extrusion-style" in q or ("extrude" in q and "cutblind" in q):
            count = sum(1 for unit in units if unit.get("kind") in {"Extrude", "Cut"})
            if count == 0:
                count = sum(
                    1
                    for unit in units
                    for kind in unit.get("cq_trace_kinds") or []
                    if kind in {"extrude", "cutBlind"}
                )
            return CodeQAScore(
                answerable=True,
                derived_answer=str(count),
                match=_answers_equal(answer, count, tol=0.0),
                qa_type="integer",
                method="count_extrude_cutblind",
                details={"count": count},
            )

        kind_map = [
            (("through-hole", "through hole", "hole"), "Hole"),
            (("fillet",), "Fillet"),
            (("chamfer",), "Chamfer"),
            (("extrude",), "Extrude"),
            (("cut",), "Cut"),
        ]
        for keywords, kind in kind_map:
            if any(k in q for k in keywords):
                count = sum(1 for unit in units if unit.get("kind") == kind)
                if count == 0 and kind == "Hole":
                    count = sum(1 for name in vars_map if "hole" in name.lower())
                return CodeQAScore(
                    answerable=True,
                    derived_answer=str(count),
                    match=_answers_equal(answer, count, tol=0.0),
                    qa_type="integer",
                    method=f"count_{kind.lower()}",
                    details={"count": count},
                )
        return CodeQAScore(answerable=False, qa_type="integer", method="no_keyword")

    if qa_type in {"ratio"}:
        aliases = _keyword_aliases(question)
        hits = _find_params_for_keywords(vars_map, aliases)
        if len(hits) >= 2:
            (n0, a), (n1, b) = hits[0], hits[1]
            if "diameter" in q and "radius" in n0.lower():
                a = a * 2.0
            if "diameter" in q and "radius" in n1.lower():
                b = b * 2.0
            if abs(b) > 1e-12:
                derived = a / b
                if _answers_equal(answer, derived):
                    return CodeQAScore(
                        answerable=True,
                        derived_answer=_normalize_answer(derived),
                        match=True,
                        qa_type="ratio",
                        method=f"name_pair:{n0}/{n1}",
                        details={"pair": [n0, n1]},
                    )
        recovered = _value_recover_ratio(vars_map, answer)
        if recovered:
            label, derived, details = recovered
            return CodeQAScore(
                answerable=True,
                derived_answer=_normalize_answer(derived),
                match=True,
                qa_type="ratio",
                method=f"value_pair:{label}",
                details=details,
            )
        return CodeQAScore(answerable=False, qa_type="ratio", method="insufficient_params")

    # dim / default
    if "smallest" in q and "radius" in q:
        radii = [(n, v) for n, v in vars_map.items() if "radius" in n.lower()]
        if radii:
            name, value = min(radii, key=lambda item: item[1])
            return CodeQAScore(
                answerable=True,
                derived_answer=_normalize_answer(value),
                match=_answers_equal(answer, value),
                qa_type="dim",
                method=f"min_radius:{name}",
                details={"param": name, "value": value},
            )

    aliases = _keyword_aliases(question)
    hits = _find_params_for_keywords(vars_map, aliases)
    hit = hits[0] if hits else None
    if hit is not None:
        name, value = hit
        if "diameter" in q and "radius" in name.lower() and "diameter" not in name.lower():
            value = value * 2.0
        if _answers_equal(answer, value):
            return CodeQAScore(
                answerable=True,
                derived_answer=_normalize_answer(value),
                match=True,
                qa_type=qa_type or "dim",
                method=f"param:{name}",
                details={"param": name, "value": value},
            )

    recovered = _value_recover_dim(vars_map, answer)
    if recovered:
        label, value = recovered
        return CodeQAScore(
            answerable=True,
            derived_answer=_normalize_answer(value),
            match=True,
            qa_type=qa_type or "dim",
            method=f"value_recover:{label}",
            details={"label": label, "value": value},
        )

    if hit is not None:
        name, value = hit
        if "diameter" in q and "radius" in name.lower() and "diameter" not in name.lower():
            value = value * 2.0
        return CodeQAScore(
            answerable=True,
            derived_answer=_normalize_answer(value),
            match=False,
            qa_type=qa_type or "dim",
            method=f"param:{name}",
            details={"param": name, "value": value},
        )

    return CodeQAScore(answerable=False, qa_type=qa_type or "dim", method="no_param")
