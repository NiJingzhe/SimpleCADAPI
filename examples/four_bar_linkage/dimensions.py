"""Planar four-bar linkage dimensions.

The linkage closes when the crank, coupler, rocker, and ground span share a
common plane and the four revolute axes are parallel to Z. Crank and rocker
pivot on the ground span; the coupler joins their tips.

Bar set (Grashof crank-rocker, mm):

    ground (A--D) 40, crank (A--B) 20, coupler (B--C) 50, rocker (D--C) 35.
    s + l = 20 + 50 = 70 < p + q = 35 + 40, so the crank fully rotates.

All pivots in the XY plane at Z = 0. With the crank along +X
(B = (20, 0)), intersecting the circles |C - B| = 50 and |C - D| = 35
(center distance 20) gives C = (61.875, 27.322).
"""

from __future__ import annotations

import math

# Bar center distances (pivot-to-pivot).
GROUND_LENGTH = 40.0
CRANK_LENGTH = 20.0
COUPLER_LENGTH = 50.0
ROCKER_LENGTH = 35.0

# Forged-link cross-section proportions.
EYE_OUTER_RADIUS = 5.0
PIVOT_BORE_RADIUS = 2.05
BAR_THICKNESS = 4.0

# Pivot bolt (hex-head pin) proportions.
PIVOT_BOLT_SHAFT_RADIUS = 2.0
PIVOT_BOLT_HEAD_RADIUS = 3.4
PIVOT_BOLT_HEAD_THICKNESS = 2.4
PIVOT_BOLT_SHANK_LENGTH = 11.0

# Ground pivots: A at origin, D at (GROUND_LENGTH, 0).
CRANK_PIVOT = (0.0, 0.0)
ROCKER_PIVOT = (GROUND_LENGTH, 0.0)
CRANK_TIP = (CRANK_LENGTH, 0.0)

# Closed-form coupler tip from the two-circle intersection (module docstring).
COUPLER_TIP = (61.875, math.sqrt(746.484375))

# Assembled-pose bar angles (degrees CCW from +X).
CRANK_ASSEMBLED_ANGLE_DEG = 0.0
COUPLER_ASSEMBLED_ANGLE_DEG = math.degrees(
    math.atan2(COUPLER_TIP[1] - CRANK_TIP[1], COUPLER_TIP[0] - CRANK_TIP[0])
)
ROCKER_ASSEMBLED_ANGLE_DEG = math.degrees(
    math.atan2(
        COUPLER_TIP[1] - ROCKER_PIVOT[1], COUPLER_TIP[0] - ROCKER_PIVOT[0]
    )
)

# Search bounds for the loop-closing revolute; wide enough to contain the
# assembled solution around the authored pose.
CLOSURE_ANGLE_LIMIT = (-30.0, 30.0)
