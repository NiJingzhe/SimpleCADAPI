"""CadQuery string selector hints for QL / list-comprehension emission."""

from __future__ import annotations

from typing import Optional, Sequence


def cq_selector_to_ql_hint(selector: str, *, on: str) -> Optional[str]:
    """Best-effort QL hint for common CadQuery face selectors."""

    text = str(selector).strip()
    if not text:
        return None

    if on == "faces":
        mapping = {
            ">X": 'ql.prop("geom.normal.x", ">", 0.9)',
            "<X": 'ql.prop("geom.normal.x", "<", -0.9)',
            ">Y": 'ql.prop("geom.normal.y", ">", 0.9)',
            "<Y": 'ql.prop("geom.normal.y", "<", -0.9)',
            ">Z": 'ql.prop("geom.normal.z", ">", 0.9)',
            "<Z": 'ql.prop("geom.normal.z", "<", -0.9)',
        }
        return mapping.get(text)

    return None


def cq_parallel_edge_expr(selector: str, body: str) -> Optional[str]:
    """Emit an edge list for CadQuery parallel selectors (|X/|Y/|Z)."""

    text = str(selector).strip()
    axis = {"|X": 0, "|Y": 1, "|Z": 2}.get(text)
    if axis is None:
        return None
    return (
        f"[e for e in {body}.get_edges() "
        f"if abs((e.get_end_vertex().get_coordinates()[{axis}] "
        f"- e.get_start_vertex().get_coordinates()[{axis}]) "
        f"/ max(e.get_length(), 1e-9)) > 0.9]"
    )


def cq_extreme_edge_expr(selector: str, body: str) -> Optional[str]:
    """Emit an edge list for CadQuery extreme selectors (>X/<X/>Y/<Y/>Z/<Z).

    CadQuery DirectionMinMax uses a stable edge location; SimpleCAD's
    ``get_center()`` for seam/circle edges can sit on the perimeter and make a
    center-only extreme test pick the wrong edges (e.g. washer ``>Z or <Z``).
    Prefer vertex extents so edges that touch the solid's extreme plane match.
    """

    text = str(selector).strip()
    if " or " in text.lower():
        parts = [part.strip() for part in text.replace(" OR ", " or ").split(" or ") if part.strip()]
        exprs = [cq_extreme_edge_expr(part, body) for part in parts]
        if all(exprs):
            joined = " + ".join(f"({expr})" for expr in exprs)
            return f"({joined})"
        return None
    mapping = {
        ">X": (0, "max"),
        "<X": (0, "min"),
        ">Y": (1, "max"),
        "<Y": (1, "min"),
        ">Z": (2, "max"),
        "<Z": (2, "min"),
    }
    spec = mapping.get(text)
    if spec is None:
        return None
    axis, extreme = spec
    # Touch the global min/max vertex coordinate on this axis.
    if extreme == "max":
        return (
            f"[e for e in {body}.get_edges() if e.get_vertices() and abs("
            f"max(tuple(v.get_coordinates())[{axis}] for v in e.get_vertices()) - "
            f"max(max(tuple(v.get_coordinates())[{axis}] for v in ee.get_vertices()) "
            f"for ee in {body}.get_edges() if ee.get_vertices())) < 1e-6]"
        )
    return (
        f"[e for e in {body}.get_edges() if e.get_vertices() and abs("
        f"min(tuple(v.get_coordinates())[{axis}] for v in e.get_vertices()) - "
        f"min(min(tuple(v.get_coordinates())[{axis}] for v in ee.get_vertices()) "
        f"for ee in {body}.get_edges() if ee.get_vertices())) < 1e-6]"
    )


def cq_face_edges_expr(selector: str, body: str) -> Optional[str]:
    """Emit edges belonging to faces matched by a CadQuery face selector."""

    hint = cq_selector_to_ql_hint(selector, on="faces")
    if hint is None:
        return None
    return (
        f"[e for f in ql.select({body}.get_faces()).where({hint}).all() "
        f"for e in f.get_edges()]"
    )


def cq_edges_from_centers_expr(
    body: str,
    centers: Sequence[tuple[float, float, float]],
    *,
    tol: float = 1e-3,
) -> Optional[str]:
    """Match edges by fingerprint centers (CQ topology indices are not portable)."""

    if not centers:
        return None
    points = ", ".join(f"({c[0]!r}, {c[1]!r}, {c[2]!r})" for c in centers)
    return (
        f"[e for e in {body}.get_edges() if any("
        f"((tuple(e.get_center())[0]-cx)**2 + (tuple(e.get_center())[1]-cy)**2 + "
        f"(tuple(e.get_center())[2]-cz)**2) ** 0.5 < {tol!r} "
        f"for cx, cy, cz in [{points}])]"
    )
