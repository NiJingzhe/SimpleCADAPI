"""Unified durable product capture boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts.assembly_definition import AssemblyDefinition
from .artifacts.assembly_io import materialize_definition
from .artifacts.part_definition import PartDefinition
from .assembly import Assembly
from .part import Part
from .product_packages import (
    ProductPackage,
    build_product_package,
    encode_product_package,
)
from .scene.product_scene import ProductScenePackage, read_scene_package


@dataclass(frozen=True, slots=True)
class CaptureResult:
    """Runtime value plus one complete durable product snapshot."""

    value: Part | Assembly
    definition: PartDefinition | AssemblyDefinition
    package: ProductPackage
    scene: ProductScenePackage
    package_bytes: bytes


def capture(result: Any, path: str | Path, /) -> CaptureResult:
    """Capture a durable product and write its canonical `.scadpkg`."""

    definition = (
        result
        if isinstance(result, (PartDefinition, AssemblyDefinition))
        else getattr(result, "definition", None)
    )
    if not isinstance(definition, (PartDefinition, AssemblyDefinition)):
        raise TypeError(
            "result must be a PartDefinition, AssemblyDefinition, PartBuildResult, "
            "or AssemblyBuildResult"
        )
    runtime = getattr(result, "value", None)
    if runtime is None:
        runtime = materialize_definition(definition)
    if not isinstance(runtime, (Part, Assembly)):
        raise TypeError("captured runtime value must be a Part or Assembly")
    package = build_product_package(definition)
    package_bytes = encode_product_package(package)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(package_bytes)
    scene = read_scene_package(package.scene_bytes)
    return CaptureResult(
        value=runtime,
        definition=definition,
        package=package,
        scene=scene,
        package_bytes=package_bytes,
    )


__all__ = ["CaptureResult", "capture"]
