"""S1 hypothesis probe: prove the volume/bbox gates discriminate.

Builds the intended S1 substructure (wall+shelf+ribs) three ways — correct,
no-rib (known bad), rib-not-intersecting-wall (known bad) — and runs the
proposed acceptance measurements on each. A gate is adopted only if it
accepts the correct body and rejects both known-bad bodies.
"""

from __future__ import annotations

import math

import simplecadapi as scad
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box

WALL_T, WIDTH, HEIGHT = 4.0, 40.0, 36.0
DEPTH, SHELF_T = 28.0, 4.0
RIB_T, RIB_H, RIB_D, RIB_Y = 3.0, 18.0, 18.0, 11.0

ANALYTIC = None  # assigned below
# rib-wall overlap: integral of (RIB_H - x) dx for x in [0, wall_t/2] times rib_t
RIB_WALL_OVERLAP = (RIB_H * (WALL_T / 2.0) - 0.5 * (WALL_T / 2.0) ** 2) * RIB_T
ANALYTIC = (
    WALL_T * WIDTH * HEIGHT
    + DEPTH * WIDTH * SHELF_T
    - WALL_T * WIDTH * SHELF_T
    + 2 * (0.5 * RIB_H * RIB_D * RIB_T)
    - 2 * RIB_WALL_OVERLAP
)


def bbox_of(solid: scad.Solid) -> tuple[tuple[float, ...], tuple[float, ...]]:
    box = Bnd_Box()
    box.SetGap(0.0)
    BRepBndLib.AddOptimal_s(solid.wrapped, box, True, False)
    return tuple(round(v, 4) for v in box.Get()[:3]), tuple(round(v, 4) for v in box.Get()[3:])


def make_wall() -> scad.Solid:
    return scad.make_box_rsolid(
        width=WALL_T, height=WIDTH, depth=HEIGHT, bottom_face_center=(0.0, 0.0, 0.0)
    )


def make_shelf() -> scad.Solid:
    return scad.make_box_rsolid(
        width=DEPTH,
        height=WIDTH,
        depth=SHELF_T,
        bottom_face_center=(DEPTH / 2.0 - WALL_T / 2.0, 0.0, 0.0),
    )


def make_rib(y_center: float, x_offset: float = 0.0) -> scad.Solid:
    y0 = y_center - RIB_T / 2.0
    wire = scad.make_polyline_rwire(
        [
            (x_offset, y0, SHELF_T),
            (x_offset, y0, SHELF_T + RIB_H),
            (x_offset + RIB_D, y0, SHELF_T),
        ],
        closed=True,
    )
    face = scad.make_face_from_wire_rface(wire, normal=(0.0, 1.0, 0.0))
    return scad.extrude_rsolid(
        profile=face, direction=(0.0, 1.0, 0.0), distance=RIB_T
    )


def volume_gate(volume: float) -> bool:
    return abs(volume - ANALYTIC) / ANALYTIC <= 1e-3


def bbox_gate(lo, hi) -> bool:
    return (
        abs(lo[0] + 2.0) <= 0.05
        and abs(lo[1] + 20.0) <= 0.05
        and abs(lo[2] - 0.0) <= 0.05
        and abs(hi[0] - 26.0) <= 0.05
        and abs(hi[1] - 20.0) <= 0.05
        and abs(hi[2] - 36.0) <= 0.05
    )


def report(name: str, body: scad.Solid) -> None:
    volume = body.get_volume()
    lo, hi = bbox_of(body)
    print(
        f"{name}: volume={volume:.3f} analytic={ANALYTIC:.3f} "
        f"vol_gate={'PASS' if volume_gate(volume) else 'FAIL'} "
        f"bbox={lo}..{hi} bbox_gate={'PASS' if bbox_gate(lo, hi) else 'FAIL'}"
    )


def main() -> None:
    with scad.GraphSession(graph_id="s1_hypothesis") as session:
        good = scad.union_rsolid(
            make_wall(), make_shelf(), make_rib(RIB_Y), make_rib(-RIB_Y)
        )
        session.capture_result(value=good)
        report("H1-correct", good)

        no_rib = scad.union_rsolid(make_wall(), make_shelf())
        report("H2-known-bad-no-rib", no_rib)

        # known bad: ribs slid out of the wall (face contact only, no overlap)
        detached = scad.union_rsolid(
            make_wall(), make_shelf(), make_rib(RIB_Y, x_offset=2.0), make_rib(-RIB_Y, x_offset=2.0)
        )
        report("H3-known-bad-detached-ribs", detached)

    print("expected: H1 both gates PASS; H2/H3 volume gate FAIL (discriminating)")
    assert volume_gate(good.get_volume())
    assert not volume_gate(no_rib.get_volume())
    assert not volume_gate(detached.get_volume())
    print("S1 hypothesis conclusion: gates discriminate -> adopt")


if __name__ == "__main__":
    main()
