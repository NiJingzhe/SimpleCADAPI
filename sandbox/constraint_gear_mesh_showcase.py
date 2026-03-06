import argparse
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Tuple

import simplecadapi as scad
from gear_case import make_involute_spur_gear_rsolid


def _log(message: str, quiet: bool) -> None:
    if not quiet:
        print(f"[progress] {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("使用声明式约束的双齿轮啮合示例。中心距由齿轮参数自动求解。")
    )
    parser.add_argument("--teeth-a", type=int, default=16)
    parser.add_argument("--teeth-b", type=int, default=28)
    parser.add_argument("--module", type=float, default=2.0)
    parser.add_argument("--gear-thickness", type=float, default=12.0)
    parser.add_argument("--plate-gap", type=float, default=44.0)
    parser.add_argument("--plate-thickness", type=float, default=10.0)
    parser.add_argument("--shaft-radius", type=float, default=4.0)
    parser.add_argument("--bearing-height", type=float, default=8.0)
    parser.add_argument("--mesh-offset", type=float, default=0.0)
    parser.add_argument("--prefix", default="constraint_gear_mesh")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def _bbox_center_xyz(solid: scad.Solid) -> Tuple[float, float, float]:
    bb = solid.cq_solid.BoundingBox()
    return (
        0.5 * (bb.xmin + bb.xmax),
        0.5 * (bb.ymin + bb.ymax),
        0.5 * (bb.zmin + bb.zmax),
    )


def make_parts(
    teeth_a: int,
    teeth_b: int,
    module: float,
    gear_thickness: float,
    plate_gap: float,
    plate_thickness: float,
    shaft_radius: float,
    bearing_height: float,
    quiet: bool,
) -> List[Tuple[str, scad.Solid]]:
    t0 = perf_counter()
    pitch_radius_a = 0.5 * module * teeth_a
    pitch_radius_b = 0.5 * module * teeth_b
    center_distance = pitch_radius_a + pitch_radius_b

    base_w = center_distance + 140.0
    base_d = 130.0
    frame_height = plate_gap + plate_thickness
    shaft_height = frame_height + 20.0
    bearing_radius = shaft_radius + 5.0

    parts: Dict[str, scad.Solid] = {}

    _log("构建上下板和轴", quiet)

    # 机架上下板（故意先打散摆放）
    parts["base_plate"] = scad.make_box_rsolid(
        base_w, base_d, plate_thickness, bottom_face_center=(0.0, 0.0, 0.0)
    )
    parts["top_plate"] = scad.make_box_rsolid(
        base_w,
        base_d,
        plate_thickness,
        bottom_face_center=(32.0, -18.0, frame_height),
    )

    # 轴（同样先打散摆放）
    parts["shaft_a"] = scad.make_cylinder_rsolid(
        shaft_radius,
        shaft_height,
        bottom_face_center=(-40.0, 20.0, -6.0),
    )
    parts["shaft_b"] = scad.make_cylinder_rsolid(
        shaft_radius,
        shaft_height,
        bottom_face_center=(46.0, -16.0, -4.0),
    )

    # 参数化渐开线齿轮
    _log("构建渐开线齿轮 A", quiet)
    bore_radius = shaft_radius + 0.35
    parts["gear_a"] = make_involute_spur_gear_rsolid(
        tooth_count=teeth_a,
        module=module,
        thickness=gear_thickness,
        pressure_angle_deg=20.0,
        bore_radius=bore_radius,
        backlash=0.03,
        profile_points=12,
        root_arc_points=6,
        tip_arc_points=6,
        root_fillet_points=6,
        root_fillet_strength=0.86,
        verbose=False,
    )
    _log("构建渐开线齿轮 B", quiet)
    parts["gear_b"] = make_involute_spur_gear_rsolid(
        tooth_count=teeth_b,
        module=module,
        thickness=gear_thickness,
        pressure_angle_deg=20.0,
        bore_radius=bore_radius,
        backlash=0.03,
        profile_points=12,
        root_arc_points=6,
        tip_arc_points=6,
        root_fillet_points=6,
        root_fillet_strength=0.86,
        verbose=False,
    )

    # 进一步打乱齿轮初始位置
    parts["gear_a"] = scad.translate_shape(parts["gear_a"], (-15.0, 24.0, 26.0))  # type: ignore[assignment]
    parts["gear_b"] = scad.translate_shape(parts["gear_b"], (21.0, -21.0, 31.0))  # type: ignore[assignment]

    # 轴承块（下/上）
    _log("构建轴承与支撑块", quiet)
    parts["bearing_a_lower"] = scad.make_cylinder_rsolid(
        bearing_radius,
        bearing_height,
        bottom_face_center=(18.0, 10.0, 8.0),
    )
    parts["bearing_a_upper"] = scad.make_cylinder_rsolid(
        bearing_radius,
        bearing_height,
        bottom_face_center=(-20.0, -14.0, frame_height - 10.0),
    )
    parts["bearing_b_lower"] = scad.make_cylinder_rsolid(
        bearing_radius,
        bearing_height,
        bottom_face_center=(-14.0, 9.0, 6.0),
    )
    parts["bearing_b_upper"] = scad.make_cylinder_rsolid(
        bearing_radius,
        bearing_height,
        bottom_face_center=(17.0, -8.0, frame_height - 12.0),
    )

    # 齿轮 A 旁的电机支架块，用于演示侧向约束
    parts["motor_block"] = scad.make_box_rsolid(
        40.0,
        28.0,
        20.0,
        bottom_face_center=(53.0, 34.0, 12.0),
    )

    # 增加拉杆，提升机架稳定性
    _log("构建拉杆", quiet)
    tie_r = 2.6
    for name, x, y in [
        ("tie_fl", -0.5 * base_w + 12.0, 0.5 * base_d - 12.0),
        ("tie_fr", 0.5 * base_w - 12.0, 0.5 * base_d - 12.0),
        ("tie_rl", -0.5 * base_w + 12.0, -0.5 * base_d + 12.0),
        ("tie_rr", 0.5 * base_w - 12.0, -0.5 * base_d + 12.0),
    ]:
        parts[name] = scad.make_cylinder_rsolid(
            tie_r,
            plate_gap,
            bottom_face_center=(x + 9.0, y - 11.0, plate_thickness),
        )

    _log(f"make_parts 完成，用时 {perf_counter() - t0:.2f}s", quiet)
    return list(parts.items())


def constrain_assembly(
    assembly: scad.Assembly,
    teeth_a: int,
    teeth_b: int,
    module: float,
    plate_gap: float,
    plate_thickness: float,
    gear_thickness: float,
    bearing_height: float,
    mesh_offset: float,
    quiet: bool,
) -> scad.Assembly:
    t0 = perf_counter()
    pitch_radius_a = 0.5 * module * teeth_a
    pitch_radius_b = 0.5 * module * teeth_b
    target_center_distance = pitch_radius_a + pitch_radius_b + mesh_offset

    asm = assembly

    _log("应用机架约束", quiet)

    # 1) 机架闭合关系
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.top"),
        asm.part("top_plate").anchor("bbox.bottom"),
        plate_gap,
        axis="z",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.center"),
        asm.part("top_plate").anchor("bbox.center"),
        0.0,
        axis="x",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.center"),
        asm.part("top_plate").anchor("bbox.center"),
        0.0,
        axis="y",
    )

    # 2) 轴心关系：参数化啮合中心距约束在这里
    _log("应用轴中心距约束", quiet)
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.center"),
        asm.part("shaft_a").anchor("bbox.center"),
        -0.5 * target_center_distance,
        axis="x",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("shaft_a").anchor("bbox.center"),
        asm.part("shaft_b").anchor("bbox.center"),
        target_center_distance,
        axis="x",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.center"),
        asm.part("shaft_a").anchor("bbox.center"),
        0.0,
        axis="y",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.center"),
        asm.part("shaft_b").anchor("bbox.center"),
        0.0,
        axis="y",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.bottom"),
        asm.part("shaft_a").anchor("bbox.bottom"),
        -6.0,
        axis="z",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.bottom"),
        asm.part("shaft_b").anchor("bbox.bottom"),
        -6.0,
        axis="z",
    )

    # 3) 同轴约束：每根轴上的齿轮和轴承同轴
    _log("应用 A/B 轴同轴约束", quiet)
    for target in ["gear_a", "bearing_a_lower", "bearing_a_upper"]:
        asm = scad.constrain_concentric_rassembly(
            asm, asm.part("shaft_a").axis("z"), asm.part(target).axis("z")
        )
    for target in ["gear_b", "bearing_b_lower", "bearing_b_upper"]:
        asm = scad.constrain_concentric_rassembly(
            asm, asm.part("shaft_b").axis("z"), asm.part(target).axis("z")
        )

    # 4) 在每根轴上于上下板之间做堆叠约束
    _log("应用轴承-齿轮-轴承堆叠约束", quiet)
    asm = scad.stack_rassembly(
        asm,
        parts=["bearing_a_lower", "gear_a", "bearing_a_upper"],
        axis="z",
        align="center",
        justify="center",
        bounds=(
            asm.part("base_plate").anchor("bbox.top"),
            asm.part("top_plate").anchor("bbox.bottom"),
        ),
    )
    asm = scad.stack_rassembly(
        asm,
        parts=["bearing_b_lower", "gear_b", "bearing_b_upper"],
        axis="z",
        align="center",
        justify="center",
        bounds=(
            asm.part("base_plate").anchor("bbox.top"),
            asm.part("top_plate").anchor("bbox.bottom"),
        ),
    )

    # 保证两齿轮节圆所在平面在 z 方向对齐
    gear_stack_height = 2.0 * bearing_height + gear_thickness
    lead_gap = 0.5 * max(0.0, plate_gap - gear_stack_height)
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.top"),
        asm.part("gear_a").anchor("bbox.bottom"),
        lead_gap + bearing_height,
        axis="z",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.top"),
        asm.part("gear_b").anchor("bbox.bottom"),
        lead_gap + bearing_height,
        axis="z",
    )

    # 5) 拉杆约束，稳定上下板关系
    _log("应用拉杆约束", quiet)
    for rod_name, x_off, y_off in [
        ("tie_fl", -1.0, 1.0),
        ("tie_fr", 1.0, 1.0),
        ("tie_rl", -1.0, -1.0),
        ("tie_rr", 1.0, -1.0),
    ]:
        x_anchor = "bbox.left" if x_off < 0 else "bbox.right"
        y_anchor = "bbox.front" if y_off > 0 else "bbox.back"
        asm = scad.constrain_offset_rassembly(
            asm,
            asm.part("base_plate").anchor(x_anchor),
            asm.part(rod_name).anchor("bbox.center"),
            x_off * 8.0,
            axis="x",
        )
        asm = scad.constrain_offset_rassembly(
            asm,
            asm.part("base_plate").anchor(y_anchor),
            asm.part(rod_name).anchor("bbox.center"),
            y_off * -8.0,
            axis="y",
        )
        asm = scad.constrain_offset_rassembly(
            asm,
            asm.part("base_plate").anchor("bbox.top"),
            asm.part(rod_name).anchor("bbox.bottom"),
            0.0,
            axis="z",
        )

    # 6) 电机块与齿轮 A 的相对关系
    _log("应用电机块关联约束", quiet)
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("gear_a").anchor("bbox.left"),
        asm.part("motor_block").anchor("bbox.right"),
        -10.0,
        axis="x",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("gear_a").anchor("bbox.center"),
        asm.part("motor_block").anchor("bbox.center"),
        0.0,
        axis="y",
    )
    asm = scad.constrain_offset_rassembly(
        asm,
        asm.part("base_plate").anchor("bbox.top"),
        asm.part("motor_block").anchor("bbox.bottom"),
        6.0,
        axis="z",
    )

    _log(f"constrain_assembly 完成，用时 {perf_counter() - t0:.2f}s", quiet)
    return asm


def print_report(prefix: str, report: scad.SolveReport) -> None:
    print(
        f"[{prefix}] converged={report.converged}, "
        f"iterations={report.iterations}, max_delta={report.max_delta:.6g}"
    )
    for item in report.diagnostics:
        print(f"[{prefix}] diagnostic: {item}")


def main() -> None:
    args = parse_args()
    total_t0 = perf_counter()
    if args.teeth_a < 8 or args.teeth_b < 8:
        raise ValueError("--teeth-a 和 --teeth-b 必须 >= 8")
    if args.module <= 0:
        raise ValueError("--module 必须 > 0")
    if args.plate_gap <= 0 or args.plate_thickness <= 0:
        raise ValueError("--plate-gap 和 --plate-thickness 必须 > 0")

    pitch_radius_a = 0.5 * args.module * args.teeth_a
    pitch_radius_b = 0.5 * args.module * args.teeth_b
    target_center_distance = pitch_radius_a + pitch_radius_b + args.mesh_offset

    _log("开始构建零件", args.quiet)
    parts = make_parts(
        teeth_a=args.teeth_a,
        teeth_b=args.teeth_b,
        module=args.module,
        gear_thickness=args.gear_thickness,
        plate_gap=args.plate_gap,
        plate_thickness=args.plate_thickness,
        shaft_radius=args.shaft_radius,
        bearing_height=args.bearing_height,
        quiet=args.quiet,
    )

    _log("构建初始装配", args.quiet)
    asm_seed = scad.make_assembly_rassembly(parts, name="gear_mesh_seed")

    _log("求解初始装配（未加约束）", args.quiet)
    t_before = perf_counter()
    before = scad.solve_assembly_rresult(asm_seed)
    _log(f"未约束求解完成，用时 {perf_counter() - t_before:.2f}s", args.quiet)

    _log("应用声明式约束", args.quiet)
    asm_constrained = constrain_assembly(
        asm_seed,
        teeth_a=args.teeth_a,
        teeth_b=args.teeth_b,
        module=args.module,
        plate_gap=args.plate_gap,
        plate_thickness=args.plate_thickness,
        gear_thickness=args.gear_thickness,
        bearing_height=args.bearing_height,
        mesh_offset=args.mesh_offset,
        quiet=args.quiet,
    )

    _log("求解约束后装配", args.quiet)
    t_after = perf_counter()
    after = scad.solve_assembly_rresult(asm_constrained)
    _log(f"约束后求解完成，用时 {perf_counter() - t_after:.2f}s", args.quiet)

    out_dir = Path(__file__).resolve().parent
    before_step = out_dir / f"{args.prefix}_before.step"
    before_stl = out_dir / f"{args.prefix}_before.stl"
    after_step = out_dir / f"{args.prefix}_constrained.step"
    after_stl = out_dir / f"{args.prefix}_constrained.stl"

    _log("导出约束前 STEP", args.quiet)
    scad.export_step(before.solids(), str(before_step))
    _log("导出约束前 STL", args.quiet)
    scad.export_stl(before.solids(), str(before_stl))
    _log("导出约束后 STEP", args.quiet)
    scad.export_step(after.solids(), str(after_step))
    _log("导出约束后 STL", args.quiet)
    scad.export_stl(after.solids(), str(after_stl))

    shaft_a_center = _bbox_center_xyz(after.get_solid("shaft_a"))
    shaft_b_center = _bbox_center_xyz(after.get_solid("shaft_b"))
    solved_center_distance = (
        (shaft_b_center[0] - shaft_a_center[0]) ** 2
        + (shaft_b_center[1] - shaft_a_center[1]) ** 2
    ) ** 0.5

    if not args.quiet:
        print_report("before", before.report)
        print_report("after", after.report)
        print(f"[mesh] 节圆半径 A/B = {pitch_radius_a:.3f}/{pitch_radius_b:.3f}")
        print(
            "[mesh] 目标中心距 = "
            f"{target_center_distance:.3f} (mesh_offset={args.mesh_offset:.3f})"
        )
        print(f"[mesh] 求解中心距 = {solved_center_distance:.3f}")
        print(f"[mesh] 偏差 = {solved_center_distance - target_center_distance:.6f}")

    print(f"OK: {before_step}")
    print(f"OK: {before_stl}")
    print(f"OK: {after_step}")
    print(f"OK: {after_stl}")
    _log(f"总耗时 {perf_counter() - total_t0:.2f}s", args.quiet)


if __name__ == "__main__":
    main()
