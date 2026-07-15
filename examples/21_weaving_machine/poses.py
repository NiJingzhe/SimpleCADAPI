"""Named digital poses and virtual-main-phase mapping."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class MachinePose(str, Enum):
    HOME = "home"
    HOOK_INSERT = "hook_insert"
    HOOK_RETRACT = "hook_retract"
    GUIDE_UNLOCK = "guide_unlock"
    GUIDE_CAPTURE = "guide_capture"
    INDEX_S0 = "index_s0"
    INDEX_S1 = "index_s1"
    INDEX_S2 = "index_s2"
    GUIDE_SEAT = "guide_seat"
    GUIDE_LOCK = "guide_lock"
    FILL_A_PICK = "fill_a_pick"
    FILL_A_RETURN = "fill_a_return"
    FILL_A_CAPTURE = "fill_a_capture"
    FILL_A_BEAT = "fill_a_beat"
    NEEDLE_SWAP = "needle_swap"
    FILL_B_PICK = "fill_b_pick"
    FILL_B_RETURN = "fill_b_return"
    FILL_B_CAPTURE = "fill_b_capture"
    FILL_B_BEAT = "fill_b_beat"
    TAKEUP_START = "takeup_start"
    TAKEUP_END = "takeup_end"
    SERVICE = "service"


@dataclass(frozen=True)
class PhaseSegment:
    start_degrees: float
    end_degrees: float
    pose: MachinePose
    active_axes: tuple[str, ...]
    required_withdrawn: tuple[str, ...]


MAIN_PHASE_SEGMENTS = (
    PhaseSegment(
        0.0,
        20.0,
        MachinePose.HOOK_INSERT,
        ("M9",),
        ("guide", "rapier", "needle", "reed", "takeup"),
    ),
    PhaseSegment(
        20.0,
        70.0,
        MachinePose.INDEX_S1,
        ("M1",),
        ("rapier", "needle", "reed", "rod2", "takeup"),
    ),
    PhaseSegment(
        70.0,
        115.0,
        MachinePose.FILL_A_PICK,
        ("M3",),
        ("needle", "reed", "guide", "takeup"),
    ),
    PhaseSegment(
        115.0,
        150.0,
        MachinePose.FILL_A_RETURN,
        ("M3",),
        ("needle", "reed_forward", "guide", "takeup"),
    ),
    PhaseSegment(
        150.0,
        190.0,
        MachinePose.FILL_A_BEAT,
        ("M4", "M5", "M6", "M7", "M8"),
        ("rapier", "guide", "takeup"),
    ),
    PhaseSegment(
        190.0,
        220.0,
        MachinePose.NEEDLE_SWAP,
        ("M2", "M5", "M7"),
        ("rapier", "guide", "takeup"),
    ),
    PhaseSegment(
        220.0, 265.0, MachinePose.FILL_B_PICK, ("M3",), ("reed", "guide", "takeup")
    ),
    PhaseSegment(
        265.0,
        300.0,
        MachinePose.FILL_B_RETURN,
        ("M3",),
        ("reed_forward", "guide", "takeup"),
    ),
    PhaseSegment(
        300.0,
        335.0,
        MachinePose.FILL_B_BEAT,
        ("M4", "M5", "M6", "M7", "M8"),
        ("rapier", "guide", "takeup"),
    ),
    PhaseSegment(
        335.0,
        360.0,
        MachinePose.TAKEUP_END,
        ("M10",),
        ("guide", "rapier", "needle", "reed", "rod1", "rod2"),
    ),
)


def normalize_main_phase(angle_degrees: float) -> float:
    if not math.isfinite(angle_degrees):
        raise ValueError("main phase must be finite")
    return angle_degrees % 360.0


def pose_at_main_phase(angle_degrees: float) -> MachinePose:
    phase = normalize_main_phase(angle_degrees)
    for segment in MAIN_PHASE_SEGMENTS:
        if segment.start_degrees <= phase < segment.end_degrees:
            return segment.pose
    raise RuntimeError("main phase segmentation is incomplete")
