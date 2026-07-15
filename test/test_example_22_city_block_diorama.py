"""Result-set regressions for Example 22 grounding."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import simplecadapi as scad


EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "22_city_block_diorama"


def _load_common_module():
    spec = importlib.util.spec_from_file_location(
        "example_22_common",
        EXAMPLE_DIR / "common.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Example 22 common helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestExample22CityBlockDiorama(unittest.TestCase):
    def test_intermediate_grounding_does_not_add_model_result(self):
        common = _load_common_module()
        with scad.GraphSession(graph_id="example_22_grounding") as session:
            body = scad.make_box_rsolid(width=2.0, height=3.0, depth=4.0)
            part = scad.make_part_rpart(part_id="block", body=body)
            assembly = scad.make_assembly_rassembly(assembly_id="fixture")
            assembly = scad.add_component_rassembly(
                assembly=assembly,
                item=part,
                component_id="block_1",
                placement=scad.identity_placement_rplacement(),
            )
            common.ground_assembly(label="intermediate", assembly=assembly)
            common.ground_assembly(
                label="final",
                assembly=assembly,
                record_result=True,
            )

        payload = json.loads(scad.export_model_json(session=session))
        leaf_nodes = {
            node["node_id"]: node for node in payload["graph"]["nodes"]
        }

        self.assertEqual(len(payload["leaf_ids"]), 1)
        self.assertEqual(
            leaf_nodes[payload["leaf_ids"][0]]["op"],
            "make_compound_from_assembly_rcompound",
        )


if __name__ == "__main__":
    unittest.main()
