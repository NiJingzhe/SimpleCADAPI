"""Build, replay, validate, and export the representative weaving machine."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import simplecadapi as scad

from .assembly import MachineBuild, make_representative_machine_assembly
from .common import semantic_signature
from .guide_fixture import GuideFixtureBuild, make_guide_fixture_assembly
from .guide_index_topology import unresolved_guide_topology
from .inventory import TOP_LEVEL_COMPONENT_IDS, Inventory, default_inventory
from .materials import make_guide_materials, make_machine_materials
from .parameters import (
    DetailLevel,
    MachineParameters,
    default_machine_parameters,
    validate_concept_parameters,
    validate_detail_level,
    validate_manufacturing_release,
)


_MACHINE_PREVIEW_GROUPS = {
    "painted_structural_steel_candidate": "role.preview.structure",
    "machined_aluminum_candidate": "role.preview.machined",
    "polished_stainless_candidate": "role.preview.contact",
    "peek_candidate": "role.preview.contact",
    "alumina_candidate": "role.preview.ceramic",
    "uhmw_pe_candidate": "role.preview.contact",
    "drive_envelope_candidate": "role.preview.drive",
    "belt_chain_envelope_candidate": "role.preview.transmission",
    "guard_panel_candidate": "role.preview.guard",
    "segmented_clamp_pad_candidate": "role.preview.clamp",
}


@dataclass(frozen=True)
class ReplayableFixture:
    build: GuideFixtureBuild
    model_json: str
    session_json: str
    model_sha256: str
    replay_signature_equal: bool
    graph_nodes: int


@dataclass(frozen=True)
class ReplayableMachine:
    build: MachineBuild
    replayed_machine: scad.Assembly
    model_json: str
    session_json: str
    model_sha256: str
    replay_signature_equal: bool
    graph_nodes: int


def build_replayable_guide_fixture(
    *,
    parameters: MachineParameters,
    position: float,
    clamp_position: bool = False,
) -> ReplayableFixture:
    validate_concept_parameters(parameters)
    with scad.GraphSession(graph_id="weaving_machine_d1_guide_fixture") as session:
        materials = make_guide_materials()
        build = make_guide_fixture_assembly(
            parameters=parameters,
            materials=materials,
            position=position,
            clamp_position=clamp_position,
        )
        session_json = scad.export_session_json(session=session, indent=2)
        model_json = scad.export_model_json(session=session, indent=2)

    scad.import_model_json(json_str=model_json)
    replayed = scad.replay_model_json(json_str=model_json, strict=True)
    if len(replayed) != 1 or not isinstance(replayed[0], scad.Assembly):
        raise ValueError("strict replay did not return exactly one fixture Assembly")
    original_signature = semantic_signature(build.assembly)
    replay_signature = semantic_signature(replayed[0])
    signature_equal = original_signature == replay_signature
    if not signature_equal:
        raise ValueError("strict replay changed the fixture semantic signature")
    payload = json.loads(model_json)
    digest = hashlib.sha256(model_json.encode("utf-8")).hexdigest()
    print(
        f"strict_replay: outputs=1 signature_equal={signature_equal} "
        f"model_sha256={digest}"
    )
    return ReplayableFixture(
        build=build,
        model_json=model_json,
        session_json=session_json,
        model_sha256=digest,
        replay_signature_equal=signature_equal,
        graph_nodes=len(payload["graph"]["nodes"]),
    )


def build_replayable_representative_machine(
    *,
    parameters: MachineParameters,
    inventory: Inventory,
    detail: DetailLevel,
) -> ReplayableMachine:
    validate_concept_parameters(parameters)
    with scad.GraphSession(
        graph_id="weaving_machine_a00_representative_home"
    ) as session:
        build = make_representative_machine_assembly(
            parameters=parameters,
            materials=make_machine_materials(),
            inventory=inventory,
            detail=detail,
        )
        leaves = session.graph.leaf_nodes()
        if (
            len(leaves) != 1
            or leaves[0].op != "make_solve_assembly_constraints_rassembly"
        ):
            raise ValueError(
                "whole-machine graph must terminate in exactly one solved Assembly"
            )
        session_json = scad.export_session_json(session=session, indent=2)
        model_json = scad.export_model_json(session=session, indent=2)

    scad.import_model_json(json_str=model_json)
    replayed = scad.replay_model_json(json_str=model_json, strict=True)
    if len(replayed) != 1 or not isinstance(replayed[0], scad.Assembly):
        raise ValueError(
            "strict replay did not return exactly one whole-machine Assembly"
        )
    signature_equal = semantic_signature(build.machine) == semantic_signature(
        replayed[0]
    )
    if not signature_equal:
        raise ValueError("strict replay changed the whole-machine semantic signature")
    payload = json.loads(model_json)
    digest = hashlib.sha256(model_json.encode("utf-8")).hexdigest()
    print(
        f"machine_strict_replay: outputs=1 signature_equal={signature_equal} "
        f"model_sha256={digest}"
    )
    return ReplayableMachine(
        build=build,
        replayed_machine=replayed[0],
        model_json=model_json,
        session_json=session_json,
        model_sha256=digest,
        replay_signature_equal=signature_equal,
        graph_nodes=len(payload["graph"]["nodes"]),
    )


def _inventory_payload(inventory: Inventory) -> dict[str, Any]:
    return {
        "schema_version": "weaving-machine-inventory.v1",
        "complete": inventory.complete,
        "unresolved_ids": list(inventory.unresolved_ids),
        "items": [
            {
                "item_id": item.item_id,
                "description": item.description,
                "quantity": item.quantity,
                "status": item.status.value,
                "source": item.source,
            }
            for item in inventory.items
        ],
    }


def _parameter_payload(parameters: MachineParameters) -> dict[str, Any]:
    return {
        name: {
            "value": value.value,
            "unit": value.unit,
            "evidence": value.evidence.value,
            "status": value.status.value,
            "source": value.source,
            "revision": value.revision,
            "external_evidence_id": value.external_evidence_id,
        }
        for name, value in parameters.design_values()
    }


def _fixture_evidence_payload(
    *,
    artifact: ReplayableFixture,
    parameters: MachineParameters,
    inventory: Inventory,
    detail: DetailLevel,
) -> dict[str, Any]:
    topology = unresolved_guide_topology()
    report = scad.inspect_assembly_constraints_rconstraintreport(
        assembly=artifact.build.assembly
    )
    return {
        "schema_version": "weaving-machine-evidence.v1",
        "scope": "D0 guide parts and D1 single-axis non-functional test fixture",
        "detail": detail.value,
        "model_sha256": artifact.model_sha256,
        "parameters": _parameter_payload(parameters),
        "claims": {
            "geometry_constructed": True,
            "strict_replay": artifact.replay_signature_equal,
            "placement_constraints_solved": report.solved,
            "joint_contract_audited": artifact.build.joint_audit.passed,
            "degrees_of_freedom_rank_proven": False,
            "functional_a40_guide_indexing": False,
            "manufacturing_release": False,
            "physical_validation_level": "not_started",
            "digital_maturity": "D1_fixture",
        },
        "guide_topology": {
            "closure": topology.closure.value,
            "block_count": topology.block_count,
        },
        "inventory_complete": inventory.complete,
        "blockers": [
            "GAP-02: guide block count and S0/S1/S2 occupancy are unresolved",
            "GAP-03: the three-state cycle interpretation lacks closure evidence",
            "candidate materials and dimensions lack manufacturing validation",
            "authoritative inventory contains unresolved quantities",
        ],
        "fixture": {
            "requested_position": artifact.build.requested_position,
            "solved_position": artifact.build.solved_position,
            "joint_contract": asdict(artifact.build.joint_contract),
            "joint_audit": asdict(artifact.build.joint_audit),
        },
    }


def _machine_evidence_payload(
    *,
    artifact: ReplayableMachine,
    parameters: MachineParameters,
    inventory: Inventory,
) -> dict[str, Any]:
    topology = unresolved_guide_topology()
    report = scad.inspect_assembly_constraints_rconstraintreport(
        assembly=artifact.build.machine
    )
    return {
        "schema_version": "weaving-machine-evidence.v2",
        "scope": "A00-A90 representative whole machine in HOME configuration",
        "detail": artifact.build.detail.value,
        "pose": "HOME",
        "model_sha256": artifact.model_sha256,
        "parameters": _parameter_payload(parameters),
        "top_level_component_ids": list(TOP_LEVEL_COMPONENT_IDS),
        "claims": {
            "whole_machine_geometry_constructed": True,
            "all_a_level_subsystems_present": tuple(
                artifact.build.machine.component_ids()
            )
            == TOP_LEVEL_COMPONENT_IDS,
            "strict_replay": artifact.replay_signature_equal,
            "placement_constraints_solved": report.solved,
            "all_visible_parts_structurally_supported": (
                artifact.build.structural_support.passed
            ),
            "degrees_of_freedom_rank_proven": False,
            "functional_a40_guide_indexing": False,
            "continuous_motion_clearance_proven": False,
            "manufacturing_release": False,
            "physical_validation_level": "not_started",
            "digital_maturity": "representative_home_geometry",
        },
        "guide_topology": {
            "closure": topology.closure.value,
            "block_count": topology.block_count,
            "displayed_instances_are_authoritative_quantity": False,
        },
        "inventory_complete": inventory.complete,
        "unresolved_inventory_ids": list(inventory.unresolved_ids),
        "structural_support": {
            "passed": artifact.build.structural_support.passed,
            "total_parts": artifact.build.structural_support.total_parts,
            "supported_parts": artifact.build.structural_support.supported_parts,
            "contact_pair_count": artifact.build.structural_support.contact_pair_count,
            "contact_tolerance_mm": artifact.build.structural_support.contact_tolerance,
            "unsupported_paths": [
                list(item.path)
                for item in artifact.build.structural_support.unsupported
            ],
            "support_links": [
                {
                    "path": list(item.path),
                    "supported_by": (
                        list(item.supported_by)
                        if item.supported_by is not None
                        else None
                    ),
                    "contact_gap_mm": item.contact_gap,
                }
                for item in artifact.build.structural_support.support_links
            ],
        },
        "blocked_capabilities": list(artifact.build.blocked_capabilities),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the replayable representative whole weaving machine or its D1 guide fixture."
    )
    parser.add_argument(
        "--target",
        choices=("machine", "fixture"),
        default="machine",
        help="Build the whole machine by default; fixture is an explicit D1 debug target",
    )
    parser.add_argument(
        "--position", type=float, default=6.0, help="Guide Y position in mm"
    )
    parser.add_argument(
        "--clamp-position",
        action="store_true",
        help="Clamp an out-of-range drive to its closed scalar limit",
    )
    parser.add_argument(
        "--detail",
        choices=[item.value for item in DetailLevel],
        default=DetailLevel.REPRESENTATIVE.value,
    )
    parser.add_argument(
        "--manufacturing-gate",
        action="store_true",
        help="Require manufacturing evidence; expected to fail for current proposals",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("examples/out/weaving_machine"),
    )
    parser.add_argument(
        "--stl",
        action="store_true",
        help="Also write a flattened STL preview",
    )
    return parser


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_fixture_outputs(
    *,
    artifact: ReplayableFixture,
    parameters: MachineParameters,
    inventory: Inventory,
    detail: DetailLevel,
    output_dir: Path,
    write_stl: bool,
) -> None:
    preview = scad.make_compound_from_assembly_rcompound(
        assembly=artifact.build.assembly
    )
    model_path = output_dir / "weaving_machine_d1_guide_fixture.model.json"
    session_path = output_dir / "weaving_machine_d1_guide_fixture.session.json"
    step_path = output_dir / "weaving_machine_d1_guide_fixture.step"
    evidence_path = output_dir / "weaving_machine_d1_guide_fixture.evidence.json"
    model_path.write_text(artifact.model_json, encoding="utf-8")
    session_path.write_text(artifact.session_json, encoding="utf-8")
    _write_json(
        evidence_path,
        _fixture_evidence_payload(
            artifact=artifact,
            parameters=parameters,
            inventory=inventory,
            detail=detail,
        ),
    )
    scad.export_step(shapes=preview, filename=str(step_path))
    if write_stl:
        stl_path = output_dir / "weaving_machine_d1_guide_fixture.stl"
        scad.export_stl(shapes=preview, filename=str(stl_path))
        print(f"stl={stl_path}")
    print(f"fixture_position_y={artifact.build.solved_position:.3f}")
    print(f"preview_solids={len(preview.get_solids())}")
    print(f"model={model_path}")
    print(f"session={session_path}")
    print(f"step={step_path}")
    print(f"evidence={evidence_path}")


def _write_machine_outputs(
    *,
    artifact: ReplayableMachine,
    parameters: MachineParameters,
    inventory: Inventory,
    output_dir: Path,
    write_stl: bool,
) -> None:
    preview = scad.make_compound_from_assembly_rcompound(
        assembly=artifact.replayed_machine
    )
    stem = "weaving_machine_a00_representative_home"
    model_path = output_dir / f"{stem}.model.json"
    session_path = output_dir / f"{stem}.session.json"
    step_path = output_dir / f"{stem}.step"
    evidence_path = output_dir / f"{stem}.evidence.json"
    model_path.write_text(artifact.model_json, encoding="utf-8")
    session_path.write_text(artifact.session_json, encoding="utf-8")
    _write_json(
        evidence_path,
        _machine_evidence_payload(
            artifact=artifact,
            parameters=parameters,
            inventory=inventory,
        ),
    )
    scad.export_step(shapes=preview, filename=str(step_path))
    if write_stl:
        stl_path = output_dir / f"{stem}.stl"
        scad.export_stl(shapes=preview, filename=str(stl_path))
        print(f"stl={stl_path}")
    print(f"machine_pose=HOME")
    print(f"top_level_components={len(artifact.build.machine.component_ids())}")
    print(f"preview_solids={len(preview.get_solids())}")
    print(f"model={model_path}")
    print(f"session={session_path}")
    print(f"step={step_path}")
    print(f"evidence={evidence_path}")


def _machine_preview_solids(
    *,
    machine: scad.Assembly,
    preview: scad.Compound,
) -> list[scad.Solid]:
    parts: list[scad.Part] = []

    def collect_parts(item: scad.Part | scad.Assembly) -> None:
        if isinstance(item, scad.Part):
            parts.append(item)
            return
        for component in item.components:
            collect_parts(component.item)

    collect_parts(machine)
    solids = preview.get_solids()
    if not isinstance(solids, list) or len(parts) != len(solids):
        raise ValueError(
            "machine preview material mapping mismatch: "
            f"parts={len(parts)} solids={len(solids) if isinstance(solids, list) else 1}"
        )

    colored: list[scad.Solid] = []
    counts: dict[str, int] = {}
    for part, solid in zip(parts, solids):
        material_id = part.material.material_id if part.material is not None else ""
        tag = _MACHINE_PREVIEW_GROUPS.get(material_id)
        if tag is not None:
            solid = scad.apply_tag(shape=solid, tag=tag)
            counts[tag] = counts.get(tag, 0) + 1
        colored.append(solid)
    print(
        "machine_preview_groups: "
        + ",".join(
            f"{tag.rsplit('.', 1)[-1]}={counts.get(tag, 0)}"
            for tag in sorted(set(_MACHINE_PREVIEW_GROUPS.values()))
        )
    )
    return colored


def _write_machine_previews(
    *,
    artifact: ReplayableMachine,
    output_dir: Path,
) -> None:
    preview = scad.make_compound_from_assembly_rcompound(
        assembly=artifact.replayed_machine
    )
    colored = _machine_preview_solids(
        machine=artifact.replayed_machine,
        preview=preview,
    )
    stem = "weaving_machine_a00_representative_home"
    tags = tuple(dict.fromkeys(_MACHINE_PREVIEW_GROUPS.values()))
    labels = {
        "role.preview.structure": "structural frame",
        "role.preview.machined": "machined mechanisms",
        "role.preview.contact": "wear and yarn-contact parts",
        "role.preview.ceramic": "ceramic guide eyes",
        "role.preview.drive": "motor and drive envelopes",
        "role.preview.transmission": "belts and chains",
        "role.preview.guard": "machine guards",
        "role.preview.clamp": "take-up clamp pads",
    }
    views = (
        ("", "isometric"),
        ("_front", "front"),
        ("_right", "right"),
        ("_top", "top"),
    )
    for suffix, view in views:
        path = output_dir / f"{stem}{suffix}.png"
        scad.render_screenshot_rpath(
            shapes=colored,
            output_path=str(path),
            highlight_tags=tags,
            tag_labels=labels,
            image_size=(1800, 1100),
            view=view,
            show_axes=False,
            show_legend=True,
            show_callouts=False,
            zoom=4.0,
        )
        print(f"preview_{view}={path}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    parameters = default_machine_parameters()
    inventory = default_inventory()
    topology = unresolved_guide_topology()
    detail = DetailLevel(args.detail)
    validate_concept_parameters(parameters)
    validate_detail_level(
        detail=detail,
        topology_closed=topology.closure.value == "closed_with_evidence",
        inventory_complete=inventory.complete,
    )
    if args.manufacturing_gate:
        validate_manufacturing_release(parameters)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "weaving_machine.inventory.json"
    _write_json(inventory_path, _inventory_payload(inventory))
    if args.target == "fixture":
        fixture = build_replayable_guide_fixture(
            parameters=parameters,
            position=args.position,
            clamp_position=args.clamp_position,
        )
        _write_fixture_outputs(
            artifact=fixture,
            parameters=parameters,
            inventory=inventory,
            detail=detail,
            output_dir=output_dir,
            write_stl=args.stl,
        )
        print(f"graph_nodes={fixture.graph_nodes}")
    else:
        machine = build_replayable_representative_machine(
            parameters=parameters,
            inventory=inventory,
            detail=detail,
        )
        _write_machine_outputs(
            artifact=machine,
            parameters=parameters,
            inventory=inventory,
            output_dir=output_dir,
            write_stl=args.stl,
        )
        _write_machine_previews(
            artifact=machine,
            output_dir=output_dir,
        )
        print(f"graph_nodes={machine.graph_nodes}")
    print(f"inventory={inventory_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
