"""Contract tests shared by product-package translator backends."""

from __future__ import annotations

import importlib
from pathlib import Path
import unittest

import simplecadapi as scad
from simplecadapi.serializer import CANONICAL_OP_SET
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
        backend_dirs = sorted(
            path
            for path in translator_root.glob("*_translator")
            if (path / "__init__.py").is_file()
        )

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

    def test_all_translators_are_reusable_for_product_packages(self):
        cache = scad.CachePolicy(mode="off")

        @scad.part(id="contract_part", cache=cache)
        def build_part() -> scad.Part:
            body = scad.make_box_rsolid(1.0, 2.0, 3.0)
            return scad.make_part_rpart("contract_part", body)

        package = scad.build_product_package(build_part())

        from simplecadapi import translator

        for backend_name in translator.__all__:
            backend = getattr(translator, backend_name)
            translator_class = getattr(
                backend, f"{backend.CAPABILITIES.display_name}Translator"
            )
            instance = translator_class(document_name="ContractTest")
            first = instance.translate_product_package(package)
            second = instance.translate_product_package(package)

            self.assertEqual(first.content, second.content, backend_name)
            self.assertEqual(first.metadata["root_definition_id"], "contract_part")
            self.assertEqual(
                backend.CAPABILITIES.input_schema_versions,
                ("product-package-2.0",),
            )
            compile(first.content, f"<{backend_name}-script>", "exec")

    def test_translator_public_surfaces_do_not_expose_model_json(self):
        from simplecadapi import translator

        for backend_name in translator.__all__:
            backend = getattr(translator, backend_name)
            self.assertFalse(
                any("model_json" in name for name in backend.__all__),
                backend_name,
            )
            self.assertFalse(
                any("ScriptTranslator" in name for name in backend.__all__),
                backend_name,
            )



if __name__ == "__main__":
    unittest.main()
