"""Building shells and deliberately visible interiors for Example 22."""

from __future__ import annotations

import simplecadapi as scad

from common import add_box, add_cylinder, ground_assembly
from dimensions import BuildingSpec


def _new_building(*, spec: BuildingSpec) -> scad.Assembly:
    return scad.make_assembly_rassembly(
        assembly_id=f"building_{spec.code.lower()}",
        name=f"{spec.code} {spec.kind.replace('_', ' ')}",
    )


def _box(
    assembly: scad.Assembly,
    *,
    component_id: str,
    width: float,
    height: float,
    depth: float,
    center: tuple[float, float, float],
    material: scad.Material,
    name: str,
    tags: tuple[str, ...] = ("role.architecture",),
) -> scad.Assembly:
    return add_box(
        assembly=assembly,
        component_id=component_id,
        width=width,
        height=height,
        depth=depth,
        center=center,
        material=material,
        name=name,
        tags=tags,
    )


def _cylinder(
    assembly: scad.Assembly,
    *,
    component_id: str,
    radius: float,
    height: float,
    center: tuple[float, float, float],
    material: scad.Material,
    name: str,
    tags: tuple[str, ...] = ("role.interior",),
) -> scad.Assembly:
    return add_cylinder(
        assembly=assembly,
        component_id=component_id,
        radius=radius,
        height=height,
        center=center,
        material=material,
        name=name,
        tags=tags,
    )


def _shell(
    assembly: scad.Assembly,
    *,
    spec: BuildingSpec,
    materials: dict[str, scad.Material],
    facade: str,
    roof: str = "roof",
) -> scad.Assembly:
    """Build a continuous four-sided floor-by-floor building shell."""

    w, d, fh = spec.width, spec.depth, spec.floor_height
    wall = 1.4
    slab = 0.75
    wall_height = fh - slab
    for floor in range(spec.floors):
        z = floor * fh
        assembly = _box(
            assembly,
            component_id=f"floor_{floor + 1}",
            width=w,
            height=d,
            depth=0.75,
            center=(0.0, 0.0, z),
            material=materials["interior_floor"],
            name=f"Floor slab {floor + 1}",
            tags=("role.architecture", "role.interior"),
        )
        assembly = _box(
            assembly,
            component_id=f"rear_wall_{floor + 1}",
            width=w,
            height=wall,
            depth=wall_height,
            center=(0.0, d / 2.0 - wall / 2.0, z + slab),
            material=materials[facade],
            name=f"Rear wall {floor + 1}",
            tags=("role.facade",),
        )
        for side, x in (("left", -w / 2.0 + wall / 2.0), ("right", w / 2.0 - wall / 2.0)):
            assembly = _box(
                assembly,
                component_id=f"{side}_wall_{floor + 1}",
                width=wall,
                height=d - wall * 2.0,
                depth=wall_height,
                center=(x, 0.0, z + slab),
                material=materials[facade],
                name=f"{side.title()} wall {floor + 1}",
                tags=("role.facade",),
            )
        assembly = _box(
            assembly,
            component_id=f"front_wall_{floor + 1}",
            width=w,
            height=wall,
            depth=wall_height,
            center=(0.0, -d / 2.0 + wall / 2.0, z + slab),
            material=materials[facade],
            name=f"Front wall {floor + 1}",
            tags=("role.facade",),
        )
    assembly = _box(
        assembly,
        component_id="closed_roof",
        width=w + 2.0,
        height=d + 2.0,
        depth=0.8,
        center=(0.0, 0.0, spec.total_height),
        material=materials[roof],
        name="Closed roof slab",
        tags=("role.roof",),
    )
    for index, x in enumerate((-w / 2.0 + 1.0, w / 2.0 - 1.0), start=1):
        assembly = _box(
            assembly,
            component_id=f"roof_parapet_{index}",
            width=1.2,
            height=d + 2.0,
            depth=1.4,
            center=(x, 0.0, spec.total_height + 0.8),
            material=materials[facade],
            name=f"Roof parapet {index}",
            tags=("role.roof",),
        )
    return assembly


def _stair(
    assembly: scad.Assembly,
    *,
    x: float,
    y: float,
    z: float,
    width: float,
    floor_height: float,
    materials: dict[str, scad.Material],
    prefix: str,
) -> scad.Assembly:
    """Add a compact staircase as overlapping, connected stepped boxes."""

    steps = 5
    rise = (floor_height - 0.75) / steps
    for index in range(steps):
        assembly = _box(
            assembly,
            component_id=f"{prefix}_step_{index + 1}",
            width=width,
            height=2.4,
            depth=rise * (index + 1),
            center=(x, y + index * 2.0, z + 0.75),
            material=materials["wood_light"],
            name=f"{prefix} stair {index + 1}",
            tags=("role.interior",),
        )
    return assembly


def _desk(
    assembly: scad.Assembly,
    *,
    prefix: str,
    x: float,
    y: float,
    z: float,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    assembly = _box(
        assembly,
        component_id=f"{prefix}_top",
        width=5.0,
        height=2.5,
        depth=0.35,
        center=(x, y, z + 3.35),
        material=materials["wood_light"],
        name=f"{prefix} desk top",
        tags=("role.interior", "role.furniture"),
    )
    for index, leg_x in enumerate((x - 2.0, x + 2.0), start=1):
        assembly = _box(
            assembly,
            component_id=f"{prefix}_leg_{index}",
            width=0.35,
            height=0.35,
            depth=2.6,
            center=(leg_x, y, z + 0.75),
            material=materials["furniture"],
            name=f"{prefix} desk leg {index}",
            tags=("role.interior", "role.furniture"),
        )
    return assembly


def _table(
    assembly: scad.Assembly,
    *,
    prefix: str,
    x: float,
    y: float,
    z: float,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    assembly = _cylinder(
        assembly,
        component_id=f"{prefix}_top",
        radius=2.7,
        height=0.4,
        center=(x, y, z + 3.35),
        material=materials["wood_light"],
        name=f"{prefix} round table",
    )
    return _cylinder(
        assembly,
        component_id=f"{prefix}_leg",
        radius=0.35,
        height=2.7,
        center=(x, y, z + 0.75),
        material=materials["furniture"],
        name=f"{prefix} table leg",
    )


def _bed(
    assembly: scad.Assembly,
    *,
    prefix: str,
    x: float,
    y: float,
    z: float,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    assembly = _box(
        assembly,
        component_id=f"{prefix}_frame",
        width=5.0,
        height=8.0,
        depth=1.0,
        center=(x, y, z + 0.75),
        material=materials["furniture"],
        name=f"{prefix} bed frame",
        tags=("role.interior", "role.furniture"),
    )
    return _box(
        assembly,
        component_id=f"{prefix}_blanket",
        width=4.6,
        height=5.7,
        depth=0.45,
        center=(x, y - 0.6, z + 1.75),
        material=materials["upholstery"],
        name=f"{prefix} blanket",
        tags=("role.interior", "role.furniture"),
    )


def _sofa(
    assembly: scad.Assembly,
    *,
    prefix: str,
    x: float,
    y: float,
    z: float,
    materials: dict[str, scad.Material],
) -> scad.Assembly:
    assembly = _box(
        assembly,
        component_id=f"{prefix}_seat",
        width=7.0,
        height=2.5,
        depth=1.4,
        center=(x, y, z + 0.75),
        material=materials["upholstery"],
        name=f"{prefix} sofa seat",
        tags=("role.interior", "role.furniture"),
    )
    return _box(
        assembly,
        component_id=f"{prefix}_back",
        width=7.0,
        height=0.8,
        depth=3.2,
        center=(x, y + 1.0, z + 2.15),
        material=materials["upholstery"],
        name=f"{prefix} sofa back",
        tags=("role.interior", "role.furniture"),
    )


def _sign(
    assembly: scad.Assembly,
    *,
    code: str,
    label: str,
    width: float,
    y: float,
    z: float,
    material: scad.Material,
) -> scad.Assembly:
    return _box(
        assembly,
        component_id=f"sign_{code.lower()}",
        width=width,
        height=0.7,
        depth=3.2,
        center=(0.0, y, z),
        material=material,
        name=label,
        tags=("role.signage",),
    )


def _add_window_grid(
    assembly: scad.Assembly,
    *,
    spec: BuildingSpec,
    materials: dict[str, scad.Material],
    material_key: str,
    floors: int | None = None,
) -> scad.Assembly:
    """Add a sparse glazed front grid on the closed facade."""

    count = floors if floors is not None else spec.floors
    for floor in range(count):
        z = floor * spec.floor_height + 0.75
        for index, x in enumerate((-spec.width * 0.28, 0.0, spec.width * 0.28), start=1):
            assembly = _box(
                assembly,
                component_id=f"window_{floor + 1}_{index}",
                width=spec.width * 0.18,
                height=0.35,
                depth=spec.floor_height - 2.0,
                center=(x, -spec.depth / 2.0 - 0.12, z + 1.0),
                material=materials[material_key],
                name=f"Front window {floor + 1}.{index}",
                tags=("role.facade", "role.glazing"),
            )
    return assembly


def _make_glass_tower(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="steel")
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="glass_light")
    w, d, fh = spec.width, spec.depth, spec.floor_height
    for floor in range(spec.floors):
        z = floor * fh
        building = _box(
            building,
            component_id=f"glass_side_{floor + 1}",
            width=0.35,
            height=d - 3.0,
            depth=fh - 0.75,
            center=(-w / 2.0 + 0.2, 0.0, z + 0.75),
            material=materials["glass"],
            name=f"Glass side curtain {floor + 1}",
            tags=("role.facade", "role.glazing"),
        )
        building = _desk(building, prefix=f"tower_{floor + 1}_desk_a", x=-10.0, y=-5.0, z=z, materials=materials)
        building = _desk(building, prefix=f"tower_{floor + 1}_desk_b", x=8.0, y=4.0, z=z, materials=materials)
        building = _box(
            building,
            component_id=f"tower_core_{floor + 1}",
            width=7.0,
            height=8.0,
            depth=fh - 0.75,
            center=(8.0, d / 2.0 - 6.0, z + 0.75),
            material=materials["concrete"],
            name=f"Tower elevator core {floor + 1}",
            tags=("role.interior", "role.structure"),
        )
        building = _stair(
            building,
            x=-w / 2.0 + 6.0,
            y=-d / 2.0 + 4.0,
            z=z,
            width=4.0,
            floor_height=fh,
            materials=materials,
            prefix=f"tower_{floor + 1}",
        )
    building = _box(
        building,
        component_id="tower_rooftop_plant",
        width=12.0,
        height=8.0,
        depth=3.0,
        center=(0.0, 9.0, spec.total_height + 0.8),
        material=materials["steel"],
        name="Tower rooftop plant room",
        tags=("role.roof",),
    )
    return building


def _make_brick_residential(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="brick")
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="cream")
    for floor in range(spec.floors):
        z = floor * spec.floor_height
        building = _box(
            building,
            component_id=f"corridor_{floor + 1}",
            width=spec.width - 6.0,
            height=3.0,
            depth=0.35,
            center=(0.0, 2.0, z + 0.75),
            material=materials["interior_wall"],
            name=f"Residential corridor partition {floor + 1}",
            tags=("role.interior",),
        )
        building = _bed(building, prefix=f"flat_{floor + 1}_bed_a", x=-12.0, y=-4.0, z=z, materials=materials)
        building = _bed(building, prefix=f"flat_{floor + 1}_bed_b", x=10.0, y=6.0, z=z, materials=materials)
        building = _sofa(building, prefix=f"flat_{floor + 1}_sofa", x=0.0, y=-8.0, z=z, materials=materials)
        building = _stair(
            building,
            x=spec.width / 2.0 - 7.0,
            y=-spec.depth / 2.0 + 4.0,
            z=z,
            width=4.0,
            floor_height=spec.floor_height,
            materials=materials,
            prefix=f"residential_{floor + 1}",
        )
        building = _box(
            building,
            component_id=f"balcony_{floor + 1}",
            width=spec.width * 0.46,
            height=3.5,
            depth=0.7,
            center=(0.0, -spec.depth / 2.0 - 1.7, z + 0.75),
            material=materials["wood_light"],
            name=f"Residential balcony {floor + 1}",
            tags=("role.facade", "role.street_furniture"),
        )
    building = _sign(
        building,
        code=spec.code,
        label="Brick residential sign",
        width=12.0,
        y=-spec.depth / 2.0 - 0.3,
        z=spec.total_height - 2.2,
        material=materials["sign_yellow"],
    )
    return building


def _make_noodle_bar(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="brick")
    w, d = spec.width, spec.depth
    building = _box(
        building,
        component_id="kitchen_backwall",
        width=w - 5.0,
        height=2.0,
        depth=5.0,
        center=(0.0, d / 2.0 - 4.0, 0.75),
        material=materials["brick_dark"],
        name="Noodle bar kitchen wall",
        tags=("role.interior",),
    )
    building = _box(
        building,
        component_id="service_counter",
        width=w * 0.66,
        height=2.0,
        depth=3.2,
        center=(0.0, 0.0, 0.75),
        material=materials["counter"],
        name="Noodle bar service counter",
        tags=("role.interior", "role.furniture"),
    )
    for index, x in enumerate((-w * 0.30, -w * 0.10, w * 0.10, w * 0.30), start=1):
        building = _table(
            building,
            prefix=f"dining_{index}",
            x=x,
            y=-d / 2.0 + 5.0,
            z=0.0,
            materials=materials,
        )
        building = _cylinder(
            building,
            component_id=f"stool_{index}",
            radius=0.8,
            height=1.5,
            center=(x, -d / 2.0 + 2.0, 0.75),
            material=materials["upholstery"],
            name=f"Noodle bar stool {index}",
        )
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="cream", floors=1)
    building = _sign(
        building,
        code=spec.code,
        label="Noodle Bar red street sign",
        width=18.0,
        y=-d / 2.0 - 0.3,
        z=spec.floor_height - 2.0,
        material=materials["sign_red"],
    )
    return building


def _make_game_cafe(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="steel")
    w, d = spec.width, spec.depth
    building = _box(
        building,
        component_id="game_counter",
        width=w * 0.70,
        height=2.0,
        depth=3.0,
        center=(0.0, d / 2.0 - 4.0, 0.75),
        material=materials["counter"],
        name="Game cafe counter",
        tags=("role.interior", "role.furniture"),
    )
    for index, x in enumerate((-10.0, 0.0, 10.0), start=1):
        building = _table(
            building,
            prefix=f"game_table_{index}",
            x=x,
            y=-2.0,
            z=0.0,
            materials=materials,
        )
        building = _box(
            building,
            component_id=f"arcade_{index}",
            width=3.5,
            height=1.0,
            depth=4.0,
            center=(x, 6.0, 0.75),
            material=materials["sign_purple"],
            name=f"Arcade cabinet {index}",
            tags=("role.interior", "role.furniture"),
        )
    building = _sofa(building, prefix="game_lounge", x=0.0, y=-8.0, z=0.0, materials=materials)
    building = _sign(
        building,
        code=spec.code,
        label="Game Cafe purple sign",
        width=16.0,
        y=-d / 2.0 - 0.3,
        z=spec.floor_height - 2.0,
        material=materials["sign_purple"],
    )
    return building


def _make_corner_retail(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="cream")
    w, d, fh = spec.width, spec.depth, spec.floor_height
    building = _box(
        building,
        component_id="checkout",
        width=12.0,
        height=2.0,
        depth=3.0,
        center=(0.0, d / 2.0 - 5.0, 0.75),
        material=materials["counter"],
        name="Retail checkout",
        tags=("role.interior", "role.furniture"),
    )
    for index, x in enumerate((-14.0, -7.0, 7.0, 14.0), start=1):
        building = _box(
            building,
            component_id=f"shelf_{index}",
            width=3.0,
            height=10.0,
            depth=5.0,
            center=(x, 1.0, 0.75),
            material=materials["wood_light"],
            name=f"Retail shelf {index}",
            tags=("role.interior", "role.furniture"),
        )
    building = _stair(
        building,
        x=-w / 2.0 + 6.0,
        y=-d / 2.0 + 4.0,
        z=fh,
        width=4.0,
        floor_height=fh,
        materials=materials,
        prefix="retail_upstairs",
    )
    building = _desk(building, prefix="upstairs_office", x=8.0, y=0.0, z=fh, materials=materials)
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="white")
    building = _sign(
        building,
        code=spec.code,
        label="Corner retail sign",
        width=17.0,
        y=-d / 2.0 - 0.3,
        z=fh - 2.0,
        material=materials["sign_yellow"],
    )
    return building


def _make_office_block(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="concrete")
    for floor in range(spec.floors):
        z = floor * spec.floor_height
        building = _desk(building, prefix=f"office_{floor + 1}_a", x=-12.0, y=-5.0, z=z, materials=materials)
        building = _desk(building, prefix=f"office_{floor + 1}_b", x=0.0, y=-5.0, z=z, materials=materials)
        building = _desk(building, prefix=f"office_{floor + 1}_c", x=12.0, y=6.0, z=z, materials=materials)
        building = _box(
            building,
            component_id=f"meeting_room_{floor + 1}",
            width=12.0,
            height=8.0,
            depth=0.4,
            center=(8.0, 9.0, z + 0.75),
            material=materials["interior_wall"],
            name=f"Office meeting room {floor + 1}",
            tags=("role.interior",),
        )
        building = _table(
            building,
            prefix=f"meeting_table_{floor + 1}",
            x=8.0,
            y=2.0,
            z=z,
            materials=materials,
        )
        building = _stair(
            building,
            x=-spec.width / 2.0 + 6.0,
            y=-spec.depth / 2.0 + 4.0,
            z=z,
            width=4.0,
            floor_height=spec.floor_height,
            materials=materials,
            prefix=f"office_{floor + 1}",
        )
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="glass_light")
    building = _sign(
        building,
        code=spec.code,
        label="Office block sign",
        width=15.0,
        y=-spec.depth / 2.0 - 0.3,
        z=spec.floor_height - 2.0,
        material=materials["glass"],
    )
    return building


def _make_midrise_cafe(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="plaster")
    w, d = spec.width, spec.depth
    building = _box(
        building,
        component_id="cafe_counter",
        width=w * 0.65,
        height=2.0,
        depth=3.0,
        center=(0.0, d / 2.0 - 4.0, 0.75),
        material=materials["counter"],
        name="Mid-rise cafe counter",
        tags=("role.interior", "role.furniture"),
    )
    for index, x in enumerate((-10.0, 0.0, 10.0), start=1):
        building = _table(building, prefix=f"cafe_table_{index}", x=x, y=-5.0, z=0.0, materials=materials)
    for floor in (1, 2):
        z = floor * spec.floor_height
        building = _sofa(building, prefix=f"apartment_{floor}_sofa", x=-8.0, y=-6.0, z=z, materials=materials)
        building = _bed(building, prefix=f"apartment_{floor}_bed", x=8.0, y=5.0, z=z, materials=materials)
        building = _stair(
            building,
            x=-w / 2.0 + 6.0,
            y=-d / 2.0 + 4.0,
            z=z,
            width=4.0,
            floor_height=spec.floor_height,
            materials=materials,
            prefix=f"cafe_{floor}",
        )
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="white")
    building = _sign(
        building,
        code=spec.code,
        label="Cafe awning sign",
        width=16.0,
        y=-d / 2.0 - 0.3,
        z=spec.floor_height - 2.0,
        material=materials["sign_red"],
    )
    return building


def _make_blue_mixed_use(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="steel")
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="glass_light")
    building = _box(
        building,
        component_id="studio_workbench",
        width=spec.width * 0.65,
        height=2.5,
        depth=2.8,
        center=(0.0, 2.0, 0.75),
        material=materials["wood_light"],
        name="Blue building studio workbench",
        tags=("role.interior", "role.furniture"),
    )
    building = _sofa(building, prefix="blue_ground_lounge", x=0.0, y=-7.0, z=0.0, materials=materials)
    building = _desk(building, prefix="blue_upper_desk", x=0.0, y=-4.0, z=spec.floor_height, materials=materials)
    building = _box(
        building,
        component_id="rooftop_hvac",
        width=10.0,
        height=7.0,
        depth=2.8,
        center=(0.0, 6.0, spec.total_height + 0.8),
        material=materials["steel"],
        name="Blue building rooftop HVAC",
        tags=("role.roof",),
    )
    building = _sign(
        building,
        code=spec.code,
        label="Blue mixed-use sign",
        width=12.0,
        y=-spec.depth / 2.0 - 0.3,
        z=spec.floor_height - 2.0,
        material=materials["glass"],
    )
    return building


def _make_small_corner_shop(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    building = _shell(assembly=_new_building(spec=spec), spec=spec, materials=materials, facade="plaster")
    building = _add_window_grid(building, spec=spec, materials=materials, material_key="white")
    for index, x in enumerate((-10.0, 0.0, 10.0), start=1):
        building = _box(
            building,
            component_id=f"shop_rack_{index}",
            width=3.0,
            height=10.0,
            depth=4.2,
            center=(x, 2.0, 0.75),
            material=materials["wood_light"],
            name=f"Corner shop rack {index}",
            tags=("role.interior", "role.furniture"),
        )
    building = _desk(building, prefix="shop_upper_room", x=0.0, y=0.0, z=spec.floor_height, materials=materials)
    building = _sign(
        building,
        code=spec.code,
        label="Small corner shop sign",
        width=14.0,
        y=-spec.depth / 2.0 - 0.3,
        z=spec.floor_height - 2.0,
        material=materials["sign_yellow"],
    )
    return building


def make_building(*, spec: BuildingSpec, materials: dict[str, scad.Material]) -> scad.Assembly:
    """Build one labeled building from the inventory in `dimensions.py`."""

    builders = {
        "glass_tower": _make_glass_tower,
        "brick_residential": _make_brick_residential,
        "noodle_bar": _make_noodle_bar,
        "game_cafe": _make_game_cafe,
        "corner_retail": _make_corner_retail,
        "office_block": _make_office_block,
        "midrise_cafe": _make_midrise_cafe,
        "blue_mixed_use": _make_blue_mixed_use,
        "small_corner_shop": _make_small_corner_shop,
    }
    try:
        building = builders[spec.kind](spec=spec, materials=materials)
    except KeyError as exc:
        raise ValueError(f"unsupported building kind: {spec.kind}") from exc
    ground_assembly(label=f"building_{spec.code}", assembly=building)
    return building
