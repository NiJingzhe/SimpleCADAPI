"""Parameterized threaded fasteners built from replayable public APIs."""

from __future__ import annotations

import math
from typing import Collection, List, Optional, Sequence, Tuple, cast

from ..core import Edge, Solid
from ..expr import ScalarLike
from ..graph import suspend_graph_recording
from ..operations import (
    apply_tag,
    cut_rsolid,
    extrude_rsolid,
    fillet_rsolid,
    intersect_rsolid,
    make_box_rsolid,
    make_cone_rsolid,
    make_cylinder_rsolid,
    make_face_from_wire_rface,
    make_helix_rwire,
    make_polyline_rwire,
    revolve_rsolid,
    rotate_shape,
    sweep_rsolid,
    union_rsolid,
)
from ..tracking import graph_tracking_scope

__all__ = ["make_bolt_rsolid", "make_nut_rsolid"]


_BOLT_HEAD_STYLES = {"hex", "square", "cylindrical", "button", "countersunk"}
_DRIVE_STYLES = {"none", "slot", "cross", "hex_socket"}
_THREAD_STYLES = {"auto", "none", "full", "partial"}
_THREAD_DETAILS = {"cosmetic", "modeled"}
_THREAD_FORMS = {"v", "trapezoidal"}
_NUT_STYLES = {"hex", "square", "round", "knurled"}
_HOLE_STYLES = {"through", "blind"}
_THREAD_PHASE_CANDIDATES = (
    0.0,
    15.0,
    30.0,
    45.0,
    60.0,
    90.0,
    120.0,
    135.0,
    150.0,
    165.0,
    180.0,
    210.0,
    240.0,
    270.0,
    300.0,
    330.0,
)

# ISO metric coarse-pitch series used when callers provide a catalog nominal
# diameter without an explicit pitch.
_METRIC_COARSE_PITCH = {
    1.0: 0.25,
    1.2: 0.25,
    1.4: 0.30,
    1.6: 0.35,
    1.8: 0.35,
    2.0: 0.40,
    2.5: 0.45,
    3.0: 0.50,
    3.5: 0.60,
    4.0: 0.70,
    5.0: 0.80,
    6.0: 1.00,
    7.0: 1.00,
    8.0: 1.25,
    10.0: 1.50,
    12.0: 1.75,
    14.0: 2.00,
    16.0: 2.00,
    18.0: 2.50,
    20.0: 2.50,
    22.0: 2.50,
    24.0: 3.00,
    27.0: 3.00,
    30.0: 3.50,
    33.0: 3.50,
    36.0: 4.00,
    39.0: 4.00,
    42.0: 4.50,
    45.0: 4.50,
    48.0: 5.00,
    52.0: 5.00,
    56.0: 5.50,
    60.0: 5.50,
    64.0: 6.00,
}

# Common ISO 4014/4017 hex-head dimensions: nominal diameter -> (s, k).
_METRIC_HEX_HEAD_DIMENSIONS = {
    3.0: (5.5, 2.0),
    4.0: (7.0, 2.8),
    5.0: (8.0, 3.5),
    6.0: (10.0, 4.0),
    8.0: (13.0, 5.3),
    10.0: (16.0, 6.4),
    12.0: (18.0, 7.5),
    14.0: (21.0, 8.8),
    16.0: (24.0, 10.0),
    18.0: (27.0, 11.5),
    20.0: (30.0, 12.5),
    22.0: (34.0, 14.0),
    24.0: (36.0, 15.0),
    27.0: (41.0, 17.0),
    30.0: (46.0, 18.7),
    33.0: (50.0, 21.0),
    36.0: (55.0, 22.5),
}


def _positive_finite(name: str, value: float) -> float:
    resolved = float(value)
    if not math.isfinite(resolved) or resolved <= 0.0:
        raise ValueError(f"{name} must be positive and finite")
    return resolved


def _optional_positive(name: str, value: Optional[float], default: float) -> float:
    return _positive_finite(name, default if value is None else value)


def _non_negative_finite(name: str, value: float) -> float:
    resolved = float(value)
    if not math.isfinite(resolved) or resolved < 0.0:
        raise ValueError(f"{name} must be non-negative and finite")
    return resolved


def _choice(name: str, value: str, choices: Collection[str]) -> str:
    resolved = str(value).lower()
    if resolved not in choices:
        options = ", ".join(sorted(choices))
        raise ValueError(f"{name} must be one of: {options}")
    return resolved


def _catalog_value(
    table: Collection[float],
    nominal_diameter: float,
) -> Optional[float]:
    return next(
        (
            candidate
            for candidate in table
            if math.isclose(candidate, nominal_diameter, rel_tol=0.0, abs_tol=1e-9)
        ),
        None,
    )


def _resolve_thread_pitch(
    diameter: float,
    thread_pitch: Optional[float],
) -> Tuple[float, str]:
    if thread_pitch is not None:
        return _positive_finite("thread_pitch", thread_pitch), "explicit"
    nominal = _catalog_value(_METRIC_COARSE_PITCH.keys(), diameter)
    if nominal is None:
        raise ValueError(
            "thread_pitch is required when diameter is outside the metric coarse series"
        )
    return _METRIC_COARSE_PITCH[nominal], "metric_coarse"


def _metric_thread_dimensions(diameter: float, pitch: float) -> Tuple[float, float]:
    pitch_diameter = diameter - 0.6495 * pitch
    minor_diameter = diameter - 1.0825 * pitch
    if minor_diameter <= 0.0:
        raise ValueError(
            "diameter and thread_pitch produce a non-positive minor diameter"
        )
    return pitch_diameter, minor_diameter


def _standard_partial_thread_length(diameter: float, length: float) -> float:
    if length <= 125.0:
        return 2.0 * diameter + 6.0
    if length <= 200.0:
        return 2.0 * diameter + 12.0
    return 2.0 * diameter + 25.0


def _regular_polygon_points(
    sides: int,
    circumradius: float,
    z: float,
    phase: float,
) -> List[Tuple[ScalarLike, ScalarLike, ScalarLike]]:
    return [
        (
            circumradius * math.cos(phase + 2.0 * math.pi * index / sides),
            circumradius * math.sin(phase + 2.0 * math.pi * index / sides),
            z,
        )
        for index in range(sides)
    ]


def _make_prism(
    points: Sequence[Tuple[ScalarLike, ScalarLike, ScalarLike]],
    height: float,
) -> Solid:
    wire = make_polyline_rwire(points=list(points), closed=True)
    face = make_face_from_wire_rface(wire=wire, normal=(0.0, 0.0, 1.0))
    return extrude_rsolid(
        profile=face,
        direction=(0.0, 0.0, 1.0),
        distance=height,
    )


def _make_across_flats_prism(
    sides: int, width: float, z: float, height: float
) -> Solid:
    radius = width / (2.0 * math.cos(math.pi / sides))
    points = _regular_polygon_points(
        sides=sides,
        circumradius=radius,
        z=z,
        phase=math.pi / sides,
    )
    return _make_prism(points=points, height=height)


def _thread_profile_points(
    *,
    inner_radius: float,
    outer_radius: float,
    pitch: float,
    z: float,
    thread_form: str,
) -> List[Tuple[ScalarLike, ScalarLike, ScalarLike]]:
    if thread_form == "v":
        flank_run = (outer_radius - inner_radius) / math.sqrt(3.0)
        crest_flat = pitch / 8.0
        root_flat = pitch - crest_flat - 2.0 * flank_run
        if root_flat <= 0.0:
            raise ValueError(
                "thread_depth is too large for a truncated 60-degree V profile"
            )
        return [
            (outer_radius, 0.0, z + crest_flat / 2.0),
            (inner_radius, 0.0, z + crest_flat / 2.0 + flank_run),
            (
                inner_radius,
                0.0,
                z + crest_flat / 2.0 + flank_run + root_flat,
            ),
            (outer_radius, 0.0, z + pitch - crest_flat / 2.0),
        ]
    return [
        (outer_radius, 0.0, z),
        (inner_radius, 0.0, z + pitch * 0.35),
        (inner_radius, 0.0, z + pitch * 0.65),
        (outer_radius, 0.0, z + pitch),
    ]


def _make_thread_cutter(
    *,
    inner_radius: float,
    outer_radius: float,
    pitch: float,
    start_z: float,
    length: float,
    thread_form: str,
) -> Solid:
    overrun_start = start_z - pitch
    profile = make_polyline_rwire(
        points=_thread_profile_points(
            inner_radius=inner_radius,
            outer_radius=outer_radius,
            pitch=pitch,
            z=overrun_start,
            thread_form=thread_form,
        ),
        closed=True,
    )
    profile_face = make_face_from_wire_rface(
        wire=profile,
        normal=(0.0, 1.0, 0.0),
    )
    helix = make_helix_rwire(
        pitch=pitch,
        height=length + 2.0 * pitch,
        radius=outer_radius,
        center=(0.0, 0.0, overrun_start),
        dir=(0.0, 0.0, 1.0),
    )
    swept = sweep_rsolid(profile=profile_face, path=helix, is_frenet=True)
    clip = make_cylinder_rsolid(
        radius=outer_radius + max(1e-6, pitch * 0.01),
        height=length,
        bottom_face_center=(0.0, 0.0, start_z),
        axis=(0.0, 0.0, 1.0),
    )
    return intersect_rsolid(swept, clip)


def _rotate_thread_cutter(cutter: Solid, angle_degrees: float) -> Solid:
    if angle_degrees == 0.0:
        return cutter
    return cast(
        Solid,
        rotate_shape(
            shape=cutter,
            angle=angle_degrees,
            axis=(0.0, 0.0, 1.0),
            origin=(0.0, 0.0, 0.0),
        ),
    )


def _select_external_thread_phase(
    *,
    shank: Solid,
    cutter: Solid,
    minimum_volume: float,
) -> float:
    maximum_volume = shank.get_volume()
    volume_tolerance = max(1e-8, maximum_volume * 1e-8)
    with suspend_graph_recording():
        for angle_degrees in _THREAD_PHASE_CANDIDATES:
            candidate = _rotate_thread_cutter(cutter, angle_degrees)
            try:
                result = cut_rsolid(
                    shank,
                    candidate,
                    skip_non_intersecting=False,
                )
            except Exception:
                continue
            volume = result.get_volume()
            if minimum_volume * 0.98 < volume < maximum_volume - volume_tolerance:
                return angle_degrees
    raise ValueError("modeled external thread is unstable for these dimensions")


def _select_internal_thread_phase(
    *,
    opened_nut: Solid,
    body: Solid,
    ridge: Solid,
) -> float:
    minimum_volume = opened_nut.get_volume()
    maximum_volume = body.get_volume()
    volume_tolerance = max(1e-8, maximum_volume * 1e-8)
    with suspend_graph_recording():
        for angle_degrees in _THREAD_PHASE_CANDIDATES:
            candidate = _rotate_thread_cutter(ridge, angle_degrees)
            try:
                result = union_rsolid(opened_nut, candidate, glue=False)
            except Exception:
                continue
            volume = result.get_volume()
            if (
                minimum_volume + volume_tolerance
                < volume
                < maximum_volume - volume_tolerance
            ):
                return angle_degrees
    raise ValueError("modeled internal thread is unstable for these dimensions")


def _default_head_dimensions(diameter: float, head_style: str) -> Tuple[float, float]:
    if head_style == "hex":
        nominal = _catalog_value(_METRIC_HEX_HEAD_DIMENSIONS.keys(), diameter)
        if nominal is not None:
            return _METRIC_HEX_HEAD_DIMENSIONS[nominal]
    factors = {
        "hex": (1.6, 0.65),
        "square": (1.5, 0.70),
        "cylindrical": (1.5, 1.0),
        "button": (1.8, 0.55),
        "countersunk": (2.0, 0.60),
    }
    width_factor, height_factor = factors[head_style]
    return diameter * width_factor, diameter * height_factor


def _underhead_edge(solid: Solid, shank_radius: float) -> Edge:
    circumference = 2.0 * math.pi * shank_radius
    edges = cast(List[Edge], solid.get_edges())
    candidates = [
        edge
        for edge in edges
        if abs(edge.get_center().z) <= max(1e-7, shank_radius * 1e-5)
        and abs(edge.get_length() - circumference) <= circumference * 0.05
    ]
    if len(candidates) != 1:
        raise ValueError("could not identify one circular underhead transition edge")
    return candidates[0]


def _make_bolt_head(
    head_style: str, width: float, height: float, shank_radius: float
) -> Solid:
    if head_style == "hex":
        return _make_across_flats_prism(
            sides=6,
            width=width,
            z=-height,
            height=height,
        )
    if head_style == "square":
        return make_box_rsolid(
            width=width,
            height=width,
            depth=height,
            bottom_face_center=(0.0, 0.0, -height),
        )
    if head_style == "cylindrical":
        return make_cylinder_rsolid(
            radius=width / 2.0,
            height=height,
            bottom_face_center=(0.0, 0.0, -height),
            axis=(0.0, 0.0, 1.0),
        )
    if head_style == "countersunk":
        return make_cone_rsolid(
            bottom_radius=width / 2.0,
            top_radius=shank_radius,
            height=height,
            bottom_face_center=(0.0, 0.0, -height),
            axis=(0.0, 0.0, 1.0),
        )

    radius = width / 2.0
    profile = make_polyline_rwire(
        points=[
            (0.0, 0.0, -height),
            (radius * 0.42, 0.0, -height),
            (radius * 0.82, 0.0, -height * 0.62),
            (radius, 0.0, -height * 0.22),
            (radius, 0.0, 0.0),
            (0.0, 0.0, 0.0),
        ],
        closed=True,
    )
    face = make_face_from_wire_rface(wire=profile, normal=(0.0, -1.0, 0.0))
    return revolve_rsolid(
        profile=face,
        axis=(0.0, 0.0, 1.0),
        angle=360.0,
        origin=(0.0, 0.0, 0.0),
    )


def _drive_cutters(
    *,
    drive_style: str,
    drive_size: float,
    drive_depth: float,
    head_height: float,
) -> List[Solid]:
    if drive_style == "none":
        return []
    epsilon = max(1e-5, head_height * 1e-4)
    cutter_z = -head_height - epsilon
    cutter_height = drive_depth + epsilon
    slot_width = max(drive_size * 0.22, epsilon * 10.0)
    if drive_style == "slot":
        return [
            make_box_rsolid(
                width=drive_size,
                height=slot_width,
                depth=cutter_height,
                bottom_face_center=(0.0, 0.0, cutter_z),
            )
        ]
    if drive_style == "cross":
        return [
            make_box_rsolid(
                width=drive_size,
                height=slot_width,
                depth=cutter_height,
                bottom_face_center=(0.0, 0.0, cutter_z),
            ),
            make_box_rsolid(
                width=slot_width,
                height=drive_size,
                depth=cutter_height,
                bottom_face_center=(0.0, 0.0, cutter_z),
            ),
        ]
    points = _regular_polygon_points(
        sides=6,
        circumradius=drive_size / 2.0,
        z=cutter_z,
        phase=math.pi / 6.0,
    )
    return [_make_prism(points=points, height=cutter_height)]


@graph_tracking_scope
def make_bolt_rsolid(
    diameter: float,
    length: float,
    head_style: str = "hex",
    thread_style: str = "auto",
    thread_detail: str = "modeled",
    thread_form: str = "v",
    thread_pitch: Optional[float] = None,
    thread_depth: Optional[float] = None,
    thread_length: Optional[float] = None,
    head_width: Optional[float] = None,
    head_height: Optional[float] = None,
    drive_style: str = "none",
    drive_size: Optional[float] = None,
    drive_depth: Optional[float] = None,
    underhead_fillet_radius: Optional[float] = None,
) -> Solid:
    """Create a bolt along +Z with its head underside on the Z=0 plane.

    ``head_style`` accepts ``hex``, ``square``, ``cylindrical``, ``button``,
    and ``countersunk``. ``thread_style`` accepts ``auto``, ``full``,
    ``partial``, and ``none``. Auto uses full thread through 3d length and the
    standard piecewise partial-thread length above 3d. Cosmetic threads retain
    a smooth major-diameter shank and record thread intent in metadata; modeled
    threads cut a replayable helical groove.
    """
    resolved_diameter = _positive_finite("diameter", diameter)
    resolved_length = _positive_finite("length", length)
    resolved_head_style = _choice("head_style", head_style, _BOLT_HEAD_STYLES)
    requested_thread_style = _choice("thread_style", thread_style, _THREAD_STYLES)
    resolved_thread_style = requested_thread_style
    if requested_thread_style == "auto":
        if thread_length is not None:
            raise ValueError("thread_length requires thread_style='partial'")
        resolved_thread_style = (
            "full" if resolved_length <= 3.0 * resolved_diameter else "partial"
        )
    resolved_thread_detail = _choice("thread_detail", thread_detail, _THREAD_DETAILS)
    resolved_thread_form = _choice("thread_form", thread_form, _THREAD_FORMS)
    resolved_drive_style = _choice("drive_style", drive_style, _DRIVE_STYLES)

    default_width, default_height = _default_head_dimensions(
        resolved_diameter,
        resolved_head_style,
    )
    resolved_head_width = _optional_positive("head_width", head_width, default_width)
    resolved_head_height = _optional_positive(
        "head_height", head_height, default_height
    )
    if resolved_head_width <= resolved_diameter:
        raise ValueError("head_width must be greater than diameter")
    head_across_corners = (
        resolved_head_width / math.cos(math.pi / 6.0)
        if resolved_head_style == "hex"
        else None
    )

    if resolved_thread_style == "none" and thread_pitch is None:
        pitch = 0.0
        pitch_source = "not_applicable"
        pitch_diameter = resolved_diameter
        basic_minor_diameter = resolved_diameter
    else:
        pitch, pitch_source = _resolve_thread_pitch(resolved_diameter, thread_pitch)
        pitch_diameter, basic_minor_diameter = _metric_thread_dimensions(
            resolved_diameter,
            pitch,
        )
    default_depth = (
        (resolved_diameter - basic_minor_diameter) / 2.0
        if resolved_thread_form == "v" and pitch > 0.0
        else pitch * 0.5
    )
    depth = (
        _positive_finite("thread_depth", thread_depth)
        if thread_depth is not None
        else default_depth
    )
    major_radius = resolved_diameter / 2.0
    if resolved_thread_style != "none" and depth >= major_radius:
        raise ValueError("thread_depth must be smaller than the bolt radius")
    modeled_minor_diameter = resolved_diameter - 2.0 * depth

    if resolved_thread_style == "none":
        resolved_thread_length = 0.0
        thread_start = resolved_length
    elif resolved_thread_style == "full":
        if thread_length is not None:
            raise ValueError("thread_length is only valid when thread_style='partial'")
        resolved_thread_length = resolved_length
        thread_start = 0.0
    else:
        if thread_length is None:
            resolved_thread_length = _standard_partial_thread_length(
                resolved_diameter,
                resolved_length,
            )
            if (
                requested_thread_style == "auto"
                and resolved_thread_length >= resolved_length
            ):
                resolved_thread_style = "full"
                resolved_thread_length = resolved_length
        else:
            resolved_thread_length = _positive_finite("thread_length", thread_length)
        if resolved_thread_length <= 0.0:
            raise ValueError("partial threads require positive unthreaded shank length")
        if (
            resolved_thread_style == "partial"
            and resolved_thread_length >= resolved_length
        ):
            raise ValueError("partial thread_length must be smaller than length")
        thread_start = (
            0.0
            if resolved_thread_style == "full"
            else resolved_length - resolved_thread_length
        )

    if (
        resolved_thread_style != "none"
        and resolved_thread_detail == "modeled"
        and resolved_thread_length <= pitch
    ):
        raise ValueError("modeled thread length must be greater than thread_pitch")

    resolved_drive_size = 0.0
    resolved_drive_depth = 0.0
    if resolved_drive_style != "none":
        resolved_drive_size = _optional_positive(
            "drive_size",
            drive_size,
            resolved_head_width * 0.48,
        )
        resolved_drive_depth = _optional_positive(
            "drive_depth",
            drive_depth,
            resolved_head_height * 0.28,
        )
        if resolved_drive_size >= resolved_head_width * 0.85:
            raise ValueError("drive_size is too large for head_width")
        if resolved_drive_depth >= resolved_head_height * 0.8:
            raise ValueError("drive_depth is too large for head_height")
    elif drive_size is not None or drive_depth is not None:
        raise ValueError("drive_size and drive_depth require a non-'none' drive_style")

    default_fillet_radius = (
        0.0 if resolved_head_style == "countersunk" else resolved_diameter * 0.06
    )
    resolved_fillet_radius = _non_negative_finite(
        "underhead_fillet_radius",
        (
            default_fillet_radius
            if underhead_fillet_radius is None
            else underhead_fillet_radius
        ),
    )
    maximum_fillet_radius = min(major_radius * 0.3, resolved_head_height * 0.25)
    if resolved_fillet_radius > maximum_fillet_radius:
        raise ValueError(
            "underhead_fillet_radius is too large for the shank and head dimensions"
        )

    epsilon = max(1e-5, resolved_diameter * 1e-4)
    thread_phase_degrees = 0.0
    shank = make_cylinder_rsolid(
        radius=major_radius,
        height=resolved_length + epsilon,
        bottom_face_center=(0.0, 0.0, -epsilon),
        axis=(0.0, 0.0, 1.0),
    )

    head = _make_bolt_head(
        head_style=resolved_head_style,
        width=resolved_head_width,
        height=resolved_head_height,
        shank_radius=major_radius,
    )
    cutters = _drive_cutters(
        drive_style=resolved_drive_style,
        drive_size=resolved_drive_size,
        drive_depth=resolved_drive_depth,
        head_height=resolved_head_height,
    )
    if cutters:
        head = cut_rsolid(head, cutters, skip_non_intersecting=False)
    bolt = union_rsolid(head, shank, glue=False)
    if resolved_fillet_radius > 0.0:
        bolt = fillet_rsolid(
            solid=bolt,
            edges=[_underhead_edge(bolt, major_radius)],
            radius=resolved_fillet_radius,
        )

    modeled_thread_start = thread_start
    modeled_thread_length = resolved_thread_length
    if resolved_thread_style == "full":
        modeled_thread_start = max(pitch, resolved_fillet_radius)
        modeled_thread_length = resolved_length - modeled_thread_start
    if resolved_thread_style != "none" and resolved_thread_detail == "modeled":
        cutter = _make_thread_cutter(
            inner_radius=major_radius - depth,
            outer_radius=major_radius + depth * 0.23,
            pitch=pitch,
            start_z=modeled_thread_start,
            length=modeled_thread_length,
            thread_form=resolved_thread_form,
        )
        maximum_removed_volume = (
            math.pi
            * (major_radius * major_radius - (major_radius - depth) ** 2)
            * modeled_thread_length
        )
        thread_phase_degrees = _select_external_thread_phase(
            shank=bolt,
            cutter=cutter,
            minimum_volume=bolt.get_volume() - maximum_removed_volume,
        )
        cutter = _rotate_thread_cutter(cutter, thread_phase_degrees)
        bolt = cut_rsolid(bolt, cutter, skip_non_intersecting=False)
    bolt = cast(Solid, apply_tag(shape=bolt, tag="role.fastener.bolt"))
    bolt = cast(Solid, apply_tag(shape=bolt, tag="group.fasteners"))
    bolt.set_metadata(
        "std.fastener.bolt",
        {
            "diameter": resolved_diameter,
            "length": resolved_length,
            "head_style": resolved_head_style,
            "head_width": resolved_head_width,
            "head_height": resolved_head_height,
            "head_across_corners": head_across_corners,
            "drive_style": resolved_drive_style,
            "drive_size": resolved_drive_size,
            "drive_depth": resolved_drive_depth,
            "requested_thread_style": requested_thread_style,
            "thread_style": resolved_thread_style,
            "thread_detail": resolved_thread_detail,
            "thread_form": resolved_thread_form,
            "thread_pitch": pitch,
            "thread_pitch_source": pitch_source,
            "thread_depth": depth,
            "pitch_diameter": pitch_diameter,
            "basic_minor_diameter": basic_minor_diameter,
            "modeled_minor_diameter": modeled_minor_diameter,
            "thread_start": thread_start,
            "thread_length": resolved_thread_length,
            "modeled_thread_start": modeled_thread_start,
            "modeled_thread_length": modeled_thread_length,
            "thread_phase_degrees": thread_phase_degrees,
            "underhead_fillet_radius": resolved_fillet_radius,
            "recommended_mating_hole_chamfer_min": resolved_fillet_radius,
        },
    )
    return bolt


def _make_nut_body(style: str, width: float, height: float, knurl_count: int) -> Solid:
    if style == "hex":
        return _make_across_flats_prism(sides=6, width=width, z=0.0, height=height)
    if style == "square":
        return make_box_rsolid(
            width=width,
            height=width,
            depth=height,
            bottom_face_center=(0.0, 0.0, 0.0),
        )
    if style == "round":
        return make_cylinder_rsolid(
            radius=width / 2.0,
            height=height,
            bottom_face_center=(0.0, 0.0, 0.0),
            axis=(0.0, 0.0, 1.0),
        )

    outer_radius = width / 2.0
    points = []
    for index in range(knurl_count * 2):
        radius = outer_radius if index % 2 == 0 else outer_radius * 0.94
        angle = math.pi * index / knurl_count
        points.append((radius * math.cos(angle), radius * math.sin(angle), 0.0))
    return _make_prism(points=points, height=height)


@graph_tracking_scope
def make_nut_rsolid(
    diameter: float,
    width: float,
    height: float,
    nut_style: str = "hex",
    hole_style: str = "through",
    thread_detail: str = "modeled",
    thread_form: str = "v",
    thread_pitch: Optional[float] = None,
    thread_depth: Optional[float] = None,
    hole_depth: Optional[float] = None,
    knurl_count: int = 24,
) -> Solid:
    """Create a nut along +Z with its bottom face on the Z=0 plane.

    ``nut_style`` accepts ``hex``, ``square``, ``round``, and ``knurled``.
    Through and blind holes are supported. Modeled thread detail adds internal
    V or trapezoidal helical teeth to a major-diameter hole.
    """
    resolved_diameter = _positive_finite("diameter", diameter)
    resolved_width = _positive_finite("width", width)
    resolved_height = _positive_finite("height", height)
    resolved_nut_style = _choice("nut_style", nut_style, _NUT_STYLES)
    resolved_hole_style = _choice("hole_style", hole_style, _HOLE_STYLES)
    resolved_thread_detail = _choice("thread_detail", thread_detail, _THREAD_DETAILS)
    resolved_thread_form = _choice("thread_form", thread_form, _THREAD_FORMS)
    pitch, pitch_source = _resolve_thread_pitch(resolved_diameter, thread_pitch)
    pitch_diameter, basic_minor_diameter = _metric_thread_dimensions(
        resolved_diameter,
        pitch,
    )
    default_depth = (
        (resolved_diameter - basic_minor_diameter) / 2.0
        if resolved_thread_form == "v"
        else pitch * 0.5
    )
    depth = (
        _positive_finite("thread_depth", thread_depth)
        if thread_depth is not None
        else default_depth
    )
    major_radius = resolved_diameter / 2.0
    if depth >= major_radius:
        raise ValueError("thread_depth must be smaller than the nut hole radius")
    if resolved_width / 2.0 <= major_radius + resolved_diameter * 0.05:
        raise ValueError("width leaves insufficient wall around the nut hole")

    if (
        not isinstance(knurl_count, int)
        or isinstance(knurl_count, bool)
        or knurl_count < 8
    ):
        raise ValueError("knurl_count must be an integer of at least 8")
    if resolved_hole_style == "through":
        if hole_depth is not None:
            raise ValueError("hole_depth is only valid when hole_style='blind'")
        resolved_hole_depth = resolved_height
        hole_start = 0.0
    else:
        resolved_hole_depth = _optional_positive(
            "hole_depth",
            hole_depth,
            resolved_height * 0.75,
        )
        if resolved_hole_depth >= resolved_height:
            raise ValueError("blind hole_depth must be smaller than height")
        hole_start = resolved_height - resolved_hole_depth
    if resolved_thread_detail == "modeled" and resolved_hole_depth <= pitch:
        raise ValueError("modeled thread depth must be greater than thread_pitch")

    body = _make_nut_body(
        style=resolved_nut_style,
        width=resolved_width,
        height=resolved_height,
        knurl_count=knurl_count,
    )
    epsilon = max(1e-5, resolved_diameter * 1e-4)
    cut_start = -epsilon if resolved_hole_style == "through" else hole_start
    cut_height = (
        resolved_hole_depth + 2.0 * epsilon
        if resolved_hole_style == "through"
        else resolved_hole_depth + epsilon
    )
    hole = make_cylinder_rsolid(
        radius=major_radius,
        height=cut_height,
        bottom_face_center=(0.0, 0.0, cut_start),
        axis=(0.0, 0.0, 1.0),
    )
    nut = cut_rsolid(body, hole, skip_non_intersecting=False)
    thread_phase_degrees = 0.0
    if resolved_thread_detail == "modeled":
        ridge = _make_thread_cutter(
            inner_radius=major_radius - depth,
            outer_radius=major_radius + depth * 0.23,
            pitch=pitch,
            start_z=hole_start,
            length=resolved_hole_depth,
            thread_form=resolved_thread_form,
        )
        thread_phase_degrees = _select_internal_thread_phase(
            opened_nut=nut,
            body=body,
            ridge=ridge,
        )
        ridge = _rotate_thread_cutter(ridge, thread_phase_degrees)
        nut = union_rsolid(nut, ridge, glue=False)
    nut = cast(Solid, apply_tag(shape=nut, tag="role.fastener.nut"))
    nut = cast(Solid, apply_tag(shape=nut, tag="group.fasteners"))
    nut.set_metadata(
        "std.fastener.nut",
        {
            "diameter": resolved_diameter,
            "width": resolved_width,
            "height": resolved_height,
            "nut_style": resolved_nut_style,
            "hole_style": resolved_hole_style,
            "hole_depth": resolved_hole_depth,
            "hole_start": hole_start,
            "thread_detail": resolved_thread_detail,
            "thread_form": resolved_thread_form,
            "thread_pitch": pitch,
            "thread_pitch_source": pitch_source,
            "thread_depth": depth,
            "pitch_diameter": pitch_diameter,
            "basic_minor_diameter": basic_minor_diameter,
            "modeled_minor_diameter": resolved_diameter - 2.0 * depth,
            "thread_phase_degrees": thread_phase_degrees,
            "knurl_count": knurl_count,
        },
    )
    return nut
