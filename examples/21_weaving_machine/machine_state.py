"""Immutable cumulative machine state, interlocks, and fault latching."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum


class Lifecycle(str, Enum):
    THREADING = "threading"
    PRIMED = "primed"
    FIRST_CYCLE = "first_cycle"
    PRODUCTION = "production"
    END_OF_TRAVEL = "end_of_travel"
    UNLOAD = "unload"
    RECOVERY = "recovery"


class MachineAction(str, Enum):
    GUIDE_INDEX = "guide_index"
    RAPIER_INSERT = "rapier_insert"
    REED_ADVANCE = "reed_advance"
    NEEDLE_SWAP = "needle_swap"
    TAKEUP = "takeup"


class FaultCode(str, Enum):
    GUIDE_TORQUE = "guide_torque_over_limit"
    RAPIER_POSITION = "rapier_not_in_position"
    REED_FORCE = "reed_force_over_limit"
    NEEDLE_POSITION = "needle_not_in_position"
    YARN_BREAK = "yarn_break"
    GUIDE_CHAIN_PHASE = "guide_chain_phase_mismatch"
    TAKEUP_SKEW = "takeup_skew"
    MISSING_HOOK = "missing_hook"
    EMERGENCY_STOP = "emergency_stop"


@dataclass(frozen=True)
class MechanismState:
    rapier_withdrawn: bool = True
    needles_safe: bool = True
    reed_down: bool = True
    reed_rear: bool = True
    rod2_rear_down: bool = True
    guide_locked: bool = True
    channels_clear: bool = True
    loops_captured: bool = False
    second_beat_complete: bool = False
    hook_sliders_withdrawn: bool = True


@dataclass(frozen=True)
class SensorConfirmations:
    guide_lock: bool = True
    chain_brake: bool = True
    guide_chain_aligned: bool = False
    left_hook_in_rail: bool = False
    right_hook_in_rail: bool = False
    clamp_locked: bool = False
    left_right_takeup_within_limit: bool = True


@dataclass(frozen=True)
class MachineState:
    lifecycle: Lifecycle = Lifecycle.THREADING
    cycle_index: int = 0
    absolute_takeup_x: float = 0.0
    left_hook_count: int = 0
    right_hook_count: int = 0
    guide_station_index: int = 0
    bias_supply_station_index: int = 0
    mechanisms: MechanismState = MechanismState()
    confirmations: SensorConfirmations = SensorConfirmations()
    latched_faults: frozenset[FaultCode] = frozenset()

    def __post_init__(self) -> None:
        if any(
            value < 0
            for value in (
                self.cycle_index,
                self.left_hook_count,
                self.right_hook_count,
                self.guide_station_index,
                self.bias_supply_station_index,
            )
        ):
            raise ValueError("cycle, hook, and station counts must not be negative")
        if not math.isfinite(self.absolute_takeup_x) or self.absolute_takeup_x < 0:
            raise ValueError("absolute_takeup_x must be finite and non-negative")


def action_blockers(state: MachineState, action: MachineAction) -> tuple[str, ...]:
    if not isinstance(action, MachineAction):
        raise TypeError("action must be a MachineAction")
    m = state.mechanisms
    c = state.confirmations
    blockers: list[str] = []
    if state.latched_faults:
        blockers.append("latched fault requires recovery")
    if action is MachineAction.GUIDE_INDEX:
        if not (
            m.rapier_withdrawn
            and m.needles_safe
            and m.reed_down
            and m.reed_rear
            and m.rod2_rear_down
        ):
            blockers.append("weaving intrusions are not withdrawn")
        if not (
            c.left_hook_in_rail and c.right_hook_in_rail and m.hook_sliders_withdrawn
        ):
            blockers.append(
                "both hooks must be in rail and insertion sliders withdrawn"
            )
    elif action is MachineAction.RAPIER_INSERT:
        if not (m.guide_locked and c.guide_lock and m.channels_clear):
            blockers.append("guide lock and three clear channels are required")
    elif action is MachineAction.REED_ADVANCE:
        if not (m.loops_captured and m.needles_safe and m.rapier_withdrawn):
            blockers.append(
                "captured loops, safe needles, and withdrawn rapiers are required"
            )
    elif action is MachineAction.NEEDLE_SWAP:
        if not (m.reed_down and m.rapier_withdrawn):
            blockers.append("needle swap requires reed down and rapiers withdrawn")
    else:
        if not (
            m.second_beat_complete
            and m.rapier_withdrawn
            and m.needles_safe
            and m.reed_down
            and m.reed_rear
            and m.rod2_rear_down
            and m.guide_locked
            and c.guide_lock
            and c.chain_brake
            and c.guide_chain_aligned
            and c.left_hook_in_rail
            and c.right_hook_in_rail
            and c.clamp_locked
            and c.left_right_takeup_within_limit
        ):
            blockers.append("take-up safety confirmations are incomplete")
    return tuple(blockers)


def require_action(state: MachineState, action: MachineAction) -> None:
    blockers = action_blockers(state, action)
    if blockers:
        raise ValueError(f"{action.value} blocked: " + "; ".join(blockers))


def complete_cycle(
    state: MachineState, *, takeup_step: float, topology_closed: bool
) -> MachineState:
    if not math.isfinite(takeup_step) or takeup_step <= 0:
        raise ValueError("takeup_step must be finite and positive")
    if not topology_closed:
        raise ValueError("cycle identity advancement requires closed guide topology")
    require_action(state, MachineAction.TAKEUP)
    return replace(
        state,
        lifecycle=Lifecycle.PRODUCTION,
        cycle_index=state.cycle_index + 1,
        absolute_takeup_x=state.absolute_takeup_x + takeup_step,
        left_hook_count=state.left_hook_count + 1,
        right_hook_count=state.right_hook_count + 1,
        guide_station_index=state.guide_station_index + 1,
        bias_supply_station_index=state.bias_supply_station_index + 1,
        mechanisms=replace(
            state.mechanisms, second_beat_complete=False, loops_captured=False
        ),
        confirmations=replace(
            state.confirmations,
            left_hook_in_rail=False,
            right_hook_in_rail=False,
            clamp_locked=False,
        ),
    )


def latch_fault(state: MachineState, fault: FaultCode) -> MachineState:
    return replace(
        state,
        lifecycle=Lifecycle.RECOVERY,
        latched_faults=state.latched_faults | {fault},
    )


def clear_faults(state: MachineState, *, reviewed_safe_exit: bool) -> MachineState:
    if state.lifecycle is not Lifecycle.RECOVERY or not reviewed_safe_exit:
        raise ValueError("faults may only be cleared after a reviewed recovery exit")
    return replace(state, latched_faults=frozenset(), lifecycle=Lifecycle.PRIMED)
