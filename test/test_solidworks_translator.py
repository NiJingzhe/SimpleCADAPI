"""Host-independent tests for the SolidWorks translator backend."""

from __future__ import annotations

import importlib
import sys
import unittest

import simplecadapi as scad
from simplecadapi import GraphSession
from simplecadapi.translator.errors import TranslationRequestError


def _rectangle_extrusion_model() -> str:
    with GraphSession() as session:
        profile = scad.make_rectangle_rface(width=2.0, height=1.0)
        scad.extrude_rsolid(
            profile=profile,
            direction=(0.0, 0.0, 1.0),
            distance=3.0,
        )
    return scad.export_model_json(session=session)


class TestSolidWorksTranslator(unittest.TestCase):
    def test_backend_imports_without_target_runtime_modules(self):
        before = set(sys.modules)

        solidworks = importlib.import_module(
            "simplecadapi.translator.solidworks_translator"
        )

        self.assertNotIn("pythoncom", set(sys.modules) - before)
        self.assertNotIn("win32com.client", set(sys.modules) - before)
        self.assertEqual(solidworks.CAPABILITIES.backend_id, "solidworks")

    def test_supported_graph_emits_deterministic_compilable_script(self):
        model_json = _rectangle_extrusion_model()
        from simplecadapi.translator.solidworks_translator import SolidWorksTranslator

        translator = SolidWorksTranslator(document_name="ContractSolidWorks")
        first = translator.translate_model_json(model_json)
        second = translator.translate_model_json(model_json)

        self.assertEqual(first.content, second.content)
        compile(first.content, "<solidworks-script>", "exec")
        self.assertFalse(first.metadata["target_runtime_validated"])
        self.assertTrue(translator.capabilities.targets[0].requires_external_runtime)

    def test_fallback_scripts_are_deterministic(self):
        with GraphSession() as session:
            profile = scad.make_rectangle_rface(3.0, 3.0)
            solid = scad.extrude_rsolid(profile, (0.0, 0.0, 1.0), 3.0)
            scad.fillet_rsolid(solid, [solid.get_edges(0)], 0.2)
        model_json = scad.export_model_json(session)

        from simplecadapi.translator.solidworks_translator import SolidWorksTranslator

        translator = SolidWorksTranslator(source_kernel_fallback=True)
        first = translator.translate_model_json(model_json).content
        second = translator.translate_model_json(model_json).content

        self.assertEqual(first, second)
        compile(first, "<solidworks-fallback-script>", "exec")

    def test_script_owns_com_and_only_its_created_document(self):
        from simplecadapi.translator.solidworks_translator import SolidWorksTranslator

        script = (
            SolidWorksTranslator(visible=True)
            .translate_model_json(_rectangle_extrusion_model())
            .content
        )

        main_offset = script.index("def main():")
        coinit_offset = script.index("pythoncom.CoInitialize()", main_offset)
        runtime_offset = script.index(
            "runtime = SimpleCADSolidWorksRuntime", main_offset
        )
        self.assertLess(coinit_offset, runtime_offset)
        self.assertEqual(script.count("pythoncom.CoInitialize()"), 1)
        self.assertIn("self.sw.CloseDoc(str(_maybe_call(self.model.GetTitle)))", script)
        self.assertIn("if not self.visible:", script)
        self.assertIn("self.sw.ExitApp()", script)

    def test_unsupported_result_operation_is_rejected_before_host_execution(self):
        with GraphSession() as session:
            scad.make_box_rsolid(width=1.0, height=2.0, depth=3.0)

        from simplecadapi.translator.solidworks_translator import SolidWorksTranslator

        with self.assertRaises(TranslationRequestError):
            SolidWorksTranslator().translate_model_json(scad.export_model_json(session))


if __name__ == "__main__":
    unittest.main()
