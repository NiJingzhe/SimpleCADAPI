"""Tests for stable public API surface.

The package may add a small number of necessary new APIs for graph/session and
serialization, but internal implementation modules should not be advertised from
the top-level namespace.
"""

import json
import subprocess
import sys
import unittest


class TestPublicApiSurface(unittest.TestCase):
    def test_internal_modules_not_in___all__(self):
        import simplecadapi as scad

        self.assertNotIn("tracking", scad.__all__)
        self.assertNotIn("autotag", scad.__all__)
        self.assertNotIn("topology", scad.__all__)
        self.assertNotIn("graph", scad.__all__)
        self.assertNotIn("serializer", scad.__all__)
        self.assertNotIn("OperationCacheReport", scad.__all__)
        self.assertNotIn("OperationSpec", scad.__all__)
        self.assertNotIn("operation_cache_scope", scad.__all__)
        self.assertFalse(hasattr(scad, "operation_cache_report"))
        self.assertFalse(hasattr(scad, "operation_registry"))

    def test_only_necessary_new_top_level_apis_are_present(self):
        code = """
import json
import simplecadapi as scad
print(json.dumps({
  'has_tracking': hasattr(scad, 'tracking'),
  'has_autotag': hasattr(scad, 'autotag'),
  'has_topology': hasattr(scad, 'topology'),
  'has_graph_module': hasattr(scad, 'graph'),
  'has_serializer_module': hasattr(scad, 'serializer'),
  'has_graph_session': hasattr(scad, 'GraphSession'),
  'has_export_graph_json': hasattr(scad, 'export_graph_json'),
  'has_import_graph_json': hasattr(scad, 'import_graph_json'),
  'has_replay_graph': hasattr(scad, 'replay_graph'),
  'has_apply_tag': hasattr(scad, 'apply_tag'),
  'has_list_tags': hasattr(scad, 'list_tags'),
  'has_set_tag': hasattr(scad, 'set_tag'),
}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(proc.stdout)

        self.assertFalse(payload["has_tracking"])
        self.assertFalse(payload["has_autotag"])
        self.assertFalse(payload["has_topology"])
        self.assertFalse(payload["has_graph_module"])
        self.assertFalse(payload["has_serializer_module"])
        self.assertTrue(payload["has_graph_session"])
        self.assertTrue(payload["has_export_graph_json"])
        self.assertTrue(payload["has_import_graph_json"])
        self.assertTrue(payload["has_replay_graph"])
        self.assertTrue(payload["has_apply_tag"])
        self.assertTrue(payload["has_list_tags"])
        self.assertFalse(payload["has_set_tag"])

    def test_canonical_tagging_exports(self):
        import simplecadapi as scad
        from simplecadapi import operators as operations, tagging

        expected = {
            "apply_tag_rselection": operations.apply_tag_rselection,
            "explain_tag": operations.explain_tag,
            "LineageDerivation": tagging.LineageDerivation,
            "LineagePolicy": tagging.LineagePolicy,
            "TagAttachment": tagging.TagAttachment,
            "TagBinding": tagging.TagBinding,
            "TagBindingScope": tagging.TagBindingScope,
            "TagCertainty": tagging.TagCertainty,
            "TagEvidence": tagging.TagEvidence,
            "TagEvidenceKind": tagging.TagEvidenceKind,
            "TagLifecycle": tagging.TagLifecycle,
            "TagLineageWitness": tagging.TagLineageWitness,
            "TagProducer": tagging.TagProducer,
            "TagProducerKind": tagging.TagProducerKind,
            "TagPropagation": tagging.TagPropagation,
            "TagScope": tagging.TagScope,
            "TagTarget": tagging.TagTarget,
            "TagTargetKind": tagging.TagTargetKind,
            "TopologyPropagation": tagging.TopologyPropagation,
        }

        for name, implementation in expected.items():
            with self.subTest(name=name):
                self.assertIn(name, scad.__all__)
                self.assertIs(getattr(scad, name), implementation)

    def test_tracking_policy_is_public(self):
        import simplecadapi as scad
        from simplecadapi.topology.tracking import TrackingPolicy

        self.assertIn("TrackingPolicy", scad.__all__)
        self.assertIs(scad.TrackingPolicy, TrackingPolicy)

    def test_unified_product_package_exports(self):
        import simplecadapi as scad
        from simplecadapi.product import packages as product_packages

        expected = {
            "PRODUCT_PACKAGE_SCHEMA_VERSION": product_packages.PRODUCT_PACKAGE_SCHEMA_VERSION,
            "ProductPackage": product_packages.ProductPackage,
            "ProductPackageError": product_packages.ProductPackageError,
            "build_product_package": product_packages.build_product_package,
            "encode_product_package": product_packages.encode_product_package,
            "load_product_package": product_packages.load_product_package,
            "read_product_package": product_packages.read_product_package,
            "validate_product_package": product_packages.validate_product_package,
        }
        for name, implementation in expected.items():
            with self.subTest(name=name):
                self.assertIn(name, scad.__all__)
                self.assertIs(getattr(scad, name), implementation)

        for legacy_name in (
            "build_part_package",
            "build_assembly_package",
            "load_part_package",
            "load_assembly_package",
            "export_product_package",
        ):
            with self.subTest(legacy_name=legacy_name):
                self.assertNotIn(legacy_name, scad.__all__)
                self.assertFalse(hasattr(scad, legacy_name))

        self.assertFalse(hasattr(product_packages, "export_product_package"))

    def test_scene_implementation_is_not_top_level_product_api(self):
        import simplecadapi as scad
        from simplecadapi import scene

        internal_scene_names = (
            "CanonicalEdgeBlock",
            "CanonicalTriangleBlock",
            "CompiledScenePackage",
            "ProductSceneError",
            "ProductScenePackage",
            "RenderEdgeMesh",
            "RenderGroup",
            "RenderMesh",
            "SceneCompileOptions",
            "SceneRoot",
            "SceneSource",
            "build_edge_mesh",
            "build_render_mesh",
            "cad_direction_to_gltf",
            "cad_to_gltf",
            "compile_product_scene",
            "compile_scene",
            "encode_product_scene",
            "export_scene",
            "read_scene_package",
            "solid_asset_bounds",
            "validate_product_scene_package",
            "write_line_glb",
            "write_triangle_glb",
        )
        for name in internal_scene_names:
            with self.subTest(name=name):
                self.assertNotIn(name, scad.__all__)
                self.assertFalse(hasattr(scad, name))
                self.assertTrue(hasattr(scene, name))

    def test_unused_brep_inspection_interfaces_are_not_public(self):
        from simplecadapi.inspect import brep

        removed = {
            "compare_boundary_adaptive_rdescriptor",
            "inspect_aligned_sections_rdescriptor",
            "inspect_face_isocurve_network_rdescriptor",
        }
        self.assertTrue(removed.isdisjoint(brep.__all__))
        for name in removed:
            with self.subTest(name=name):
                self.assertFalse(hasattr(brep, name))
