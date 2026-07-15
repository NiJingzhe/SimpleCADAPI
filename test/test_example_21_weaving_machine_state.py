from __future__ import annotations

import importlib
from dataclasses import replace

import pytest


state_module = importlib.import_module("examples.21_weaving_machine.machine_state")


def _takeup_ready_state():
    return state_module.MachineState(
        lifecycle=state_module.Lifecycle.FIRST_CYCLE,
        mechanisms=state_module.MechanismState(
            second_beat_complete=True,
            loops_captured=True,
        ),
        confirmations=state_module.SensorConfirmations(
            guide_lock=True,
            chain_brake=True,
            guide_chain_aligned=True,
            left_hook_in_rail=True,
            right_hook_in_rail=True,
            clamp_locked=True,
            left_right_takeup_within_limit=True,
        ),
    )


def test_cycle_state_is_cumulative_and_requires_topology_closure():
    state = _takeup_ready_state()

    with pytest.raises(ValueError, match="closed guide topology"):
        state_module.complete_cycle(state, takeup_step=12.0, topology_closed=False)

    complete = state_module.complete_cycle(
        state, takeup_step=12.0, topology_closed=True
    )

    assert complete.cycle_index == 1
    assert complete.absolute_takeup_x == 12.0
    assert complete.left_hook_count == complete.right_hook_count == 1
    assert complete.guide_station_index == complete.bias_supply_station_index == 1
    assert complete.lifecycle is state_module.Lifecycle.PRODUCTION


def test_take_up_and_guide_index_require_confirmations():
    state = state_module.MachineState()

    assert state_module.action_blockers(state, state_module.MachineAction.TAKEUP)
    assert state_module.action_blockers(state, state_module.MachineAction.GUIDE_INDEX)
    with pytest.raises(ValueError, match="take-up safety"):
        state_module.require_action(state, state_module.MachineAction.TAKEUP)
    with pytest.raises(TypeError, match="MachineAction"):
        state_module.action_blockers(state, "takeup")


def test_each_action_exposes_its_specific_interlock_and_success_path():
    ready = _takeup_ready_state()
    state_module.require_action(ready, state_module.MachineAction.TAKEUP)

    guide_ready = replace(
        ready,
        mechanisms=replace(
            ready.mechanisms,
            second_beat_complete=False,
            loops_captured=False,
        ),
    )
    state_module.require_action(guide_ready, state_module.MachineAction.GUIDE_INDEX)
    state_module.require_action(guide_ready, state_module.MachineAction.RAPIER_INSERT)
    state_module.require_action(guide_ready, state_module.MachineAction.NEEDLE_SWAP)

    reed_ready = replace(
        guide_ready,
        mechanisms=replace(guide_ready.mechanisms, loops_captured=True),
    )
    state_module.require_action(reed_ready, state_module.MachineAction.REED_ADVANCE)

    cases = (
        (
            state_module.MachineAction.GUIDE_INDEX,
            replace(
                guide_ready,
                mechanisms=replace(guide_ready.mechanisms, rapier_withdrawn=False),
            ),
            "intrusions",
        ),
        (
            state_module.MachineAction.RAPIER_INSERT,
            replace(
                guide_ready,
                mechanisms=replace(guide_ready.mechanisms, channels_clear=False),
            ),
            "three clear channels",
        ),
        (
            state_module.MachineAction.REED_ADVANCE,
            guide_ready,
            "captured loops",
        ),
        (
            state_module.MachineAction.NEEDLE_SWAP,
            replace(
                guide_ready, mechanisms=replace(guide_ready.mechanisms, reed_down=False)
            ),
            "reed down",
        ),
    )
    for action, state, message in cases:
        with pytest.raises(ValueError, match=message):
            state_module.require_action(state, action)


def test_machine_state_and_cycle_validate_numeric_boundaries():
    with pytest.raises(ValueError, match="counts"):
        state_module.MachineState(guide_station_index=-1)
    with pytest.raises(ValueError, match="absolute_takeup_x"):
        state_module.MachineState(absolute_takeup_x=float("nan"))
    with pytest.raises(ValueError, match="finite and positive"):
        state_module.complete_cycle(
            _takeup_ready_state(), takeup_step=0.0, topology_closed=True
        )


def test_faults_latch_and_only_reviewed_recovery_clears_them():
    state = state_module.latch_fault(
        state_module.MachineState(),
        state_module.FaultCode.EMERGENCY_STOP,
    )

    assert state.lifecycle is state_module.Lifecycle.RECOVERY
    assert state_module.FaultCode.EMERGENCY_STOP in state.latched_faults
    assert state_module.action_blockers(state, state_module.MachineAction.RAPIER_INSERT)
    with pytest.raises(ValueError, match="reviewed recovery"):
        state_module.clear_faults(state, reviewed_safe_exit=False)

    cleared = state_module.clear_faults(state, reviewed_safe_exit=True)
    assert not cleared.latched_faults
    assert cleared.lifecycle is state_module.Lifecycle.PRIMED
