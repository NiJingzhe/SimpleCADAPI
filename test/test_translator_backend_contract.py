"""Contract tests shared by translator backends."""

from __future__ import annotations

import importlib
from pathlib import Path
import unittest

import simplecadapi as scad
from simplecadapi.graph import GraphSession
from simplecadapi.serializer import CANONICAL_OP_SET, _canonical_contract_payload
from simplecadapi.translator.base import BaseTranslator
from simplecadapi.translator.freecad_translator import FreeCADTranslator
from simplecadapi.translator.freecad_translator.emitters.registry import (
    EMITTER_METHOD_BY_OP,
)
from simplecadapi.translator.freecad_translator.runtime import (
    assemble_runtime_source,
)
from simplecadapi.translator.types import SupportLevel


class TestTranslatorBackendContract(unittest.TestCase):
    def test_backend_packages_have_required_modules(self):
        translator_root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "simplecadapi"
            / "translator"
        )
        backend_dirs = sorted(translator_root.glob("*_translator"))
        self.assertTrue(backend_dirs)

        for backend_dir in backend_dirs:
            for filename in (
                "__init__.py",
                "api.py",
                "translator.py",
                "capabilities.py",
            ):
                self.assertTrue(
                    (backend_dir / filename).is_file(),
                    f"{backend_dir.name} is missing required {filename}",
                )

    def test_backend_public_exports_and_capabilities_are_valid(self):
        from simplecadapi import translator

        for backend_package_name in translator.__all__:
            backend = importlib.import_module(
                f"simplecadapi.translator.{backend_package_name}"
            )
            for exported_name in backend.__all__:
                self.assertTrue(hasattr(backend, exported_name))

            capabilities = backend.CAPABILITIES
            expected_backend_name = backend_package_name.removesuffix("_translator")
            self.assertEqual(capabilities.backend_id, expected_backend_name)
            self.assertEqual(
                set(capabilities.operations), set(CANONICAL_OP_SET)
            )
            for op, capability in capabilities.operations.items():
                if capability.level is SupportLevel.UNSUPPORTED:
                    self.assertTrue(capability.reason, op)

            translator_class = getattr(
                backend, f"{capabilities.display_name}Translator"
            )
            self.assertTrue(issubclass(translator_class, BaseTranslator))

    def test_freecad_emitter_registry_matches_declared_support(self):
        from simplecadapi.translator.freecad_translator import CAPABILITIES

        self.assertIs(
            CAPABILITIES.operations["apply_tag_rselection"].level,
            SupportLevel.METADATA_ONLY,
        )
        self.assertIs(
            CAPABILITIES.operations["make_twisted_sweep_rsolid"].level,
            SupportLevel.EMULATED,
        )
        supported_ops = {
            op
            for op, capability in CAPABILITIES.operations.items()
            if capability.level is not SupportLevel.UNSUPPORTED
        }
        self.assertEqual(set(EMITTER_METHOD_BY_OP), supported_ops)

    def test_freecad_runtime_fragments_form_valid_python(self):
        runtime_source = assemble_runtime_source()

        self.assertTrue(runtime_source)
        compile(runtime_source, "<freecad-runtime>", "exec")

    def test_freecad_translator_is_reusable_and_emits_valid_python(self):
        with GraphSession() as session:
            scad.make_box_rsolid(1.0, 2.0, 3.0)

        model_json = scad.export_model_json(session)
        translator = FreeCADTranslator(document_name="ContractTest")
        first = translator.translate_model_json_to_script(model_json)
        second = translator.translate_model_json_to_script(model_json)

        self.assertEqual(first, second)
        self.assertIn('DOC_NAME = "ContractTest"', first)
        compile(first, "<generated-freecad-script>", "exec")

    def test_translator_rejects_snapshot_operation_before_backend_emission(self):
        import json

        payload = {
            "schema_version": "2.0",
            "canonical_contract": _canonical_contract_payload(),
            "graph": {
                "schema_version": "2.0",
                "graph_id": "snapshot",
                "nodes": [
                    {
                        "node_id": "n1",
                        "op": "load_brep_region_rsolid",
                        "params": {
                            "path": "body.scadbrep",
                            "sha256": "sha256:" + "0" * 64,
                        },
                        "inputs": [],
                        "output_count": 1,
                        "tags": [],
                    }
                ],
                "edges": [],
            },
            "leaf_ids": ["n1"],
            "expression_graph": {"schema_version": "2.0", "nodes": []},
            "tolerance_graph": {"schema_version": "1.0", "requirements": []},
            "frame_graph": {},
            "geometry_registry": [],
            "semantic_entity_registry": [],
            "sketch_profile_registry": [],
            "semantic_delta_log": [],
            "topology_delta_log": [],
            "semantic_bindings": [],
        }

        with self.assertRaisesRegex(ValueError, "load_brep_region_rsolid"):
            FreeCADTranslator().translate_model_json(json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
