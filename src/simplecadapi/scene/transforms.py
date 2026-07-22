"""Deterministic rigid-transform primitives used by Scene validation."""

from __future__ import annotations

from typing import Mapping, Sequence


RigidTransform = Mapping[str, Sequence[float]]


def compose_rigid_transforms(
    left: RigidTransform, right: RigidTransform
) -> dict[str, list[float]]:
    """Compose parent-relative transforms using fixed multiply/add order."""

    def rotate(vector: Sequence[float]) -> list[float]:
        return [
            (left["x_axis"][index] * vector[0] + left["y_axis"][index] * vector[1])
            + left["z_axis"][index] * vector[2]
            for index in range(3)
        ]

    rotated_origin = rotate(right["origin"])
    return {
        "origin": [
            left["origin"][index] + rotated_origin[index] for index in range(3)
        ],
        "x_axis": rotate(right["x_axis"]),
        "y_axis": rotate(right["y_axis"]),
        "z_axis": rotate(right["z_axis"]),
    }


def rigid_transforms_equal(actual: RigidTransform, expected: RigidTransform) -> bool:
    """Compare derived transforms with the frozen Scene numeric profile."""

    origin_epsilon = max(
        1e-9,
        1e-12
        * max(
            1.0,
            *(abs(component) for component in actual["origin"]),
            *(abs(component) for component in expected["origin"]),
        ),
    )
    return all(
        abs(left - right) <= origin_epsilon
        for left, right in zip(actual["origin"], expected["origin"])
    ) and all(
        abs(left - right) <= 1e-12
        for key in ("x_axis", "y_axis", "z_axis")
        for left, right in zip(actual[key], expected[key])
    )


__all__ = ["compose_rigid_transforms", "rigid_transforms_equal"]
