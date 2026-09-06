from __future__ import annotations

import math
import random

from simplecadapi.artifacts.canonical import content_hash
from simplecadapi.artifacts.references import ConnectorInterface, PartInstance
from simplecadapi.product.placement import (
    canonical_frame,
    placement_from_canonical,
    placement_ticks,
)


def _euler_frame(a: float, b: float, c: float) -> dict[str, list[float]]:
    ca, sa = math.cos(a), math.sin(a)
    cb, sb = math.cos(b), math.sin(b)
    cc, sc = math.cos(c), math.sin(c)
    return {
        "origin": [41.7193000900063, -14.849242404917511, 0.0],
        "x_axis": [ca * cb, sa * cb, -sb],
        "y_axis": [ca * sb * sc - sa * cc, sa * sb * sc + ca * cc, cb * sc],
    }


def test_tick_frames_survive_reconstruct_and_re_tick() -> None:
    randomizer = random.Random(20260906)

    for _ in range(500):
        raw = _euler_frame(*(randomizer.uniform(-math.pi, math.pi) for _ in range(3)))
        ticks = placement_ticks(raw)
        rebuilt = placement_from_canonical(ticks)

        assert placement_ticks(rebuilt) == ticks
        assert rebuilt.to_dict() == {
            key: [value * 1e-9 for value in ticks[key]] for key in ticks
        }


def test_part_instance_round_trip_is_byte_stable() -> None:
    instance = PartInstance("wheel", "wheel-definition", None, _euler_frame(0.73, -1.21, 2.34))
    restored = PartInstance.from_dict(instance.to_dict())

    assert restored.to_dict() == instance.to_dict()
    assert content_hash(restored.to_dict()) == content_hash(instance.to_dict())


def test_connector_round_trip_is_byte_stable() -> None:
    frame = _euler_frame(-0.4, 0.9, 1.7)
    connector = ConnectorInterface("axis", None, "placement", frame, None)
    restored = ConnectorInterface.from_dict(connector.to_dict())

    assert restored.to_dict() == connector.to_dict()
    assert content_hash(restored.to_dict()) == content_hash(connector.to_dict())


def test_legacy_float_frames_upgrade_to_ticks() -> None:
    raw = _euler_frame(0.7, 1.1, -0.4)
    ticks = placement_ticks(raw)
    instance = PartInstance("wheel", "wheel-definition", None, raw)

    assert instance.placement == ticks
    assert canonical_frame(instance.placement) == ticks
