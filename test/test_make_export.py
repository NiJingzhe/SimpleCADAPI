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
        self.assertIn("apply_tag", inventory["operations"].functions)
        self.assertIn("list_tags", inventory["operations"].functions)
        self.assertNotIn("set_tag", inventory["operations"].functions)
        self.assertIn("make_n_hole_flange_rsolid", inventory["evolve"].functions)
        self.assertNotIn("constraints", inventory)
        self.assertNotIn("field", inventory)
        self.assertIn("select", inventory["ql"].functions)

    def test_generate_init_file_excludes_removed_modules(self):
        inventory = make_export.collect_api_inventory()

        content = make_export.generate_init_file(inventory)

        self.assertNotIn("from .constraints import (", content)
        self.assertIn("from . import ql", content)
        self.assertIn("from . import translator", content)
        self.assertNotIn("create_field_surface", content)
        self.assertIn("make_assembly_rassembly", content)
        self.assertIn("make_part_rpart", content)
        self.assertIn("make_material_rmaterial", content)
        self.assertIn("add_revolute_constraint_rassembly", content)
        self.assertIn("add_gear_constraint_rassembly", content)
        self.assertIn("apply_tag", content)
        self.assertIn("list_tags", content)
        self.assertNotIn("set_tag", content)
        self.assertNotIn('"field",', content)
        self.assertIn('"ql",', content)
        self.assertIn('"translator",', content)

    def test_target_symbols_include_product_semantics_but_exclude_removed_exports(self):
        inventory = make_export.collect_api_inventory()

        symbols = make_export._target_symbols(inventory)

        self.assertIn("make_assembly_rassembly", symbols)
        self.assertIn("make_part_rpart", symbols)
        self.assertIn("make_material_rmaterial", symbols)
        self.assertIn("add_prismatic_constraint_rassembly", symbols)
        self.assertIn("add_rack_pinion_constraint_rassembly", symbols)
        self.assertNotIn("PartHandle", symbols)
        self.assertIn("apply_tag", symbols)
        self.assertIn("list_tags", symbols)
        self.assertNotIn("set_tag", symbols)
        self.assertNotIn("field", symbols)
        self.assertIn("ql", symbols)
        self.assertIn("translator", symbols)


if __name__ == "__main__":
    unittest.main()
