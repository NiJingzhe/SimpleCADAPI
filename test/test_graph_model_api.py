import json
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import simplecadapi as scad
from simplecadapi.scene import (
    parse_canonical_json,
    preflight_zip_bytes,
    validate_scene_package,
)
from simplecadapi.topology import TopoKind, TopoRef


class TestGraphModelApi(unittest.TestCase):
    def test_model_export_dir_writes_one_self_contained_scene_package(self):
        with TemporaryDirectory() as directory:
            @scad.model(graph_id="auto_export", export_dir=directory)
            def build_model():
                body = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
                scad.capture_result(value=body)
                return body

            result = build_model()
            self.assertEqual(set(result.artifact_paths), {"scene"})
            self.assertTrue(
                all(Path(path).is_file() for path in result.artifact_paths.values())
            )
            self.assertEqual(
                sorted(Path(directory).iterdir()),
                [result.artifact_paths["scene"]],
            )

    def test_model_export_dir_writes_assembly_artifacts_with_model_provenance(self):
        with TemporaryDirectory() as directory:
            @scad.model(graph_id="assembly_export", export_dir=directory)
            def build_model():
                body = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
                part = scad.make_part_rpart(part_id="body", body=body)
                assembly = scad.make_assembly_rassembly(assembly_id="root")
                assembly = scad.add_component_rassembly(
                    assembly=assembly,
                    item=part,
                    component_id="body",
                    placement=scad.identity_placement_rplacement(),
                )
                scad.capture_result(value=assembly)
                return assembly

            result = build_model()
            self.assertEqual(set(result.artifact_paths), {"scene"})
            self.assertTrue(
                all(Path(path).is_file() for path in result.artifact_paths.values())
            )

            archive = preflight_zip_bytes(
                result.artifact_paths["scene"].read_bytes()
            )
            manifest = parse_canonical_json(archive.members["scene.json"])
            blobs = {
                name: payload
                for name, payload in archive.members.items()
                if name != "scene.json"
            }
            report = validate_scene_package(manifest, blobs)
            self.assertTrue(report.valid, report.issues)
            self.assertEqual(manifest["source"]["kind"], "model")
            self.assertIn("model/model.json", archive.members)
            self.assertTrue(manifest["compile_options"]["embed_source"])
            self.assertEqual(
                manifest["source"]["embedded_artifact_uri"],
                "model/model.json",
            )
            source_files = manifest["source"]["source_files"]
            self.assertEqual(
                [record["path"] for record in source_files],
                ["test/test_graph_model_api.py"],
            )
            self.assertEqual(
                archive.members[source_files[0]["uri"]],
                Path(__file__).read_bytes(),
            )
            self.assertFalse(
                any(
                    name.lower().endswith((".step", ".stl", ".fcstd"))
                    for name in archive.members
                )
            )
            self.assertTrue(
                manifest["definitions"]
                and all(
                    item["source"]["kind"] == "product_model"
                    for item in manifest["definitions"]
                )
            )

    def test_model_source_embedding_is_explicit(self):
        @scad.model(graph_id="embedded_source")
        def build_model():
            body = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
            scad.capture_result(value=body)
            return body

        result = build_model()
        package = scad.compile_scene(
            scene_id="embedded_source",
            roots=(scad.SceneRoot(root_id="main", value=result.value),),
            source=result,
            options=scad.SceneCompileOptions(embed_source=True),
        )

        self.assertEqual(
            package.blobs["model/model.json"],
            result.model_json.encode("utf-8"),
        )
        self.assertTrue(package.manifest["compile_options"]["embed_source"])
        self.assertEqual(
            package.manifest["source"]["embedded_artifact_uri"],
            "model/model.json",
        )
        source_files = package.manifest["source"]["source_files"]
        self.assertEqual(
            [record["path"] for record in source_files],
            ["test/test_graph_model_api.py"],
        )
        self.assertEqual(
            package.blobs[source_files[0]["uri"]],
            Path(__file__).read_bytes(),
        )

    def test_model_owns_one_session_and_replays_explicit_result(self):
        @scad.model(graph_id="decorator_model")
        def build_model():
            scad.make_box_rsolid(width=0.5, height=0.5, depth=0.5)
            return scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

        result = build_model()

        self.assertIsInstance(result, scad.ModelResult)
        self.assertEqual(result.session.graph.graph_id, "decorator_model")
        self.assertEqual(len(result.result_node_ids), 1)
        self.assertEqual(result.session.graph.node_count, 2)
        self.assertEqual(len(result.replay()), 1)
        payload = json.loads(result.model_json)
        self.assertEqual(payload["leaf_ids"], list(result.result_node_ids))

    def test_requires_session_reuses_active_session(self):
        @scad.requires_session
        def build_box():
            return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

        with self.assertRaisesRegex(RuntimeError, "requires an active GraphSession"):
            build_box()

        with scad.GraphSession(graph_id="shared") as session:
            box = build_box()

        self.assertEqual(box.get_metadata("graph")["graph_id"], "shared")
        self.assertEqual(session.graph.node_count, 1)

    def test_model_rejects_nested_model_sessions(self):
        @scad.model
        def child_model():
            return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

        @scad.model
        def parent_model():
            return child_model()

        with self.assertRaisesRegex(RuntimeError, "cannot be nested"):
            parent_model()

    def test_capture_result_can_exclude_unrelated_leaf(self):
        @scad.model
        def build_model():
            debug = scad.make_box_rsolid(width=0.25, height=0.25, depth=0.25)
            final = scad.make_box_rsolid(width=2.0, height=2.0, depth=2.0)
            scad.capture_result(value=final)
            return debug, final

        result = build_model()
        payload = json.loads(result.model_json)
        nodes = {node["node_id"]: node for node in payload["graph"]["nodes"]}

        self.assertEqual(payload["leaf_ids"], list(result.result_node_ids))
        self.assertEqual(len(payload["leaf_ids"]), 1)
        self.assertEqual(nodes[payload["leaf_ids"][0]]["params"]["width"], 2.0)

    def test_cross_session_shape_input_is_rejected_at_operation_boundary(self):
        with scad.GraphSession(graph_id="source"):
            foreign = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

        with scad.GraphSession(graph_id="target"):
            with self.assertRaisesRegex(ValueError, "source.*target"):
                scad.translate_shape(shape=foreign, vector=(1.0, 0.0, 0.0))

    def test_cross_session_child_assembly_is_rejected(self):
        with scad.GraphSession(graph_id="child_graph"):
            child = scad.make_assembly_rassembly(assembly_id="child")

        with scad.GraphSession(graph_id="parent_graph"):
            parent = scad.make_assembly_rassembly(assembly_id="parent")
            placement = scad.identity_placement_rplacement()
            with self.assertRaisesRegex(ValueError, "child_graph.*parent_graph"):
                scad.add_component_rassembly(
                    assembly=parent,
                    item=child,
                    component_id="child_1",
                    placement=placement,
                )

    def test_unrecorded_child_assembly_is_rejected(self):
        child = scad.make_assembly_rassembly(assembly_id="unrecorded_child")

        with scad.GraphSession(graph_id="parent_graph"):
            parent = scad.make_assembly_rassembly(assembly_id="parent")
            placement = scad.identity_placement_rplacement()
            with self.assertRaisesRegex(ValueError, "unrecorded Assembly"):
                scad.add_component_rassembly(
                    assembly=parent,
                    item=child,
                    component_id="child_1",
                    placement=placement,
                )

    def test_capture_result_walks_dataclass_values_and_is_atomic_on_failure(self):
        @dataclass
        class ResultValue:
            body: scad.Solid

        @scad.model(graph_id="dataclass_result")
        def build_model():
            body = scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)
            scad.capture_result(value=ResultValue(body=body))
            return ResultValue(body=body)

        result = build_model()
        self.assertEqual(len(result.result_node_ids), 1)
        self.assertEqual(len(result.replay()), 1)

        with scad.GraphSession(graph_id="atomic_capture") as session:
            body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
            with scad.GraphSession(graph_id="foreign_capture"):
                foreign = scad.make_box_rsolid(
                    width=2.0, height=2.0, depth=2.0
                )
            with self.assertRaisesRegex(ValueError, "foreign_capture.*atomic_capture"):
                session.capture_result(value=(body, foreign))
            self.assertFalse(session.has_explicit_results)
            self.assertEqual(session.result_node_ids, ())

        with scad.GraphSession(graph_id="topology_capture") as session:
            body = scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)
            node = body._get_runtime("graph.node")
            body._set_runtime(
                "topo.ref",
                TopoRef(
                    graph_id="foreign_topology",
                    node_id=node.node_id,
                    output_slot=0,
                    kind=TopoKind.SOLID,
                    topo_id="solid_0",
                ),
            )
            with self.assertRaisesRegex(
                ValueError, "foreign_topology.*topology_capture"
            ):
                session.capture_result(value=body)
            self.assertFalse(session.has_explicit_results)
            self.assertEqual(session.result_node_ids, ())

    def test_model_and_requires_session_reject_async_functions(self):
        async def async_model():
            return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

        async def async_builder():
            return scad.make_box_rsolid(width=1.0, height=1.0, depth=1.0)

        with self.assertRaisesRegex(TypeError, "@model does not support async"):
            scad.model(async_model)
        with self.assertRaisesRegex(
            TypeError, "@requires_session does not support async"
        ):
            scad.requires_session(async_builder)


if __name__ == "__main__":
    unittest.main()
