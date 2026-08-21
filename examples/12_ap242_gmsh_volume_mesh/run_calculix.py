"""Run a linear-static CalculiX analysis of the named Gmsh bracket mesh."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable, Sequence

import numpy as np


OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "ap242_gmsh_volume_mesh"
MESH_PATH = OUT_DIR / "ap242_gmsh_bracket.msh"
INPUT_PATH = OUT_DIR / "ap242_gmsh_bracket_static.inp"
SUMMARY_PATH = OUT_DIR / "ap242_gmsh_bracket_static.calculix.json"

FIXED_INTERFACE = "interface.fixed_support"
LOAD_INTERFACE = "interface.load_surface"
MATERIAL_NAME = "ALUMINUM_6061_T6"
YOUNGS_MODULUS_MPA = 68_900.0
POISSON_RATIO = 0.33
DEFAULT_LOAD_Z_N = -1_000.0
LINEAR_SOLVERS = {
    "SPOOLES",
    "ITERATIVE CHOLESKY",
    "ITERATIVE SCALING",
}


@dataclass(frozen=True, slots=True)
class CalculiXInputReport:
    mesh_path: Path
    input_path: Path
    node_count: int
    element_count: int
    fixed_node_count: int
    load_node_count: int
    load_surface_area_mm2: float
    applied_load_z_n: float
    linear_solver: str = "SPOOLES"


@dataclass(frozen=True, slots=True)
class CalculiXRunReport:
    executable: Path
    input_path: Path
    dat_path: Path
    frd_path: Path
    log_path: Path
    summary_path: Path
    max_displacement_mm: float
    max_displacement_node: int
    max_von_mises_mpa: float
    max_von_mises_element: int
    max_von_mises_integration_point: int
    reaction_force_x_n: float
    reaction_force_y_n: float
    reaction_force_z_n: float
    force_balance_z_n: float


@dataclass(frozen=True, slots=True)
class _MeshData:
    nodes: tuple[tuple[int, float, float, float], ...]
    tetrahedra: tuple[tuple[int, int, int, int, int], ...]
    fixed_nodes: tuple[int, ...]
    load_triangles: tuple[tuple[int, int, int], ...]


def _optional_gmsh(gmsh_module: Any | None) -> Any:
    if gmsh_module is not None:
        return gmsh_module
    try:
        return importlib.import_module("gmsh")
    except ImportError as exc:
        raise RuntimeError(
            "CalculiX FEM support is optional; install Python dependencies with "
            "`pip install simplecadapi[fem]`"
        ) from exc


def _physical_group_tag(gmsh: Any, name: str, dimension: int) -> int:
    matches = [
        int(tag)
        for dim, tag in gmsh.model.getPhysicalGroups(dimension)
        if int(dim) == dimension and gmsh.model.getPhysicalName(dim, tag) == name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"mesh must contain exactly one {dimension}D physical group named {name!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _read_gmsh_mesh(mesh_path: Path, gmsh: Any) -> _MeshData:
    initialized = False
    try:
        gmsh.initialize()
        initialized = True
        gmsh.open(str(mesh_path))

        node_tags, coordinates, _parameters = gmsh.model.mesh.getNodes()
        node_ids = [int(tag) for tag in node_tags]
        coordinate_values = np.asarray(coordinates, dtype=float).reshape((-1, 3))
        if not node_ids or len(node_ids) != len(coordinate_values):
            raise ValueError("Gmsh mesh contains no valid three-dimensional nodes")
        nodes = tuple(
            (node_id, float(point[0]), float(point[1]), float(point[2]))
            for node_id, point in zip(node_ids, coordinate_values)
        )

        tetrahedron_type = int(gmsh.model.mesh.getElementType("Tetrahedron", 1))
        volume_types = {int(value) for value in gmsh.model.mesh.getElementTypes(3)}
        if volume_types != {tetrahedron_type}:
            raise ValueError(
                "CalculiX example requires only first-order tetrahedral volume elements; "
                f"found Gmsh types {sorted(volume_types)}"
            )
        element_tags, element_nodes = gmsh.model.mesh.getElementsByType(tetrahedron_type)
        element_ids = [int(tag) for tag in element_tags]
        connectivity = np.asarray(element_nodes, dtype=np.int64).reshape((-1, 4))
        if not element_ids or len(element_ids) != len(connectivity):
            raise ValueError("Gmsh mesh contains no valid first-order tetrahedra")
        tetrahedra = tuple(
            (element_id, *(int(node) for node in element))
            for element_id, element in zip(element_ids, connectivity)
        )

        fixed_tag = _physical_group_tag(gmsh, FIXED_INTERFACE, 2)
        fixed_node_tags, _fixed_coordinates = gmsh.model.mesh.getNodesForPhysicalGroup(
            2, fixed_tag
        )
        fixed_nodes = tuple(sorted({int(tag) for tag in fixed_node_tags}))
        if not fixed_nodes:
            raise ValueError(f"physical group {FIXED_INTERFACE!r} contains no nodes")

        load_tag = _physical_group_tag(gmsh, LOAD_INTERFACE, 2)
        load_entities = gmsh.model.getEntitiesForPhysicalGroup(2, load_tag)
        triangle_type = int(gmsh.model.mesh.getElementType("Triangle", 1))
        triangles: list[tuple[int, int, int]] = []
        for entity_tag in load_entities:
            _triangle_tags, triangle_nodes = gmsh.model.mesh.getElementsByType(
                triangle_type, int(entity_tag)
            )
            values = np.asarray(triangle_nodes, dtype=np.int64).reshape((-1, 3))
            triangles.extend(tuple(int(node) for node in triangle) for triangle in values)
        if not triangles:
            raise ValueError(f"physical group {LOAD_INTERFACE!r} contains no triangles")
        load_triangles = tuple(triangles)
    finally:
        if initialized:
            gmsh.finalize()

    return _MeshData(
        nodes=nodes,
        tetrahedra=tetrahedra,
        fixed_nodes=fixed_nodes,
        load_triangles=load_triangles,
    )


def _append_node_set(lines: list[str], name: str, ids: Sequence[int]) -> None:
    lines.append(f"*NSET,NSET={name}")
    for start in range(0, len(ids), 16):
        lines.append(",".join(str(value) for value in ids[start : start + 16]))


def build_calculix_input(
    mesh_path: str | Path,
    input_path: str | Path,
    *,
    load_z_n: float = DEFAULT_LOAD_Z_N,
    youngs_modulus_mpa: float = YOUNGS_MODULUS_MPA,
    poisson_ratio: float = POISSON_RATIO,
    linear_solver: str = "SPOOLES",
    gmsh_module: Any | None = None,
) -> CalculiXInputReport:
    """Convert the semantic Gmsh mesh into a CalculiX linear-static deck."""

    if not math.isfinite(load_z_n) or load_z_n == 0.0:
        raise ValueError("load_z_n must be finite and nonzero")
    if not math.isfinite(youngs_modulus_mpa) or youngs_modulus_mpa <= 0.0:
        raise ValueError("youngs_modulus_mpa must be positive")
    if not math.isfinite(poisson_ratio) or not (-1.0 < poisson_ratio < 0.5):
        raise ValueError("poisson_ratio must be between -1 and 0.5")
    normalized_solver = linear_solver.strip().upper()
    if normalized_solver not in LINEAR_SOLVERS:
        raise ValueError(
            f"linear_solver must be one of {sorted(LINEAR_SOLVERS)}"
        )

    source = Path(mesh_path).expanduser().resolve()
    destination = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Run export_fem_mesh.py first: {source}")
    mesh = _read_gmsh_mesh(source, _optional_gmsh(gmsh_module))
    coordinates = {
        node_id: np.asarray((x, y, z), dtype=float)
        for node_id, x, y, z in mesh.nodes
    }

    nodal_loads: dict[int, float] = {}
    triangle_areas: list[float] = []
    for triangle in mesh.load_triangles:
        first, second, third = (coordinates[node] for node in triangle)
        area = 0.5 * float(np.linalg.norm(np.cross(second - first, third - first)))
        if area <= 0.0:
            raise ValueError("load surface contains a degenerate triangle")
        triangle_areas.append(area)
    total_area = math.fsum(triangle_areas)
    for triangle, area in zip(mesh.load_triangles, triangle_areas):
        share = load_z_n * area / (3.0 * total_area)
        for node_id in triangle:
            nodal_loads[node_id] = nodal_loads.get(node_id, 0.0) + share

    lines = [
        "*HEADING",
        "SimpleCADAPI ribbed L-bracket linear static analysis",
        "** Consistent units: mm, N, MPa",
        "*NODE,NSET=NALL",
    ]
    lines.extend(
        f"{node_id},{x:.12g},{y:.12g},{z:.12g}"
        for node_id, x, y, z in mesh.nodes
    )
    lines.append("*ELEMENT,TYPE=C3D4,ELSET=EALL")
    lines.extend(
        f"{element_id},{first},{second},{third},{fourth}"
        for element_id, first, second, third, fourth in mesh.tetrahedra
    )
    _append_node_set(lines, "FIXED_SUPPORT", mesh.fixed_nodes)
    _append_node_set(lines, "LOAD_SURFACE", tuple(sorted(nodal_loads)))
    lines.extend(
        [
            f"*MATERIAL,NAME={MATERIAL_NAME}",
            "*ELASTIC",
            f"{youngs_modulus_mpa:.12g},{poisson_ratio:.12g}",
            f"*SOLID SECTION,ELSET=EALL,MATERIAL={MATERIAL_NAME}",
            "*BOUNDARY",
            "FIXED_SUPPORT,1,3",
            "*STEP",
            f"*STATIC,SOLVER={normalized_solver}",
            "*CLOAD",
        ]
    )
    lines.extend(
        f"{node_id},3,{force:.12g}"
        for node_id, force in sorted(nodal_loads.items())
    )
    lines.extend(
        [
            "*NODE PRINT,NSET=NALL",
            "U",
            "*NODE PRINT,NSET=FIXED_SUPPORT,TOTALS=ONLY",
            "RF",
            "*EL PRINT,ELSET=EALL",
            "S",
            "*NODE FILE",
            "U",
            "*EL FILE",
            "S",
            "*END STEP",
        ]
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n", encoding="ascii")
    return CalculiXInputReport(
        mesh_path=source,
        input_path=destination,
        node_count=len(mesh.nodes),
        element_count=len(mesh.tetrahedra),
        fixed_node_count=len(mesh.fixed_nodes),
        load_node_count=len(nodal_loads),
        load_surface_area_mm2=total_area,
        applied_load_z_n=math.fsum(nodal_loads.values()),
        linear_solver=normalized_solver,
    )


_FLOAT_PATTERN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def _numeric_fields(line: str) -> list[float]:
    return [float(value) for value in _FLOAT_PATTERN.findall(line)]


def _von_mises(stress: Sequence[float]) -> float:
    sxx, syy, szz, sxy, sxz, syz = stress
    return math.sqrt(
        0.5 * ((sxx - syy) ** 2 + (syy - szz) ** 2 + (szz - sxx) ** 2)
        + 3.0 * (sxy**2 + sxz**2 + syz**2)
    )


def parse_calculix_dat(path: str | Path) -> dict[str, int | float]:
    """Extract final-step displacement, stress, and support reaction facts."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"CalculiX result file is missing: {source}")
    displacements: list[tuple[float, int]] = []
    stresses: list[tuple[float, int, int]] = []
    reaction_force: tuple[float, float, float] | None = None
    section: str | None = None
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        lowered = line.lower()
        if "displacements (vx,vy,vz)" in lowered:
            section = "displacements"
            displacements = []
            continue
        if "total force (fx,fy,fz) for set fixed_support" in lowered:
            section = "reaction"
            reaction_force = None
            continue
        if "stresses (elem, integ.pnt." in lowered:
            section = "stresses"
            stresses = []
            continue
        values = _numeric_fields(line)
        if section == "displacements" and len(values) == 4:
            node = int(values[0])
            magnitude = math.sqrt(math.fsum(value * value for value in values[1:4]))
            displacements.append((magnitude, node))
        elif section == "stresses" and len(values) >= 8:
            element = int(values[0])
            integration_point = int(values[1])
            stresses.append(
                (_von_mises(values[2:8]), element, integration_point)
            )
        elif section == "reaction" and len(values) == 3:
            reaction_force = (values[0], values[1], values[2])
    if not displacements:
        raise RuntimeError(f"no nodal displacements found in {source}")
    if not stresses:
        raise RuntimeError(f"no integration-point stresses found in {source}")
    if reaction_force is None:
        raise RuntimeError(f"no total support reaction found in {source}")
    displacement, node = max(displacements)
    stress, element, integration_point = max(stresses)
    return {
        "max_displacement_mm": displacement,
        "max_displacement_node": node,
        "max_von_mises_mpa": stress,
        "max_von_mises_element": element,
        "max_von_mises_integration_point": integration_point,
        "reaction_force_x_n": reaction_force[0],
        "reaction_force_y_n": reaction_force[1],
        "reaction_force_z_n": reaction_force[2],
    }

def _ccx_version_key(path: Path) -> tuple[int, ...]:
    values = tuple(int(value) for value in re.findall(r"\d+", path.name))
    return values or (0,)


def resolve_calculix_executable(explicit: str | Path | None = None) -> Path:
    """Resolve --ccx, CALCULIX_BIN, unversioned ccx, then versioned ccx_* binaries."""

    requested = str(explicit) if explicit is not None else os.environ.get("CALCULIX_BIN")
    if requested:
        candidate = Path(requested).expanduser()
        resolved = Path(shutil.which(str(candidate)) or candidate).resolve()
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return resolved
        raise FileNotFoundError(f"CalculiX executable is not runnable: {requested}")
    unversioned = shutil.which("ccx")
    if unversioned:
        return Path(unversioned).resolve()
    versioned: list[Path] = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if directory:
            versioned.extend(Path(directory).glob("ccx_*"))
    runnable = {
        path.resolve()
        for path in versioned
        if path.is_file() and os.access(path, os.X_OK)
    }
    if runnable:
        return max(runnable, key=_ccx_version_key)
    raise FileNotFoundError(
        "CalculiX solver not found. On macOS run "
        "`brew install costerwi/homebrew-calculix/calculix-ccx`, then pass "
        "`--ccx $(brew --prefix calculix-ccx)/bin/ccx_2.23` or set CALCULIX_BIN."
    )


def run_calculix_static(
    input_report: CalculiXInputReport,
    *,
    ccx: str | Path | None = None,
    summary_path: str | Path | None = None,
    timeout_seconds: float = 300.0,
    runner: Callable[..., Any] = subprocess.run,
) -> CalculiXRunReport:
    """Execute ccx for one prepared deck and summarize its final static result."""

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0:
        raise ValueError("timeout_seconds must be positive")
    executable = resolve_calculix_executable(ccx)
    source = input_report.input_path.resolve()
    destination = (
        Path(summary_path).expanduser().resolve()
        if summary_path is not None
        else source.with_suffix(".calculix.json")
    )
    completed = runner(
        [str(executable), source.stem],
        cwd=source.parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout_seconds,
    )
    log_path = source.with_suffix(".ccx.log")
    log_path.write_text(
        (completed.stdout or "")
        + ("\n" if completed.stdout and completed.stderr else "")
        + (completed.stderr or ""),
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"CalculiX exited with status {completed.returncode}; see {log_path}"
        )
    dat_path = source.with_suffix(".dat")
    frd_path = source.with_suffix(".frd")
    if not frd_path.is_file() or frd_path.stat().st_size <= 0:
        raise RuntimeError(f"CalculiX did not create a non-empty FRD result: {frd_path}")
    maxima = parse_calculix_dat(dat_path)
    maxima["force_balance_z_n"] = (
        float(maxima["reaction_force_z_n"]) + input_report.applied_load_z_n
    )
    payload = {
        "schema_version": "1.0",
        "analysis": "linear_static",
        "units": {"length": "mm", "force": "N", "stress": "MPa"},
        "material": {
            "name": MATERIAL_NAME,
            "youngs_modulus_mpa": YOUNGS_MODULUS_MPA,
            "poisson_ratio": POISSON_RATIO,
        },
        "input": {
            "mesh_path": str(input_report.mesh_path),
            "input_path": str(input_report.input_path),
            "node_count": input_report.node_count,
            "element_count": input_report.element_count,
            "fixed_node_count": input_report.fixed_node_count,
            "load_node_count": input_report.load_node_count,
            "load_surface_area_mm2": input_report.load_surface_area_mm2,
            "applied_load_z_n": input_report.applied_load_z_n,
            "linear_solver": input_report.linear_solver,
        },
        "results": maxima,
        "artifacts": {
            "dat": str(dat_path),
            "frd": str(frd_path),
            "log": str(log_path),
        },
        "solver": str(executable),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return CalculiXRunReport(
        executable=executable,
        input_path=source,
        dat_path=dat_path,
        frd_path=frd_path,
        log_path=log_path,
        summary_path=destination,
        **maxima,
    )


def main(
    *,
    mesh_path: Path = MESH_PATH,
    input_path: Path = INPUT_PATH,
    summary_path: Path = SUMMARY_PATH,
    load_z_n: float = DEFAULT_LOAD_Z_N,
    ccx: str | None = None,
    prepare_only: bool = False,
    timeout_seconds: float = 300.0,
    linear_solver: str = "SPOOLES",
) -> None:
    input_report = build_calculix_input(
        mesh_path,
        input_path,
        load_z_n=load_z_n,
        linear_solver=linear_solver,
    )
    print("calculix_input", input_report.input_path)
    print("calculix_nodes", input_report.node_count)
    print("calculix_elements", input_report.element_count)
    print("calculix_fixed_nodes", input_report.fixed_node_count)
    print("calculix_load_nodes", input_report.load_node_count)
    print("calculix_load_z_n", f"{input_report.applied_load_z_n:.9g}")
    print("calculix_linear_solver", input_report.linear_solver)
    if prepare_only:
        return
    report = run_calculix_static(
        input_report,
        ccx=ccx,
        summary_path=summary_path,
        timeout_seconds=timeout_seconds,
    )
    print("calculix_frd", report.frd_path)
    print("calculix_summary", report.summary_path)
    print("max_displacement_mm", f"{report.max_displacement_mm:.9g}")
    print("max_von_mises_mpa", f"{report.max_von_mises_mpa:.9g}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, default=MESH_PATH)
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--load-z", type=float, default=DEFAULT_LOAD_Z_N)
    parser.add_argument("--ccx")
    parser.add_argument("--linear-solver", default="SPOOLES")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--timeout", type=float, default=300.0)
    arguments = parser.parse_args()
    main(
        mesh_path=arguments.mesh,
        input_path=arguments.input,
        summary_path=arguments.summary,
        load_z_n=arguments.load_z,
        ccx=arguments.ccx,
        linear_solver=arguments.linear_solver,
        prepare_only=arguments.prepare_only,
        timeout_seconds=arguments.timeout,
    )
