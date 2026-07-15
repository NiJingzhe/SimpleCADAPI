from __future__ import annotations

import importlib

import pytest


topology_module = importlib.import_module(
    "examples.21_weaving_machine.guide_index_topology"
)
poses_module = importlib.import_module("examples.21_weaving_machine.poses")
yarn_module = importlib.import_module("examples.21_weaving_machine.yarn_topology")


def test_unresolved_topology_blocks_functional_release():
    topology = topology_module.unresolved_guide_topology()

    assert topology.block_count is None
    with pytest.raises(ValueError, match="closed_with_evidence"):
        topology.require_functional_release()


def test_closed_occupancy_preserves_identity_and_requires_evidence():
    states = tuple(
        topology_module.GuideOccupancy(
            state_id=state_id,
            slots=(("upper-0", "g1"), ("lower-0", "g2"), ("receiver", None)),
        )
        for state_id in ("S0", "S1", "S2")
    )

    topology = topology_module.GuideIndexTopology(
        closure=topology_module.TopologyClosure.CLOSED_WITH_EVIDENCE,
        states=states,
        evidence_ref="mechanical-review:test",
    )

    assert topology.block_count == 2
    topology.require_functional_release()
    with pytest.raises(ValueError, match="evidence reference"):
        topology_module.GuideIndexTopology(
            closure=topology_module.TopologyClosure.CLOSED_WITH_EVIDENCE,
            states=states,
        )


def test_occupancy_rejects_duplicates_and_missing_receiving_location():
    with pytest.raises(ValueError, match="state_id"):
        topology_module.GuideOccupancy(state_id="", slots=())
    with pytest.raises(ValueError, match="duplicate slot"):
        topology_module.GuideOccupancy(
            state_id="S0",
            slots=(("slot", "g1"), ("slot", None)),
        )
    with pytest.raises(ValueError, match="empty slot"):
        topology_module.GuideOccupancy(
            state_id="S0",
            slots=(("", "g1"), ("receiver", None)),
        )
    with pytest.raises(ValueError, match="empty block"):
        topology_module.GuideOccupancy(
            state_id="S0",
            slots=(("upper", ""), ("receiver", None)),
        )
    with pytest.raises(ValueError, match="duplicate block"):
        topology_module.GuideOccupancy(
            state_id="S0",
            slots=(("upper", "g1"), ("lower", "g1"), ("receiver", None)),
        )


def test_closed_topology_rejects_bad_state_sets_and_identity_drift():
    valid_state = topology_module.GuideOccupancy(
        state_id="S0",
        slots=(("upper", "g1"), ("receiver", None)),
    )
    with pytest.raises(ValueError, match="ordered S0"):
        topology_module.GuideIndexTopology(
            closure=topology_module.TopologyClosure.CLOSED_WITH_EVIDENCE,
            states=(valid_state,),
            evidence_ref="test",
        )

    empty_states = tuple(
        topology_module.GuideOccupancy(
            state_id=state_id,
            slots=(("receiver", None),),
        )
        for state_id in ("S0", "S1", "S2")
    )
    with pytest.raises(ValueError, match="must contain"):
        topology_module.GuideIndexTopology(
            closure=topology_module.TopologyClosure.CLOSED_WITH_EVIDENCE,
            states=empty_states,
            evidence_ref="test",
        )

    drift_states = (
        valid_state,
        topology_module.GuideOccupancy("S1", (("upper", "g2"), ("receiver", None))),
        topology_module.GuideOccupancy("S2", (("upper", "g1"), ("receiver", None))),
    )
    with pytest.raises(ValueError, match="same block identities"):
        topology_module.GuideIndexTopology(
            closure=topology_module.TopologyClosure.CLOSED_WITH_EVIDENCE,
            states=drift_states,
            evidence_ref="test",
        )
    with pytest.raises(ValueError, match="only closed_with_evidence"):
        topology_module.GuideIndexTopology(
            closure=topology_module.TopologyClosure.ASSUMPTION_ONLY,
            evidence_ref="test",
        )


def test_phase_functions_reject_non_finite_values_and_incomplete_tables(monkeypatch):
    with pytest.raises(ValueError, match="finite"):
        topology_module.guide_phase_at(float("nan"))
    with pytest.raises(ValueError, match="finite"):
        poses_module.pose_at_main_phase(float("inf"))

    monkeypatch.setattr(poses_module, "MAIN_PHASE_SEGMENTS", ())
    with pytest.raises(RuntimeError, match="incomplete"):
        poses_module.pose_at_main_phase(0.0)
    with pytest.raises(ValueError, match="receiving location"):
        topology_module.GuideOccupancy(
            state_id="S0",
            slots=(("upper", "g1"), ("lower", "g2")),
        )


@pytest.mark.parametrize(
    ("angle", "expected"),
    (
        (0.0, topology_module.GuidePhase.UNLOCK),
        (30.0, topology_module.GuidePhase.CAPTURE),
        (90.0, topology_module.GuidePhase.TRANSLATE_AND_TRANSFER),
        (210.0, topology_module.GuidePhase.SEAT),
        (270.0, topology_module.GuidePhase.LOCK),
        (320.0, topology_module.GuidePhase.DWELL),
        (360.0, topology_module.GuidePhase.UNLOCK),
    ),
)
def test_local_guide_phase_boundaries(angle, expected):
    assert topology_module.guide_phase_at(angle) is expected


@pytest.mark.parametrize(
    ("angle", "pose"),
    (
        (0.0, poses_module.MachinePose.HOOK_INSERT),
        (20.0, poses_module.MachinePose.INDEX_S1),
        (70.0, poses_module.MachinePose.FILL_A_PICK),
        (150.0, poses_module.MachinePose.FILL_A_BEAT),
        (190.0, poses_module.MachinePose.NEEDLE_SWAP),
        (220.0, poses_module.MachinePose.FILL_B_PICK),
        (300.0, poses_module.MachinePose.FILL_B_BEAT),
        (335.0, poses_module.MachinePose.TAKEUP_END),
        (360.0, poses_module.MachinePose.HOOK_INSERT),
    ),
)
def test_main_phase_boundaries(angle, pose):
    assert poses_module.pose_at_main_phase(angle) is pose


def test_yarn_cycle_adds_two_hooks_and_six_channel_loops():
    initial = yarn_module.YarnTopologyState(
        yarn_ends=(
            yarn_module.YarnEnd(
                "bias-1",
                yarn_module.YarnFamily.BIAS_POSITIVE,
                "bobbin-1",
                guide_id="guide-1",
            ),
        )
    )

    first = yarn_module.advance_yarn_cycle(initial, takeup_step=12.0)
    second = yarn_module.advance_yarn_cycle(first, takeup_step=12.0)

    assert first.cycle_index == 1
    assert len(first.hooks) == 2
    assert len(first.filling_loops) == 6
    assert len(second.hooks) == 4
    assert len(second.filling_loops) == 12
    assert second.hooks[0].x_position == 24.0


def test_bias_yarn_identity_mapping_is_one_to_one():
    with pytest.raises(ValueError, match="one-to-one"):
        yarn_module.YarnTopologyState(
            yarn_ends=(
                yarn_module.YarnEnd(
                    "bias-1",
                    yarn_module.YarnFamily.BIAS_POSITIVE,
                    "bobbin-1",
                    guide_id="guide-1",
                ),
                yarn_module.YarnEnd(
                    "bias-2",
                    yarn_module.YarnFamily.BIAS_NEGATIVE,
                    "bobbin-2",
                    guide_id="guide-1",
                ),
            )
        )


def test_yarn_value_objects_and_cycle_reject_invalid_inputs():
    with pytest.raises(ValueError, match="must not be empty"):
        yarn_module.YarnEnd("", yarn_module.YarnFamily.WARP, "bobbin")
    with pytest.raises(ValueError, match="require one guide"):
        yarn_module.YarnEnd("bias", yarn_module.YarnFamily.BIAS_POSITIVE, "bobbin")
    with pytest.raises(ValueError, match="hook ID"):
        yarn_module.EdgeHook("", "left", 1, 0.0)
    with pytest.raises(ValueError, match="left or right"):
        yarn_module.EdgeHook("hook", "center", 1, 0.0)
    with pytest.raises(ValueError, match="cycle must be positive"):
        yarn_module.EdgeHook("hook", "left", 0, 0.0)
    with pytest.raises(ValueError, match="loop ID and cycle"):
        yarn_module.FillingLoop("", 1, "A", "top")
    with pytest.raises(ValueError, match="valid channel"):
        yarn_module.FillingLoop("loop", 1, "C", "top")
    with pytest.raises(ValueError, match="cycle_index"):
        yarn_module.YarnTopologyState(cycle_index=-1)
    with pytest.raises(ValueError, match="finite and positive"):
        yarn_module.advance_yarn_cycle(yarn_module.YarnTopologyState(), takeup_step=0.0)


@pytest.mark.parametrize(
    ("field_name", "values"),
    (
        (
            "yarn_ends",
            (
                yarn_module.YarnEnd("same", yarn_module.YarnFamily.WARP, "s1"),
                yarn_module.YarnEnd("same", yarn_module.YarnFamily.WARP, "s2"),
            ),
        ),
        (
            "hooks",
            (
                yarn_module.EdgeHook("same", "left", 1, 0.0),
                yarn_module.EdgeHook("same", "right", 1, 0.0),
            ),
        ),
        (
            "filling_loops",
            (
                yarn_module.FillingLoop("same", 1, "A", "top"),
                yarn_module.FillingLoop("same", 1, "B", "bottom"),
            ),
        ),
    ),
)
def test_yarn_state_rejects_duplicate_identity_by_category(field_name, values):
    with pytest.raises(ValueError, match="duplicate"):
        yarn_module.YarnTopologyState(**{field_name: values})


def test_bias_yarn_supply_identity_mapping_is_one_to_one():
    with pytest.raises(ValueError, match="one-to-one"):
        yarn_module.YarnTopologyState(
            yarn_ends=(
                yarn_module.YarnEnd(
                    "bias-1",
                    yarn_module.YarnFamily.BIAS_POSITIVE,
                    "bobbin-1",
                    guide_id="guide-1",
                ),
                yarn_module.YarnEnd(
                    "bias-2",
                    yarn_module.YarnFamily.BIAS_NEGATIVE,
                    "bobbin-1",
                    guide_id="guide-2",
                ),
            )
        )
