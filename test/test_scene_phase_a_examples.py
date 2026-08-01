"""Opt-in Phase A hierarchy characterization for selected large examples."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUN_SLOW_EXAMPLES = os.environ.get("SIMPLECADAPI_RUN_SLOW_SCENE_EXAMPLES") == "1"

EXAMPLE_CASES = (
    (
        "10_part_assembly.py",
        "build_hydraulic_rod_assembly",
        3,
        3,
        2,
    ),
    (
        "16_compact_two_stage_planetary_reducer/main.py",
        "_build_compact_two_stage_planetary_reducer",
        116,
        17,
        15,
    ),
    (
        "20_integrated_bldc_joint_actuator/main.py",
        "build_integrated_bldc_joint_actuator",
        89,
        38,
        29,
    ),
)

_PROBE = r"""
import importlib.util
import json
from pathlib import Path
import sys

import simplecadapi as scad
from simplecadapi.product import Assembly

path = Path(sys.argv[1]).resolve()
builder_name = sys.argv[2]
print(
    f"SCENE_PHASE_A_START={path.name}:{builder_name}",
    flush=True,
)
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location("phase_a_example_probe", path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"could not load example: {path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = getattr(module, builder_name)()
assembly = result.value[0]
if not isinstance(assembly, Assembly):
    raise TypeError(f"{builder_name} did not return an Assembly first")

nodes = []
def walk(item):
    nodes.append(item)
    if isinstance(item, Assembly):
        for component in item.components:
            walk(component.item)

walk(assembly)
definitions = {
    ("assembly", item.assembly_id)
    if isinstance(item, Assembly)
    else ("part", item.part_id)
    for item in nodes
}
part_definitions = {
    item.part_id
    for item in nodes
    if not isinstance(item, Assembly)
}
face_naming = {}
if path.name == "10_part_assembly.py":
    naming_contract = {
        "outer_sleeve": ("sleeve.", "sleeve.gland.face.mount"),
        "piston_rod": ("rod.", "rod.piston.land.left.face.rear"),
    }
    for part_id, (prefix, connector_face_tag) in naming_contract.items():
        part = next(
            item
            for item in nodes
            if not isinstance(item, Assembly) and item.part_id == part_id
        )
        faces = part.body.get_faces()
        face_naming[part_id] = {
            "face_count": len(faces),
            "unnamed_indices": [
                index
                for index, face in enumerate(faces)
                if not any(
                    tag.startswith(prefix)
                    for tag in scad.list_tags(face, scope="local")
                )
            ],
            "connector_face_count": len(
                scad.select_faces_by_tag(
                    part.body,
                    connector_face_tag,
                    scope="local",
                )
            ),
        }
print("SCENE_PHASE_A_FACTS=" + json.dumps({
    "expected_mesh_count": len(part_definitions),
    "face_naming": face_naming,
    "product_node_count": len(nodes),
    "unique_definition_count": len(definitions),
}, sort_keys=True), flush=True)
"""


@pytest.mark.skipif(
    not RUN_SLOW_EXAMPLES,
    reason="set SIMPLECADAPI_RUN_SLOW_SCENE_EXAMPLES=1 to run large examples",
)
@pytest.mark.parametrize(
    (
        "relative_path",
        "builder_name",
        "expected_nodes",
        "expected_definitions",
        "expected_meshes",
    ),
    EXAMPLE_CASES,
    ids=("example_10", "example_16", "example_20"),
)
def test_allowlisted_example_product_hierarchy_in_fresh_process(
    relative_path: str,
    builder_name: str,
    expected_nodes: int,
    expected_definitions: int,
    expected_meshes: int,
):
    path = ROOT / "examples" / relative_path
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = "0"
    label = f"{relative_path}:{builder_name}"
    print(
        f"\n[scene-example] starting {label}; "
        f"expected nodes={expected_nodes}, definitions={expected_definitions}, "
        f"meshes={expected_meshes}",
        flush=True,
    )
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-c", _PROBE, str(path), builder_name],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    output: list[str] = []

    def relay_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            output.append(line)
            print(f"[{relative_path}] {line}", end="", flush=True)

    relay = threading.Thread(target=relay_output, daemon=True)
    relay.start()
    try:
        next_heartbeat = 15.0
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed >= 600:
                process.kill()
                process.wait()
                pytest.fail(f"{label} timed out after {elapsed:.1f}s")
            if elapsed >= next_heartbeat:
                print(
                    f"[scene-example] still building {label}; elapsed={elapsed:.1f}s",
                    flush=True,
                )
                next_heartbeat += 15.0
            time.sleep(0.5)
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.wait()
        raise
    finally:
        relay.join(timeout=5)

    elapsed = time.monotonic() - started
    stdout = "".join(output)
    print(
        f"[scene-example] finished {label}; "
        f"returncode={process.returncode}, elapsed={elapsed:.1f}s",
        flush=True,
    )
    assert process.returncode == 0, stdout
    fact_lines = [
        line.removeprefix("SCENE_PHASE_A_FACTS=")
        for line in stdout.splitlines()
        if line.startswith("SCENE_PHASE_A_FACTS=")
    ]
    assert len(fact_lines) == 1, stdout
    assert json.loads(fact_lines[0]) == {
        "expected_mesh_count": expected_meshes,
        "face_naming": (
            {
                "outer_sleeve": {
                    "connector_face_count": 1,
                    "face_count": 31,
                    "unnamed_indices": [],
                },
                "piston_rod": {
                    "connector_face_count": 1,
                    "face_count": 24,
                    "unnamed_indices": [],
                },
            }
            if relative_path == "10_part_assembly.py"
            else {}
        ),
        "product_node_count": expected_nodes,
        "unique_definition_count": expected_definitions,
    }
