"""Discrete multi-cycle yarn, loop, and edge-hook identity conservation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class YarnFamily(str, Enum):
    WARP = "warp_0"
    BIAS_POSITIVE = "bias_positive"
    BIAS_NEGATIVE = "bias_negative"
    FILLING = "filling_90"
    BINDER = "binder_z"


@dataclass(frozen=True)
class YarnEnd:
    yarn_id: str
    family: YarnFamily
    supply_id: str
    guide_id: str | None = None

    def __post_init__(self) -> None:
        if not self.yarn_id.strip() or not self.supply_id.strip():
            raise ValueError("yarn and supply IDs must not be empty")
        if (
            self.family in (YarnFamily.BIAS_POSITIVE, YarnFamily.BIAS_NEGATIVE)
            and not self.guide_id
        ):
            raise ValueError("bias yarns require one guide identity")


@dataclass(frozen=True)
class EdgeHook:
    hook_id: str
    side: str
    insertion_cycle: int
    x_position: float

    def __post_init__(self) -> None:
        if not self.hook_id.strip():
            raise ValueError("hook ID must not be empty")
        if self.side not in {"left", "right"}:
            raise ValueError("hook side must be left or right")
        if self.insertion_cycle <= 0 or not math.isfinite(self.x_position):
            raise ValueError("hook cycle must be positive and position finite")


@dataclass(frozen=True)
class FillingLoop:
    loop_id: str
    cycle_index: int
    insertion: str
    channel: str

    def __post_init__(self) -> None:
        if not self.loop_id.strip() or self.cycle_index <= 0:
            raise ValueError("filling loop ID and cycle must be valid")
        if self.insertion not in {"A", "B"} or self.channel not in {
            "top",
            "middle",
            "bottom",
        }:
            raise ValueError("filling loops require insertion A/B and a valid channel")


@dataclass(frozen=True)
class YarnTopologyState:
    cycle_index: int = 0
    yarn_ends: tuple[YarnEnd, ...] = ()
    hooks: tuple[EdgeHook, ...] = ()
    filling_loops: tuple[FillingLoop, ...] = ()

    def __post_init__(self) -> None:
        if self.cycle_index < 0:
            raise ValueError("cycle_index must not be negative")
        for label, values in (
            ("yarn", tuple(item.yarn_id for item in self.yarn_ends)),
            ("hook", tuple(item.hook_id for item in self.hooks)),
            ("loop", tuple(item.loop_id for item in self.filling_loops)),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identity")
        bias = tuple(
            item
            for item in self.yarn_ends
            if item.family in (YarnFamily.BIAS_POSITIVE, YarnFamily.BIAS_NEGATIVE)
        )
        guide_ids = tuple(item.guide_id for item in bias)
        supply_ids = tuple(item.supply_id for item in bias)
        if len(guide_ids) != len(set(guide_ids)) or len(supply_ids) != len(
            set(supply_ids)
        ):
            raise ValueError("bias guide and supply identities must be one-to-one")


def advance_yarn_cycle(
    state: YarnTopologyState, *, takeup_step: float
) -> YarnTopologyState:
    if not math.isfinite(takeup_step) or takeup_step <= 0:
        raise ValueError("takeup_step must be finite and positive")
    cycle = state.cycle_index + 1
    moved_hooks = tuple(
        EdgeHook(
            item.hook_id, item.side, item.insertion_cycle, item.x_position + takeup_step
        )
        for item in state.hooks
    )
    new_hooks = (
        EdgeHook(f"hook-left-{cycle:04d}", "left", cycle, takeup_step),
        EdgeHook(f"hook-right-{cycle:04d}", "right", cycle, takeup_step),
    )
    new_loops = tuple(
        FillingLoop(
            loop_id=f"fill-{cycle:04d}-{insertion.lower()}-{channel}",
            cycle_index=cycle,
            insertion=insertion,
            channel=channel,
        )
        for insertion in ("A", "B")
        for channel in ("top", "middle", "bottom")
    )
    return YarnTopologyState(
        cycle_index=cycle,
        yarn_ends=state.yarn_ends,
        hooks=moved_hooks + new_hooks,
        filling_loops=state.filling_loops + new_loops,
    )
