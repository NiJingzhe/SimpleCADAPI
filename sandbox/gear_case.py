def make_involute_spur_gear_rsolid(
    tooth_count: int = 28,
    module: float = 1.8,
    thickness: float = 10.0,
    pressure_angle_deg: float = 20.0,
    bore_radius: float = 5.0,
    backlash: float = 0.03,
    addendum_coeff: float = 1.0,
    dedendum_coeff: float = 1.25,
    profile_points: int = 20,
    root_arc_points: int = 8,
    tip_arc_points: int = 8,
    root_fillet_points: int = 8,
    root_fillet_strength: float = 0.85,
    verbose: bool = False,
):
    """Create an involute spur gear solid."""
    import math
    import simplecadapi as scad

    if tooth_count < 8:
        raise ValueError("tooth_count 必须 >= 8")
    if module <= 0:
        raise ValueError("module 必须 > 0")
    if thickness <= 0:
        raise ValueError("thickness 必须 > 0")
    if not 10.0 <= pressure_angle_deg <= 35.0:
        raise ValueError("pressure_angle_deg 必须位于 [10, 35]")
    if profile_points < 8:
        raise ValueError("profile_points 必须 >= 8")
    if root_arc_points < 4:
        raise ValueError("root_arc_points 必须 >= 4")
    if tip_arc_points < 4:
        raise ValueError("tip_arc_points 必须 >= 4")
    if root_fillet_points < 3:
        raise ValueError("root_fillet_points 必须 >= 3")
    if addendum_coeff <= 0 or dedendum_coeff <= 0:
        raise ValueError("addendum_coeff 和 dedendum_coeff 必须 > 0")
    if root_fillet_strength <= 0:
        raise ValueError("root_fillet_strength 必须 > 0")

    if verbose:
        print("[gear] 计算基础几何参数...")

    pressure_angle = math.radians(pressure_angle_deg)
    pitch_radius = 0.5 * module * tooth_count
    addendum = addendum_coeff * module
    dedendum = dedendum_coeff * module

    tip_radius = pitch_radius + addendum
    root_radius = pitch_radius - dedendum
    base_radius = pitch_radius * math.cos(pressure_angle)

    if root_radius <= 0:
        raise ValueError("几何无效：root_radius <= 0")
    if bore_radius < 0 or bore_radius >= root_radius:
        raise ValueError("bore_radius 必须 >= 0 且 < root_radius")

    half_tooth_angle = (math.pi / (2.0 * tooth_count)) - (
        backlash / (2.0 * pitch_radius)
    )
    if half_tooth_angle <= 0:
        raise ValueError("在当前节圆半径下，backlash 过大")

    inv_pitch = math.tan(pressure_angle) - pressure_angle
    r_start = max(root_radius, base_radius)

    def flank_angle_at_radius(radius: float) -> float:
        ratio = min(1.0, max(0.0, base_radius / radius))
        phi = math.acos(ratio)
        inv_r = math.tan(phi) - phi
        return half_tooth_angle + inv_pitch - inv_r

    beta_root = flank_angle_at_radius(r_start)
    beta_tip = flank_angle_at_radius(tip_radius)

    if verbose:
        tooth_thickness_pitch = 2.0 * pitch_radius * half_tooth_angle
        tooth_thickness_tip = 2.0 * tip_radius * beta_tip
        print(
            "[gear] 半径 rp/rb/rf/ra = "
            f"{pitch_radius:.4f}/{base_radius:.4f}/{root_radius:.4f}/{tip_radius:.4f}"
        )
        print(
            "[gear] 齿廓角 root->tip (deg) = "
            f"{math.degrees(beta_root):.4f} -> {math.degrees(beta_tip):.4f}"
        )
        print(
            "[gear] 齿厚 pitch->tip = "
            f"{tooth_thickness_pitch:.4f} -> {tooth_thickness_tip:.4f}"
        )

    if verbose:
        print("[gear] 采样渐开线齿廓...")

    rs = [
        r_start + (tip_radius - r_start) * i / (profile_points - 1)
        for i in range(profile_points)
    ]

    flank_pos: list[tuple[float, float]] = []
    flank_neg: list[tuple[float, float]] = []
    for radius in rs:
        beta = flank_angle_at_radius(radius)
        x = radius * math.cos(beta)
        y = radius * math.sin(beta)
        flank_pos.append((x, y))
        flank_neg.append((x, -y))

    start_angle = math.atan2(flank_pos[0][1], flank_pos[0][0])
    tip_angle_neg = math.atan2(flank_neg[-1][1], flank_neg[-1][0])
    tip_angle_pos = math.atan2(flank_pos[-1][1], flank_pos[-1][0])

    local_tip_arc = [
        (
            tip_radius
            * math.cos(
                tip_angle_neg + (tip_angle_pos - tip_angle_neg) * i / tip_arc_points
            ),
            tip_radius
            * math.sin(
                tip_angle_neg + (tip_angle_pos - tip_angle_neg) * i / tip_arc_points
            ),
        )
        for i in range(1, tip_arc_points)
    ]

    root_neg = (
        root_radius * math.cos(-start_angle),
        root_radius * math.sin(-start_angle),
    )
    root_pos = (
        root_radius * math.cos(start_angle),
        root_radius * math.sin(start_angle),
    )

    def _norm2d(x: float, y: float) -> tuple[float, float]:
        length = math.hypot(x, y)
        if length <= 1e-12:
            return (0.0, 0.0)
        return (x / length, y / length)

    def _hermite_points(
        p0: tuple[float, float],
        p1: tuple[float, float],
        t0: tuple[float, float],
        t1: tuple[float, float],
        count: int,
    ) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for i in range(count):
            u = i / (count - 1)
            h00 = 2.0 * u * u * u - 3.0 * u * u + 1.0
            h10 = u * u * u - 2.0 * u * u + u
            h01 = -2.0 * u * u * u + 3.0 * u * u
            h11 = u * u * u - u * u
            x = h00 * p0[0] + h10 * t0[0] + h01 * p1[0] + h11 * t1[0]
            y = h00 * p0[1] + h10 * t0[1] + h01 * p1[1] + h11 * t1[1]
            points.append((x, y))
        return points

    tooth_local: list[tuple[float, float]] = []
    if root_radius < r_start - 1e-8:
        root_clearance = r_start - root_radius
        blend_len = max(0.25 * module, root_fillet_strength * root_clearance)

        root_tangent_neg = _norm2d(math.sin(start_angle), math.cos(start_angle))
        flank_dir_neg = _norm2d(
            flank_neg[1][0] - flank_neg[0][0],
            flank_neg[1][1] - flank_neg[0][1],
        )

        blend_neg = _hermite_points(
            root_neg,
            flank_neg[0],
            (root_tangent_neg[0] * blend_len, root_tangent_neg[1] * blend_len),
            (flank_dir_neg[0] * blend_len, flank_dir_neg[1] * blend_len),
            root_fillet_points,
        )
        blend_pos = [(x, -y) for (x, y) in reversed(blend_neg)]

        tooth_local.extend(blend_neg)
        tooth_local.extend(flank_neg[1:])
        tooth_local.extend(local_tip_arc)
        tooth_local.extend(reversed(flank_pos))
        tooth_local.extend(blend_pos[1:])
    else:
        tooth_local.append(root_neg)
        tooth_local.extend(flank_neg)
        tooth_local.extend(local_tip_arc)
        tooth_local.extend(reversed(flank_pos))
        tooth_local.append(root_pos)

    if verbose and root_radius < r_start - 1e-8:
        print(
            "[gear] 启用齿根圆角过渡："
            f"clearance={r_start - root_radius:.4f}, "
            f"points={root_fillet_points}, strength={root_fillet_strength:.3f}"
        )

    def rotate_xy(point: tuple[float, float], angle: float) -> tuple[float, float]:
        c = math.cos(angle)
        s = math.sin(angle)
        return (point[0] * c - point[1] * s, point[0] * s + point[1] * c)

    if verbose:
        print("[gear] 构建完整 2D 齿形轮廓...")

    tooth_pitch_angle = 2.0 * math.pi / tooth_count
    full_profile: list[tuple[float, float]] = []

    for k in range(tooth_count):
        center_angle = k * tooth_pitch_angle
        tooth_world = [rotate_xy(p, center_angle) for p in tooth_local]

        if not full_profile:
            full_profile.extend(tooth_world)
        else:
            full_profile.extend(tooth_world[1:])

        a0 = center_angle + start_angle
        a1 = center_angle + tooth_pitch_angle - start_angle
        for i in range(1, root_arc_points):
            a = a0 + (a1 - a0) * i / root_arc_points
            full_profile.append((root_radius * math.cos(a), root_radius * math.sin(a)))

    cleaned: list[tuple[float, float]] = []
    for point in full_profile:
        if not cleaned:
            cleaned.append(point)
            continue
        if math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) > 1e-7:
            cleaned.append(point)

    if (
        len(cleaned) >= 2
        and math.hypot(cleaned[0][0] - cleaned[-1][0], cleaned[0][1] - cleaned[-1][1])
        <= 1e-7
    ):
        cleaned.pop()

    if len(cleaned) < 3:
        raise ValueError("生成的轮廓点数量过少")

    if verbose:
        print(f"[gear] 使用 {len(cleaned)} 个点拉伸轮廓...")

    profile_pts = [(x, y, 0.0) for (x, y) in cleaned]
    profile_wire = scad.make_polyline_rwire(profile_pts, closed=True)
    gear = scad.extrude_rsolid(profile_wire, (0.0, 0.0, 1.0), thickness)

    if bore_radius > 0:
        if verbose:
            print("[gear] 切出中心孔...")
        bore = scad.make_cylinder_rsolid(bore_radius, thickness)
        gear = scad.cut_rsolidlist(gear, bore)[0]

    if verbose:
        print("[gear] 完成。")
    return gear
