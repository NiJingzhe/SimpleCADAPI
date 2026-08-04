"""Snap-fit two-piece enclosure for the 7EP-CAPLCD display module.

Module constraints (measured from examples/out/invtest/7EP-CAPLCD-3D-Drawing.stp,
module datum: origin at screen center, +X right, +Y top, +Z front):
  - Module envelope          X [-52.1, 52.1]  Y [-85.09, 85.09]  Z [-10.03, 4.6]
  - Touch glass top          Z = 4.6 (full footprint)
  - LCD cell (7INCH-070II)   X [-49.88, 49.88]  Y [-83.54, 78.06]
  - PCB (HL2412 outline)     99.5 x 161, top Z = -2.12
  - Frame bottom face        Z = -2.4 (support datum)
  - Audio jack (SJ2-35894D)  mouth (X -33.3, Y 79.9, Z -6.2), faces +Y (top edge)
  - USB-C x2 (mouths +Y)     (-20.8, 49.5) and (-6.8, 49.5), mouth plane Y=53.4
  - 47151-0001 (right-angle  socket cavity at the +Y end (X 8.8..14.6,
    10-pin, mouth +Y)         Y 51.4..54.0, Z -5.3..-4.5), exits toward the
                             top edge; through-hole tails at Z -10.03
  - 3-pin PH2.0 connector    (-41.7, 24.2), RIGHT-ANGLE: socket faces -X,
                             plug/wires exit through the LEFT wall
  - 4-pin 1.25 x2 (exit -Z)  (-43.2, 57.3) and (-43.2, -41.0), to Z -8.51
  - Tact button (6x6x7)      (33.85, 71.76), plunger to Z -8.7
  - Speakers (SPK-2030x4)    20 x 55 at X [28.25, 48.25], Y [8.3, 63.3] and
                             Y [-68.7, -13.7], cones face -Z (grilles in rear)
  - 4 corner M2.5 standoffs  (+-45.75, +-73.75), Z -7.7..-2.2

Enclosure scheme (screw-mounted, no snap-fit):
  - Back tray: base panel Z -13.0..-10.5, walls to rim Z=0, outer X +-56.0,
    Y +-89.2 (2.5 wall). Screwed to the module's 8 threaded M2.5 standoffs
    (SMTSO-M2_5-4ET have an internal bore) with countersunk M2.5 screws, so
    the tray is fixed directly to the back of the display. Rear panel
    openings for connectors, button, speaker grilles; recessed interface
    bay on the top edge so the jack, USB-C and 47151 mouths sit at the
    bay/channel floors and plugs go straight in; recessed pocket on the
    left wall for the 3-pin.
  - Upper cover: bezel with LCD window (98.5 x 160, R5), skirt wraps the
    tray rim; fixed with 6 M2 countersunk side screws (wall bosses +
    skirt pockets).
  - Fasteners: 8x M2.5 countersunk (tray <-> module standoffs),
    6x M2 countersunk (cover <-> tray walls).
"""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad
from simplecadapi import ql

OUT_DIR = Path(__file__).resolve().parent / "out" / "7ep_caplcd_enclosure"

# --- module datums -----------------------------------------------------------
GLASS_Z = 4.6          # touch glass top
FRAME_BOTTOM_Z = -2.4  # display frame bottom (support datum)
PANEL_INNER_Z = -10.5  # tray panel inner face
PANEL_OUTER_Z = -13.0
RIM_Z = 0.0            # tray rim / parting line

TRAY_X = 56.0
TRAY_Y = 89.2
WALL_T = 2.5

COVER_X = 58.5
COVER_Y = 91.7
SKIRT_T = 2.4
COVER_TOP_INNER = 4.7
COVER_TOP = 6.6

WINDOW_X = 49.25
WINDOW_Y = 80.0


@scad.model(graph_id="caplcd_enclosure_7ep", export_dir=OUT_DIR)
def build_enclosure():
    @scad.requires_session
    def _build():
        tray = _build_tray()
        tray = scad.apply_tag(shape=tray, tag="role.enclosure.tray")
        scad.capture_result(value=(tray,))

        # incremental grounding
        print("tray volume", round(tray.get_volume(), 1))
        print("tray faces", len(ql.faces().resolve(tray)))
        print("tags", scad.list_tags(shape=tray))
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        scad.export_step(shapes=tray, filename=str(OUT_DIR / "back_panel.step"))
        return tray

    return _build()


def _box(width, height, depth, bottom_face_center, **kwargs):
    return scad.make_box_rsolid(
        width=width,
        height=height,
        depth=depth,
        bottom_face_center=bottom_face_center,
        **kwargs,
    )


def _cyl(radius, height, bottom_face_center, **kwargs):
    return scad.make_cylinder_rsolid(
        radius=radius,
        height=height,
        bottom_face_center=bottom_face_center,
        **kwargs,
    )


def _build_tray():
    parts = []
    # base panel
    parts.append(
        _box(2 * TRAY_X, 2 * TRAY_Y, 2.5, (0, 0, PANEL_OUTER_Z))
    )
    # walls to the glass plane (rim at Z 4.4, glass top at 4.6): the module
    # frame is the finished front face, the walls are the side guard rim
    WALL_H = 4.4 - PANEL_INNER_Z
    for sx in (-1, 1):
        parts.append(_box(WALL_T, 2 * TRAY_Y, WALL_H, (sx * (TRAY_X - WALL_T / 2), 0, PANEL_INNER_Z)))
    for sy in (-1, 1):
        parts.append(_box(2 * TRAY_X, WALL_T, WALL_H, (0, sy * (TRAY_Y - WALL_T / 2), PANEL_INNER_Z)))

    # support pads under the module's 8 M2.5 standoff feet (Z -7.7). The
    # frame bottom face (-2.4) is not loadable: the PCB (Z -3.7..-2.12, 99.5 x
    # 161) hangs below it over nearly the full footprint, and the corner
    # standoffs hang to Z -7.7. The standoffs are the module's own feet.
    pad_top = -7.7
    pad_h = pad_top - PANEL_INNER_Z
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(_cyl(2.75, pad_h, (sx * 45.75, sy * 73.75, PANEL_INNER_Z)))
    for sx in (-1, 1):
        parts.append(_cyl(2.75, pad_h, (sx * 18.0, 36.26, PANEL_INNER_Z)))
        parts.append(_cyl(2.75, pad_h, (sx * 18.0, -21.74, PANEL_INNER_Z)))

    # centering ribs on the inner wall faces, Z -2.9..0.6
    rib_h = 0.6 - (-2.9)
    for ry in (-55, -20, 20, 55):
        for sx in (-1, 1):
            parts.append(_box(1.0, 10.0, rib_h, (sx * 53.0, ry, -2.9)))
    for rx in (-50, -20, 20, 50):
        for sy in (-1, 1):
            parts.append(_box(10.0, 1.0, rib_h, (rx, sy * 86.2, -2.9)))

    # --- connector-side (USB-C x2 + 47151 + jack) CONCAVE CONTOUR ---
    # The tray's plan outline steps INWARD here: the wall in X -38.6..+24.2
    # is recessed from Y 89.2 to Y 82.7 (lower band Z -10.5..-2.5), forming
    # the concave polyline that follows the PCB's own top-edge notch. The
    # jack mouth (79.9) sits 0.3 mm behind the recessed wall's inner face;
    # USB-C / 47151 mouths (53.4 / 54.0) are reached through the open space
    # below the PCB. Raised shelves align the plug axes with the mouths.
    parts.append(_box(62.8, 2.5, 8.0, (-7.2, 81.45, -10.5)))   # recessed wall Y 80.2..82.7, Z -10.5..-2.5
    parts.append(_box(32.3, 28.6, 2.2, (-12.15, 65.9, -10.5)))  # USB shelf X -28.3..4.0, Y 51.6..80.2, Z -10.5..-8.3
    parts.append(_box(20.2, 26.2, 2.2, (14.1, 67.1, -10.5)))    # 47151 shelf X 4.0..24.2, Y 54.0..80.2, Z -10.5..-8.3
    # left side: the 3-pin socket faces -X at X -45.4; the wall is opened
    # at the socket band (Y 18.76..29.56) forming an open bay for the plug.

    # upper centering ribs on the wall inner faces (frame band Z 0.8..4.3)
    rib_h2 = 4.3 - 0.8
    for ry in (-55, -20, 20, 55):
        for sx in (-1, 1):
            parts.append(_box(1.0, 10.0, rib_h2, (sx * 53.0, ry, 0.8)))
    for rx in (-50, -20, 20, 50):
        for sy in (-1, 1):
            parts.append(_box(10.0, 1.0, rib_h2, (rx, sy * 86.2, 0.8)))

    tray = scad.union_rsolid(parts)

    # --- rear panel openings (cut through the base panel, Z -13..-9) ---
    tools = []
    PANEL_CUT = 4.0
    # remove the original wall's lower band at the connector side (the recess
    # void) and open the access holes through the recessed wall at the mouths
    tools.append(_box(62.8, 3.5, 8.0, (-7.2, TRAY_Y - WALL_T / 2, -10.5)))  # void Y 86.2..89.7, Z -10.5..-2.5
    tools.append(_box(9.2, 3.1, 5.0, (-33.3, 81.45, -8.4)))    # jack mouth hole
    tools.append(_box(10.0, 3.1, 5.0, (-20.8, 81.45, -7.8)))   # usb1 hole
    tools.append(_box(10.0, 3.1, 5.0, (-6.8, 81.45, -7.8)))    # usb2 hole
    tools.append(_box(10.0, 3.1, 2.2, (12.5, 81.45, -6.0)))    # 47151 hole
    # left notch: open the left wall at the 3-pin socket band
    tools.append(_box(3.0, 10.8, 6.4, (-(TRAY_X - WALL_T / 2), 24.16, -10.3)))  # Y 18.76..29.56, Z -10.3..-3.9
    # M2.5 countersunk mounting holes -> the module's 8 threaded standoffs
    for sx in (-1, 1):
        for sy in (-1, 1):
            tools.append(_cyl(1.4, 6.0, (sx * 45.75, sy * 73.75, -13.5)))   # through pad+base
        tools.append(_cyl(1.4, 6.0, (sx * 18.0, 36.26, -13.5)))
        tools.append(_cyl(1.4, 6.0, (sx * 18.0, -21.74, -13.5)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            tools.append(_cyl(2.6, 1.5, (sx * 45.75, sy * 73.75, -13.2)))   # 90-deg countersink
        tools.append(_cyl(2.6, 1.5, (sx * 18.0, 36.26, -13.2)))
        tools.append(_cyl(2.6, 1.5, (sx * 18.0, -21.74, -13.2)))
    # 3-pin notch is cut above (left wall, open bay); 4-pin 1.25 x2 (vertical,
    # wires exit -Z through the rear panel)
    tools.append(_box(5.8, 11.4, PANEL_CUT, (-43.16, 57.26, PANEL_OUTER_Z)))
    tools.append(_box(5.8, 11.4, PANEL_CUT, (-43.16, -40.98, PANEL_OUTER_Z)))
    # tact button
    tools.append(_box(6.0, 6.0, PANEL_CUT, (33.85, 71.76, PANEL_OUTER_Z)))
    # speaker grilles: 2 zones x 12 slots (18 x 1.6, pitch 4.4)
    for zone_center_y in (35.75, -41.24):
        for k in range(-5, 7):
            tools.append(
                _box(18.0, 1.6, PANEL_CUT, (37.7, zone_center_y + 4.4 * (k - 0.5), PANEL_OUTER_Z))
            )
    # MCU cooling vents
    for vx, vy in ((-14.0, 6.5), (-9.5, 6.5), (-14.0, 10.5), (-9.5, 10.5)):
        tools.append(_cyl(1.25, PANEL_CUT, (vx, vy, PANEL_OUTER_Z)))
    # jack / USB-C / 47151 access is the open top notch (no through-holes)

    tray = scad.cut_rsolid(tray, tools)

    # corner rounding R6
    corners = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            corners.append(_cyl(6.0, 30.0, (sx * TRAY_X, sy * TRAY_Y, -15.0)))
    tray = scad.cut_rsolid(tray, corners)
    return tray


if __name__ == "__main__":
    result = build_enclosure()
    tray = result.value
    print("replay count", len(result.replay()))
    print("tray volume", round(tray.get_volume(), 1))
