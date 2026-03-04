import argparse
from pathlib import Path

import simplecadapi as scad
from simplecad_self_evolve_cases.evolve import make_involute_spur_gear_rsolid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate involute spur gear STEP/STL")
    parser.add_argument("--tooth-count", type=int, default=28)
    parser.add_argument("--module", type=float, default=1.8)
    parser.add_argument("--thickness", type=float, default=10.0)
    parser.add_argument("--pressure-angle-deg", type=float, default=20.0)
    parser.add_argument("--bore-radius", type=float, default=5.0)
    parser.add_argument("--backlash", type=float, default=0.04)
    parser.add_argument("--addendum-coeff", type=float, default=1.0)
    parser.add_argument("--dedendum-coeff", type=float, default=1.25)
    parser.add_argument("--profile-points", type=int, default=16)
    parser.add_argument("--root-arc-points", type=int, default=6)
    parser.add_argument("--tip-arc-points", type=int, default=6)
    parser.add_argument("--root-fillet-points", type=int, default=8)
    parser.add_argument("--root-fillet-strength", type=float, default=0.85)
    parser.add_argument("--step", default="gear.step")
    parser.add_argument("--stl", default="gear.stl")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(__file__).resolve().parent

    if not args.quiet:
        print("[main] start involute gear generation...")

    gear = make_involute_spur_gear_rsolid(
        tooth_count=args.tooth_count,
        module=args.module,
        thickness=args.thickness,
        pressure_angle_deg=args.pressure_angle_deg,
        bore_radius=args.bore_radius,
        backlash=args.backlash,
        addendum_coeff=args.addendum_coeff,
        dedendum_coeff=args.dedendum_coeff,
        profile_points=args.profile_points,
        root_arc_points=args.root_arc_points,
        tip_arc_points=args.tip_arc_points,
        root_fillet_points=args.root_fillet_points,
        root_fillet_strength=args.root_fillet_strength,
        verbose=not args.quiet,
    )

    step_path = out_dir / args.step
    stl_path = out_dir / args.stl
    if not args.quiet:
        print("[main] export STEP...")
    scad.export_step(gear, str(step_path))
    if not args.quiet:
        print("[main] export STL...")
    scad.export_stl(gear, str(stl_path))

    print(f"OK: gear created -> {step_path}")
    print(f"OK: gear created -> {stl_path}")


if __name__ == "__main__":
    main()
