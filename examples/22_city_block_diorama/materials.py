"""Material palette for the architectural city-block diorama."""

from __future__ import annotations

import simplecadapi as scad


def make_city_materials() -> dict[str, scad.Material]:
    """Create the small, intentionally graphic material palette."""

    palette = {
        "earth": (0.30, 0.19, 0.12),
        "earth_trim": (0.48, 0.30, 0.17),
        "ground": (0.38, 0.42, 0.29),
        "road": (0.10, 0.12, 0.14),
        "road_marking": (0.92, 0.79, 0.28),
        "sidewalk": (0.65, 0.62, 0.54),
        "curb": (0.46, 0.47, 0.44),
        "brick": (0.56, 0.20, 0.13),
        "brick_dark": (0.30, 0.10, 0.07),
        "plaster": (0.78, 0.59, 0.35),
        "cream": (0.83, 0.70, 0.48),
        "concrete": (0.55, 0.57, 0.56),
        "steel": (0.16, 0.20, 0.24),
        "glass": (0.16, 0.52, 0.67),
        "glass_light": (0.40, 0.77, 0.84),
        "roof": (0.13, 0.15, 0.17),
        "wood": (0.43, 0.20, 0.08),
        "wood_light": (0.70, 0.43, 0.17),
        "interior_wall": (0.86, 0.73, 0.52),
        "interior_floor": (0.69, 0.48, 0.25),
        "furniture": (0.34, 0.17, 0.09),
        "upholstery": (0.72, 0.20, 0.14),
        "counter": (0.89, 0.51, 0.12),
        "sign_red": (0.80, 0.08, 0.05),
        "sign_purple": (0.45, 0.12, 0.63),
        "sign_yellow": (0.98, 0.76, 0.12),
        "water": (0.08, 0.48, 0.86),
        "plant": (0.13, 0.45, 0.18),
        "plant_light": (0.38, 0.68, 0.20),
        "lamp": (0.82, 0.78, 0.54),
        "white": (0.92, 0.90, 0.80),
    }
    return {
        key: scad.make_material_rmaterial(
            material_id=f"city_{key}",
            name=f"City {key.replace('_', ' ')}",
            color=color,
        )
        for key, color in palette.items()
    }
