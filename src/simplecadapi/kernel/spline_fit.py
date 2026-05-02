"""Shared spline fitting helpers for runtime and translators."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


Point3 = Tuple[float, float, float]


def select_fit_samples(
    points: Iterable[Sequence[float]], target_count: int = 6
) -> List[Point3]:
    pts = [(float(point[0]), float(point[1]), float(point[2])) for point in points]
    if len(pts) <= 2 or target_count <= 2 or len(pts) <= target_count:
        return pts

    result: List[Point3] = [pts[0]]
    interior_count = target_count - 2
    last_index = len(pts) - 1
    for i in range(1, interior_count + 1):
        idx = round(i * last_index / (interior_count + 1))
        idx = max(1, min(last_index - 1, int(idx)))
        result.append(pts[idx])
    result.append(pts[-1])

    deduped: List[Point3] = []
    for point in result:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if len(deduped) < 2:
        return pts[:2]
    return deduped
