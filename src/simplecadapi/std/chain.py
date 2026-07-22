"""Roller-chain standard parts built from pitch and roller dimensions."""

from __future__ import annotations

import math

from ..core import Solid
from ..operations import cut_rsolid, make_cylinder_rsolid

__all__ = ["make_roller_chain_sprocket_rsolid"]


def _positive_finite(name: str, value: float) -> float:
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return resolved


def make_roller_chain_sprocket_rsolid(
    n_teeth: int,
    chain_pitch: float,
    roller_diameter: float,
    sprocket_thickness: float,
    *,
    bore_radius: float = 0.0,
    roller_clearance: float = 0.15,
) -> Solid:
    """Create a roller-chain sprocket from the chain engagement dimensions.

    The pitch radius follows the regular pitch polygon. Circular roller-seat
    cutters are placed at every pitch point and opened through the standard
    engineering outside-diameter envelope ``p * (0.6 + cot(180 / z))``. The
    result preserves the tooth count, pitch, roller seats, root diameter, and
    outside diameter needed for assembly-level selection.

    A released sprocket still requires the selected chain standard's permitted
    tooth-form range, tooth width, hub, material, heat treatment, runout, and
    supplier checks.
    """
    if not isinstance(n_teeth, int) or isinstance(n_teeth, bool) or n_teeth < 6:
        raise ValueError("n_teeth must be an integer of at least 6")
    pitch = _positive_finite("chain_pitch", chain_pitch)
    roller = _positive_finite("roller_diameter", roller_diameter)
    thickness = _positive_finite("sprocket_thickness", sprocket_thickness)
    resolved_bore = float(bore_radius)
    resolved_clearance = float(roller_clearance)
    if not math.isfinite(resolved_bore) or resolved_bore < 0.0:
        raise ValueError("bore_radius must be non-negative and finite")
    if not math.isfinite(resolved_clearance) or resolved_clearance < 0.0:
        raise ValueError("roller_clearance must be non-negative and finite")
    if roller >= pitch:
        raise ValueError("roller_diameter must be smaller than chain_pitch")

    half_tooth_angle = math.pi / n_teeth
    pitch_radius = pitch / (2.0 * math.sin(half_tooth_angle))
    seat_radius = roller / 2.0 + resolved_clearance
    root_radius = pitch_radius - seat_radius
    outside_radius = pitch * (0.6 + 1.0 / math.tan(half_tooth_angle)) / 2.0
    if root_radius <= 0.0:
        raise ValueError("chain dimensions produce a non-positive root radius")
    if not root_radius < outside_radius < pitch_radius + seat_radius:
        raise ValueError("chain dimensions do not produce open roller seats")
    if resolved_bore >= root_radius:
        raise ValueError("bore_radius must be smaller than the sprocket root radius")

    blank = make_cylinder_rsolid(
        radius=outside_radius,
        height=thickness,
        bottom_face_center=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
    )
    cutters = [
        make_cylinder_rsolid(
            radius=seat_radius,
            height=thickness + 0.4,
            bottom_face_center=(
                pitch_radius * math.cos(2.0 * math.pi * index / n_teeth),
                pitch_radius * math.sin(2.0 * math.pi * index / n_teeth),
                -0.2,
            ),
            axis=(0.0, 0.0, 1.0),
        )
        for index in range(n_teeth)
    ]
    if resolved_bore > 0.0:
        cutters.append(
            make_cylinder_rsolid(
                radius=resolved_bore,
                height=thickness + 0.4,
                bottom_face_center=(0.0, 0.0, -0.2),
                axis=(0.0, 0.0, 1.0),
            )
        )
    sprocket = cut_rsolid(blank, cutters, skip_non_intersecting=False)
    sprocket.set_metadata(
        "std.chain.roller_sprocket",
        {
            "n_teeth": n_teeth,
            "chain_pitch": pitch,
            "roller_diameter": roller,
            "sprocket_thickness": thickness,
            "bore_radius": resolved_bore,
            "roller_clearance": resolved_clearance,
            "pitch_radius": pitch_radius,
            "root_radius": root_radius,
            "outside_radius": outside_radius,
        },
    )
    return sprocket
