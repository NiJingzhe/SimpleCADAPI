import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src/simplecadapi/auto_tools/make_export.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "simplecadapi_make_export",
    MODULE_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

make_export = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = make_export
MODULE_SPEC.loader.exec_module(make_export)


class TestMakeExportInventory(unittest.TestCase):
    def test_collect_api_inventory_includes_all_supported_modules(self):
        inventory = make_export.collect_api_inventory()

        self.assertIn("make_box_rsolid", inventory["operations"].functions)
        self.assertIn("make_n_hole_flange_rsolid", inventory["evolve"].functions)
        self.assertIn("make_assembly_rassembly", inventory["constraints"].functions)
        self.assertIn("Assembly", inventory["constraints"].classes)
        self.assertIn("make_box_rscalarfield", inventory["field"].functions)
        self.assertIn("select", inventory["ql"].functions)

    def test_generate_init_file_includes_constraints_and_modules(self):
        inventory = make_export.collect_api_inventory()

        content = make_export.generate_init_file(inventory)

        self.assertIn("from .constraints import (", content)
        self.assertIn("from . import field", content)
        self.assertIn("from . import ql", content)
        self.assertIn("create_field_surface = make_field_surface_rsolid", content)
        self.assertIn('"field",', content)
        self.assertIn('"ql",', content)

    def test_target_symbols_include_constraints_and_module_exports(self):
        inventory = make_export.collect_api_inventory()

        symbols = make_export._target_symbols(inventory)

        self.assertIn("make_assembly_rassembly", symbols)
        self.assertIn("Assembly", symbols)
        self.assertIn("field", symbols)
        self.assertIn("ql", symbols)


if __name__ == "__main__":
    unittest.main()
