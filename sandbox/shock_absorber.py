#!/usr/bin/env python3
"""
Car Shock Absorber Model - Fixed Version
"""

import simplecadapi as scad
import os
from typing import cast
from simplecadapi import (
    Solid,
    make_cylinder_rsolid,
    make_circle_rwire,
    helical_sweep_rsolid,
    translate_shape,
    export_step,
    export_stl,
)


def create_shock_absorber():
    print("=" * 50)
    print("Creating Car Shock Absorber Model (Fixed)")
    print("=" * 50)

    parts = []

    cylinder_bottom_z = 0.0
    cylinder_height = 80.0
    cylinder_top_z = cylinder_bottom_z + cylinder_height

    rod_bottom_z = 10.0
    rod_height = 90.0

    bottom_seat_bottom_z = 5.0
    seat_height = 3.0
    spring_bottom_z = bottom_seat_bottom_z + seat_height
    spring_height = 86.0
    top_seat_bottom_z = spring_bottom_z + spring_height

    # =====================
    # 1. Top Connection (Mounting Eye)
    # =====================
    print("\n[1/7] Creating top connection (mounting eye)...")

    top_mount_outer = make_cylinder_rsolid(
        radius=8.0, height=5.0, bottom_face_center=(0, 0, 100)
    )
    top_mount_inner = make_cylinder_rsolid(
        radius=4.0, height=6.0, bottom_face_center=(0, 0, 99.5)
    )
    top_mount = scad.cut_rsolidlist([top_mount_outer, top_mount_inner])[0]
    parts.append(("top_mount", top_mount, top_mount.get_volume()))
    print(f"  - Top mount: volume = {top_mount.get_volume():.2f}")

    # =====================
    # 2. Top Spring Seat
    # =====================
    print("\n[2/7] Creating top spring seat...")
    top_seat = make_cylinder_rsolid(
        radius=12.0, height=seat_height, bottom_face_center=(0, 0, top_seat_bottom_z)
    )
    parts.append(("top_seat", top_seat, top_seat.get_volume()))
    print(f"  - Top seat: volume = {top_seat.get_volume():.2f}")

    # =====================
    # 3. Spring (Coil)
    # =====================
    print("\n[3/7] Creating coil spring...")
    spring_profile = make_circle_rwire(center=(0, 0, 0), radius=1.5)
    spring = cast(
        Solid,
        translate_shape(
            helical_sweep_rsolid(
                spring_profile, pitch=8.0, height=spring_height, radius=10.0
            ),
            (0, 0, spring_bottom_z),
        ),
    )
    parts.append(("spring", spring, spring.get_volume()))
    print(f"  - Spring: volume = {spring.get_volume():.2f}")

    # =====================
    # 4. Bottom Spring Seat
    # =====================
    print("\n[4/7] Creating bottom spring seat...")
    bottom_seat = make_cylinder_rsolid(
        radius=12.0,
        height=seat_height,
        bottom_face_center=(0, 0, bottom_seat_bottom_z),
    )
    parts.append(("bottom_seat", bottom_seat, bottom_seat.get_volume()))
    print(f"  - Bottom seat: volume = {bottom_seat.get_volume():.2f}")

    # =====================
    # 5. Hydraulic Cylinder Body (Hollow)
    # =====================
    print("\n[5/7] Creating hydraulic cylinder (outer tube, hollow)...")

    # Outer cylinder
    cylinder_outer = make_cylinder_rsolid(
        radius=10.0,
        height=cylinder_height,
        bottom_face_center=(0, 0, cylinder_bottom_z),
    )
    # Inner hole (to make it hollow)
    cylinder_inner = make_cylinder_rsolid(
        radius=5.5,
        height=cylinder_height + 2.0,
        bottom_face_center=(0, 0, cylinder_bottom_z - 1.0),
    )
    hydraulic_cylinder = scad.cut_rsolidlist([cylinder_outer, cylinder_inner])[0]
    parts.append(
        ("hydraulic_cylinder", hydraulic_cylinder, hydraulic_cylinder.get_volume())
    )
    print(
        f"  - Hydraulic cylinder (hollow): volume = {hydraulic_cylinder.get_volume():.2f}"
    )

    # =====================
    # 6. Hydraulic Rod (Piston Rod) - extends above cylinder top
    # =====================
    print("\n[6/7] Creating hydraulic rod (piston rod)...")
    hydraulic_rod = make_cylinder_rsolid(
        radius=5.0, height=rod_height, bottom_face_center=(0, 0, rod_bottom_z)
    )
    parts.append(("hydraulic_rod", hydraulic_rod, hydraulic_rod.get_volume()))
    print(f"  - Hydraulic rod: volume = {hydraulic_rod.get_volume():.2f}")

    # =====================
    # 7. Bottom Connection
    # =====================
    print("\n[7/7] Creating bottom connection (mounting point)...")
    bottom_mount_outer = make_cylinder_rsolid(
        radius=8.0, height=5.0, bottom_face_center=(0, 0, -5)
    )
    bottom_mount_inner = make_cylinder_rsolid(
        radius=4.0, height=6.0, bottom_face_center=(0, 0, -5.5)
    )
    bottom_mount = scad.cut_rsolidlist([bottom_mount_outer, bottom_mount_inner])[0]
    parts.append(("bottom_mount", bottom_mount, bottom_mount.get_volume()))
    print(f"  - Bottom mount: volume = {bottom_mount.get_volume():.2f}")

    # =====================
    # Check volumes before export
    # =====================
    print("\n" + "=" * 50)
    print("Component Summary (before export):")
    total_vol = 0
    for name, part, vol in parts:
        print(f"  {name:20s}: {vol:10.2f}")
        total_vol += vol
    print(f"  {'TOTAL':20s}: {total_vol:10.2f}")

    # =====================
    # Keep solids separated and export as positioned assembly
    # =====================
    print("\n" + "=" * 50)
    print("Preparing assembly parts...")

    final_parts = [
        top_mount,
        top_seat,
        hydraulic_cylinder,
        hydraulic_rod,
        bottom_mount,
        bottom_seat,
        spring,
    ]

    print(f"  - Cylinder top Z: {cylinder_top_z:.1f}")
    print(f"  - Rod top Z: {rod_bottom_z + rod_height:.1f}")
    print(
        f"  - Spring range Z: {spring_bottom_z:.1f} -> {spring_bottom_z + spring_height:.1f}"
    )
    print(f"  - Total parts for export: {len(final_parts)}")

    output_dir = "/Users/lildino/Project/ocws/SimpleCADAPI/sandbox"
    assembly_step_path = os.path.join(output_dir, "shock_absorber_assembly.step")
    assembly_stl_path = os.path.join(output_dir, "shock_absorber_assembly.stl")

    print("\nExporting assembled model to STEP format...")
    export_step(final_parts, assembly_step_path)
    print(
        f"  - Saved: {os.path.basename(assembly_step_path)} ({len(final_parts)} solids in one file)"
    )

    print("\nExporting assembled model to STL format...")
    export_stl(final_parts, assembly_stl_path)
    print(
        f"  - Saved: {os.path.basename(assembly_stl_path)} ({len(final_parts)} solids in one file)"
    )

    print("\n" + "=" * 50)
    print("DONE!")
    print("=" * 50)

    return final_parts


if __name__ == "__main__":
    parts = create_shock_absorber()
