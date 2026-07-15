"""Bias guide occupancy and local phase contracts; no geometry is created here."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class TopologyClosure(str, Enum):
    UNRESOLVED = "unresolved"
    ASSUMPTION_ONLY = "assumption_only"
    CLOSED_WITH_EVIDENCE = "closed_with_evidence"


class GuidePhase(str, Enum):
    UNLOCK = "unlock"
    CAPTURE = "capture"
    TRANSLATE_AND_TRANSFER = "translate_and_transfer"
    SEAT = "seat"
    LOCK = "lock"
    DWELL = "dwell"


ROW_DIRECTIONS = {
    ("A40", "upper"): 1,
    ("A40", "lower"): -1,
    ("A41", "upper"): -1,
    ("A41", "lower"): 1,
}


@dataclass(frozen=True)
class GuideOccupancy:
    state_id: str
    slots: tuple[tuple[str, str | None], ...]

    def __post_init__(self) -> None:
        if not self.state_id.strip():
            raise ValueError("state_id must not be empty")
        slot_ids = tuple(slot_id for slot_id, _block_id in self.slots)
        block_ids = tuple(
            block_id for _slot_id, block_id in self.slots if block_id is not None
        )
        if any(not slot_id.strip() for slot_id in slot_ids):
            raise ValueError(f"{self.state_id} has an empty slot ID")
        if any(not block_id.strip() for block_id in block_ids):
            raise ValueError(f"{self.state_id} has an empty block ID")
        if len(slot_ids) != len(set(slot_ids)):
            raise ValueError(f"{self.state_id} has duplicate slot IDs")
        if len(block_ids) != len(set(block_ids)):
            raise ValueError(f"{self.state_id} has duplicate block IDs")
        if not any(block_id is None for _slot_id, block_id in self.slots):
            raise ValueError(f"{self.state_id} must expose a receiving location")

    @property
    def block_ids(self) -> frozenset[str]:
        return frozenset(
            block_id for _slot_id, block_id in self.slots if block_id is not None
        )


@dataclass(frozen=True)
class GuideIndexTopology:
    closure: TopologyClosure
    states: tuple[GuideOccupancy, ...] = ()
    evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if self.closure is TopologyClosure.CLOSED_WITH_EVIDENCE:
            if not self.evidence_ref:
                raise ValueError("closed guide topology requires an evidence reference")
            if tuple(state.state_id for state in self.states) != ("S0", "S1", "S2"):
                raise ValueError(
                    "closed guide topology requires ordered S0, S1, and S2 states"
                )
            identities = self.states[0].block_ids
            if not identities:
                raise ValueError("closed guide topology must contain guide blocks")
            for state in self.states[1:]:
                if state.block_ids != identities:
                    raise ValueError(
                        "S0, S1, and S2 must preserve the same block identities"
                    )
        elif self.evidence_ref is not None:
            raise ValueError(
                "only closed_with_evidence topology may carry closure evidence"
            )

    @property
    def block_count(self) -> int | None:
        return len(self.states[0].block_ids) if self.states else None

    def require_functional_release(self) -> None:
        if self.closure is not TopologyClosure.CLOSED_WITH_EVIDENCE:
            raise ValueError(
                "functional guide release requires closed_with_evidence S0/S1/S2 occupancy"
            )


def unresolved_guide_topology() -> GuideIndexTopology:
    return GuideIndexTopology(closure=TopologyClosure.UNRESOLVED)


def normalize_local_phase(angle_degrees: float) -> float:
    if not math.isfinite(angle_degrees):
        raise ValueError("guide phase must be finite")
    return angle_degrees % 360.0


def guide_phase_at(angle_degrees: float) -> GuidePhase:
    phase = normalize_local_phase(angle_degrees)
    if phase < 30.0:
        return GuidePhase.UNLOCK
    if phase < 90.0:
        return GuidePhase.CAPTURE
    if phase < 210.0:
        return GuidePhase.TRANSLATE_AND_TRANSFER
    if phase < 270.0:
        return GuidePhase.SEAT
    if phase < 320.0:
        return GuidePhase.LOCK
    return GuidePhase.DWELL
