"""Emit SFTC Python source from feature IR."""

from __future__ import annotations

from typing import Any, Dict, List

from .ir import FeatureProgram, fmt_num, fmt_vec, plane_vectors
from .selectors import cq_selector_to_ql_hint
from .sftc_template import ParameterRegistry, emit_sftc_module


def _box_bottom_center(origin: tuple[float, float, float], plane: str, depth: float) -> str:
    frame = plane_vectors(plane)
    normal = frame["normal"]
    adjusted = (
        origin[0] - normal[0] * 0.0,
        origin[1] - normal[1] * 0.0,
        origin[2] - normal[2] * 0.0,
    )
    return fmt_vec(adjusted)


def _fmt_dim(value: Any) -> str:
    if isinstance(value, str):
        return value
    return fmt_num(float(value))


def _emit_wire_path_segments(profile: Dict[str, Any], prefix: str) -> tuple[List[str], str]:
    lines: List[str] = []
    edge_names: List[str] = []
    for idx, segment in enumerate(profile["segments"]):
        edge = f"{prefix}_edge_{idx}"
        if segment["kind"] == "line":
            lines.append(
                f"    {edge} = scad.make_segment_redge("
                f"start={fmt_vec(segment['start'])}, end={fmt_vec(segment['end'])},)"
            )
        elif segment["kind"] == "arc3":
            lines.append(
                f"    {edge} = scad.make_three_point_arc_redge("
                f"start={fmt_vec(segment['start'])}, "
                f"middle={fmt_vec(segment['mid'])}, end={fmt_vec(segment['end'])},)"
            )
        edge_names.append(edge)
    wire_expr = f"{prefix}_wire"
    lines.append(f"    {wire_expr} = scad.make_wire_from_edges_rwire(edges=[{', '.join(edge_names)}])")
    return lines, wire_expr


def _emit_spline_path(profile: Dict[str, Any], prefix: str) -> tuple[List[str], str]:
    lines: List[str] = []
    point_lines = ",\n        ".join(fmt_vec(point) for point in profile["points"])
    wire_expr = f"{prefix}_wire"
    lines.extend(
        [
            f"    {wire_expr} = scad.make_interpolated_spline_rwire(",
            "        points=[",
            f"        {point_lines},",
            "        ],",
            "    )",
        ]
    )
    return lines, wire_expr


def _emit_profile_expr(
    profile: Dict[str, Any],
    prefix: str,
    *,
    as_wire: bool = False,
) -> tuple[List[str], str]:
    lines: List[str] = []
    kind = profile["kind"]
    plane = profile.get("plane", "XY")
    origin = profile.get("origin", (0.0, 0.0, 0.0))
    frame = profile.get("frame")
    if frame:
        normal = frame["normal"]
        extrude = frame.get("extrude", normal)
    else:
        normal = plane_vectors(plane)["normal"]
        extrude = plane_vectors(plane)["extrude"]

    if kind == "circle":
        api = "make_circle_rwire" if as_wire else "make_circle_rface"
        lines.append(
            f"    {prefix}_profile = scad.{api}("
            f"center={fmt_vec(origin)}, radius={_fmt_dim(profile['radius'])}, "
            f"normal={fmt_vec(normal)},)"
        )
        return lines, f"{prefix}_profile"

    if kind == "rect":
        u_dir = frame.get("u") if frame else plane_vectors(plane)["u"]
        v_dir = frame.get("v") if frame else plane_vectors(plane)["v"]
        # Build corners explicitly: SimpleCAD's default orthonormal frame for a
        # world normal does not match CadQuery Workplane x/y directions.
        half_w = f"(({_fmt_dim(profile['width'])}) / 2.0)"
        half_h = f"(({_fmt_dim(profile['height'])}) / 2.0)"
        ox, oy, oz = origin
        ux, uy, uz = u_dir
        vx, vy, vz = v_dir
        corners = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(
                f"({fmt_num(ox)} + ({half_w}) * ({fmt_num(ux)}) * ({su}) + ({half_h}) * ({fmt_num(vx)}) * ({sv}), "
                f"{fmt_num(oy)} + ({half_w}) * ({fmt_num(uy)}) * ({su}) + ({half_h}) * ({fmt_num(vy)}) * ({sv}), "
                f"{fmt_num(oz)} + ({half_w}) * ({fmt_num(uz)}) * ({su}) + ({half_h}) * ({fmt_num(vz)}) * ({sv}))"
            )
        point_lines = ",\n        ".join(corners)
        lines.extend(
            [
                f"    {prefix}_wire = scad.make_polyline_rwire(",
                "        points=[",
                f"        {point_lines},",
                "        ],",
                "        closed=True,",
                "    )",
            ]
        )
        if as_wire:
            return lines, f"{prefix}_wire"
        lines.append(f"    {prefix}_profile = scad.make_face_from_wire_rface(wire={prefix}_wire)")
        return lines, f"{prefix}_profile"

    if kind == "polygon":
        point_lines = ",\n        ".join(fmt_vec(point) for point in profile["points"])
        lines.extend(
            [
                f"    {prefix}_wire = scad.make_polyline_rwire(",
                "        points=[",
                f"        {point_lines},",
                "        ],",
                "        closed=True,",
                "    )",
            ]
        )
        if as_wire:
            return lines, f"{prefix}_wire"
        lines.append(f"    {prefix}_profile = scad.make_face_from_wire_rface(wire={prefix}_wire)")
        return lines, f"{prefix}_profile"

    if kind == "polyline":
        point_lines = ",\n        ".join(fmt_vec(point) for point in profile["points"])
        lines.extend(
            [
                f"    {prefix}_wire = scad.make_polyline_rwire(",
                "        points=[",
                f"        {point_lines},",
                "        ],",
                "        closed=True,",
                "    )",
            ]
        )
        if as_wire:
            return lines, f"{prefix}_wire"
        lines.append(f"    {prefix}_profile = scad.make_face_from_wire_rface(wire={prefix}_wire)")
        return lines, f"{prefix}_profile"

    if kind == "wire_path":
        wire_lines, wire_expr = _emit_wire_path_segments(profile, prefix)
        lines.extend(wire_lines)
        if as_wire:
            return lines, wire_expr
        if frame:
            lines.append(
                f"    {prefix}_profile = scad.make_face_from_wire_rface("
                f"wire={wire_expr}, normal={fmt_vec(normal)},)"
            )
        else:
            lines.append(f"    {prefix}_profile = scad.make_face_from_wire_rface(wire={wire_expr})")
        return lines, f"{prefix}_profile"

    if kind == "spline_path":
        wire_lines, wire_expr = _emit_spline_path(profile, prefix)
        lines.extend(wire_lines)
        if as_wire:
            return lines, wire_expr
        lines.append(f"    {prefix}_profile = scad.make_face_from_wire_rface(wire={wire_expr})")
        return lines, f"{prefix}_profile"

    raise ValueError(f"unsupported profile kind: {kind}")


def _emit_edge_selector(selector: tuple[str, str] | None, var_name: str, indent: str = "    ") -> tuple[str, str]:
    var = f"_{var_name}_edges"
    if selector is None:
        return var, f"{indent}{var} = {var_name}.get_edges()"
    kind, text = selector
    if " or " in text:
        lines = (
            f"{indent}{var} = ql.select({var_name}.get_edges())",
            f"{indent}# SFTC_UNSUPPORTED: refine compound selector {kind}({text!r})",
        )
        return var, "\n".join(lines)
    hint = cq_selector_to_ql_hint(text, on=kind)
    if hint is None:
        lines = (
            f"{indent}{var} = ql.select({var_name}.get_edges())",
            f"{indent}# SFTC_UNSUPPORTED: refine selector {kind}({text!r})",
        )
        return var, "\n".join(lines)
    return var, f"{indent}{var} = ql.select({var_name}.get_edges()).where({hint})"


def _emit_cut_tool(profile: Dict[str, Any], plane: str, depth: float, prefix: str) -> List[str]:
    lines, profile_expr = _emit_profile_expr(profile, prefix)
    frame = profile.get("frame")
    if frame:
        direction = frame.get("extrude", frame["normal"])
    else:
        direction = plane_vectors(plane)["extrude"]
    lines.append(
        f"    {prefix}_tool = scad.extrude_rsolid("
        f"profile={profile_expr}, direction={fmt_vec(direction)}, "
        f"distance={fmt_num(depth)},)"
    )
    return lines


def emit_sftc(program: FeatureProgram) -> str:
    header = program.stem or program.graph_id
    if program.family:
        header += f" ({program.family})"
    registry = ParameterRegistry()
    for param in program.parameters:
        registry.define(param.name, param.default, comment=param.comment, unit=param.unit)

    feature_lines: List[str] = []
    current_body = "body"

    for step in program.steps:
        feature_lines.append(f"    # Feature {step.index}: {step.description}")
        params = step.params

        if step.kind == "box_solid":
            var = params["result_var"]
            origin = params.get("origin", (0.0, 0.0, 0.0))
            feature_lines.append(
                f"    {var} = scad.make_box_rsolid("
                f"width={fmt_num(params['width'])}, "
                f"height={fmt_num(params['height'])}, "
                f"depth={fmt_num(params['depth'])}, "
                f"bottom_face_center={fmt_vec(origin)},)"
            )
            current_body = var
            continue

        if step.kind == "cylinder_solid":
            var = params["result_var"]
            origin = params.get("origin", (0.0, 0.0, 0.0))
            axis = plane_vectors(params["plane"])["extrude"]
            feature_lines.append(
                f"    {var} = scad.make_cylinder_rsolid("
                f"radius={fmt_num(params['radius'])}, height={fmt_num(params['height'])}, "
                f"bottom_face_center={fmt_vec(origin)}, axis={fmt_vec(axis)},)"
            )
            current_body = var
            continue

        if step.kind == "sphere_solid":
            var = params["result_var"]
            origin = params.get("origin", (0.0, 0.0, 0.0))
            feature_lines.append(
                f"    {var} = scad.make_sphere_rsolid("
                f"radius={fmt_num(params['radius'])}, center={fmt_vec(origin)},)"
            )
            current_body = var
            continue

        if step.kind == "extrude_profile":
            var = params["result_var"]
            profile_lines, _ = _emit_profile_expr(params["profile"], var)
            feature_lines.extend(profile_lines)
            direction = plane_vectors(params["plane"])["extrude"]
            distance = float(params["distance"])
            if params.get("both"):
                feature_lines.append(
                    f"    {var}_pos = scad.extrude_rsolid("
                    f"profile={var}_profile, direction={fmt_vec(direction)}, "
                    f"distance={fmt_num(distance / 2.0)},)"
                )
                neg = tuple(-component for component in direction)
                feature_lines.append(
                    f"    {var}_neg = scad.extrude_rsolid("
                    f"profile={var}_profile, direction={fmt_vec(neg)}, "
                    f"distance={fmt_num(distance / 2.0)},)"
                )
                feature_lines.append(f"    {var} = scad.union_rsolid({var}_pos, {var}_neg,)")
            else:
                feature_lines.append(
                    f"    {var} = scad.extrude_rsolid("
                    f"profile={var}_profile, direction={fmt_vec(direction)}, "
                    f"distance={fmt_num(distance)},)"
                )
            current_body = var
            continue

        if step.kind == "revolve_profile":
            var = params["result_var"]
            profile_lines, _ = _emit_profile_expr(params["profile"], var)
            feature_lines.extend(profile_lines)
            feature_lines.append(
                f"    {var} = scad.revolve_rsolid("
                f"profile={var}_profile, axis={fmt_vec(params['axis'])}, "
                f"angle={fmt_num(params['angle'])}, origin={fmt_vec(params['origin'])},)"
            )
            current_body = var
            continue

        if step.kind == "loft":
            var = params["result_var"]
            profile_vars: List[str] = []
            for idx, profile in enumerate(params["profiles"]):
                prefix = f"{var}_p{idx}"
                profile_lines, profile_var = _emit_profile_expr(profile, prefix, as_wire=True)
                feature_lines.extend(profile_lines)
                profile_vars.append(profile_var)
            profiles_arg = ", ".join(profile_vars)
            feature_lines.append(
                f"    {var} = scad.loft_rsolid(profiles=[{profiles_arg}],)"
            )
            current_body = var
            continue

        if step.kind == "through_hole":
            target = params["target_var"]
            result = params["result_var"]
            plane = params["plane"]
            direction = plane_vectors(plane)["extrude"]
            origin = params.get("origin", (0.0, 0.0, 0.0))
            radius = float(params["diameter"]) / 2.0
            feature_lines.extend(
                [
                    f"    hole_profile = scad.make_circle_rface("
                    f"center={fmt_vec(origin)}, radius={fmt_num(radius)}, "
                    f"normal={fmt_vec(plane_vectors(plane)['normal'])},)",
                    f"    hole_tool = scad.extrude_rsolid("
                    f"profile=hole_profile, direction={fmt_vec(direction)}, distance=1000.0,)",
                    f"    {result} = scad.cut_rsolid({target}, hole_tool)",
                ]
            )
            current_body = result
            continue

        if step.kind in {"through_cut_profile", "blind_cut"}:
            target = params["target_var"]
            result = params["result_var"]
            depth = float(params.get("depth", 1000.0))
            feature_lines.extend(_emit_cut_tool(params["profile"], params["plane"], depth, "cut"))
            feature_lines.append(f"    {result} = scad.cut_rsolid({target}, cut_tool)")
            current_body = result
            continue

        if step.kind == "pattern_cut":
            target = params["target_var"]
            result = params["result_var"]
            pattern = params["pattern"]
            depth = float(params["depth"])
            plane = params["plane"]
            x_count = int(pattern["x_count"])
            y_count = int(pattern["y_count"])
            x_spacing = float(pattern["x_spacing"])
            y_spacing = float(pattern["y_spacing"])
            feature_lines.append(f"    {result} = {target}")
            feature_lines.append("    for _ix in range(" + str(x_count) + "):")
            feature_lines.append("        for _iy in range(" + str(y_count) + "):")
            feature_lines.append(
                f"            _ox = (_ix - ({x_count} - 1) / 2.0) * {fmt_num(x_spacing)}"
            )
            feature_lines.append(
                f"            _oy = (_iy - ({y_count} - 1) / 2.0) * {fmt_num(y_spacing)}"
            )
            profile = dict(params["profile"])
            base_origin = profile.get("origin", (0.0, 0.0, 0.0))
            frame = plane_vectors(plane)
            origin_expr = (
                f"({fmt_num(base_origin[0])} + _ox * {fmt_num(frame['u'][0])} + _oy * {fmt_num(frame['v'][0])}, "
                f"{fmt_num(base_origin[1])} + _ox * {fmt_num(frame['u'][1])} + _oy * {fmt_num(frame['v'][1])}, "
                f"{fmt_num(base_origin[2])} + _ox * {fmt_num(frame['u'][2])} + _oy * {fmt_num(frame['v'][2])})"
            )
            if profile["kind"] == "rect":
                feature_lines.extend(
                    [
                        f"            _profile = scad.make_rectangle_rface("
                        f"width={_fmt_dim(profile['width'])}, height={_fmt_dim(profile['height'])}, "
                        f"center={origin_expr}, normal={fmt_vec(frame['normal'])},)",
                        f"            _tool = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(frame['extrude'])}, "
                        f"distance={fmt_num(depth)},)",
                        f"            {result} = scad.cut_rsolid({result}, _tool)",
                    ]
                )
            else:
                feature_lines.append("            pass  # SFTC_UNSUPPORTED: pattern profile kind")
            current_body = result
            continue

        if step.kind == "boolean":
            mode = params["mode"]
            fn = {"union": "union_rsolid", "cut": "cut_rsolid", "intersect": "intersect_rsolid"}[mode]
            feature_lines.append(
                f"    {params['result_var']} = scad.{fn}("
                f"{params['target_var']}, {params['tool_var']},)"
            )
            current_body = params["result_var"]
            continue

        if step.kind == "chamfer":
            edge_var, edge_lines = _emit_edge_selector(params.get("selector"), params["target_var"])
            feature_lines.append(edge_lines)
            feature_lines.append(
                f"    {params['result_var']} = scad.chamfer_rsolid("
                f"solid={params['target_var']}, edges={edge_var}, "
                f"distance={fmt_num(params['distance'])},)"
            )
            current_body = params["result_var"]
            continue

        if step.kind == "fillet":
            edge_var, edge_lines = _emit_edge_selector(params.get("selector"), params["target_var"])
            feature_lines.append(edge_lines)
            feature_lines.append(
                f"    {params['result_var']} = scad.fillet_rsolid("
                f"solid={params['target_var']}, edges={edge_var}, "
                f"radius={fmt_num(params['radius'])},)"
            )
            current_body = params["result_var"]
            continue

        feature_lines.append(f"    # SFTC_UNSUPPORTED: step kind {step.kind!r}")

    return emit_sftc_module(
        graph_id=program.graph_id,
        header=f"SFTC model converted from CadQuery: {header}",
        parameters=registry,
        feature_lines=feature_lines,
        unsupported=program.unsupported,
        body=current_body,
        include_ql_import=True,
    )
