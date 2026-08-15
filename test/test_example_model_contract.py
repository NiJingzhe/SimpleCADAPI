"""Structural checks for the example model/session contract."""

import runpy
import importlib.util
import sys
from pathlib import Path
import unittest


import simplecadapi as scad

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _source_files() -> tuple[Path, ...]:
    return tuple(
        path
        for path in EXAMPLES.rglob("*.py")
        if "out" not in path.relative_to(EXAMPLES).parts
    )


FORMAL_EXAMPLE_PACKAGES = {
    "examples/04_dimension_tolerance_chain.py": (
        "examples/out/dimension_tolerance_chain/dimension_tolerance_chain.scadpkg"
    ),
    "examples/08_constrained_sketch.py": (
        "examples/out/constrained_sketch/constrained_sketch.scadpkg"
    ),
    "examples/09_naca0016_blade_freecad.py": (
        "examples/out/naca0016_blade/naca0016_blade.scadpkg"
    ),
    "examples/10_part_assembly.py": (
        "examples/out/hydraulic_rod_assembly/hydraulic_rod_assembly.scadpkg"
    ),
    "examples/11_external_reference_gear_train.py": (
        "examples/out/external_reference_gear_train/"
        "nested_external_reference_gear_trains.scadpkg"
    ),
    "examples/12_ap242_gmsh_volume_mesh.py": (
        "examples/out/ap242_gmsh_volume_mesh/ap242_gmsh_bracket.scadpkg"
    ),
    "examples/7ep_caplcd_enclosure.py": (
        "examples/out/7ep_caplcd_enclosure/caplcd_enclosure_7ep.scadpkg"
    ),
    "examples/16_compact_two_stage_planetary_reducer/main.py": (
        "examples/out/compact_two_stage_planetary_reducer/"
        "compact_two_stage_planetary_reducer.scadpkg"
    ),
    "examples/20_integrated_bldc_joint_actuator/main.py": (
        "examples/out/integrated_bldc_joint_actuator/"
        "integrated_bldc_joint_actuator.scadpkg"
    ),
}


class TestExampleModelContract(unittest.TestCase):
    def test_example_10_output_dir_is_anchored_to_the_example_file(self):
        path = EXAMPLES / "10_part_assembly.py"
        spec = importlib.util.spec_from_file_location("example_10_path_contract", path)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(module.OUT_DIR.is_absolute())
        self.assertEqual(
            module.OUT_DIR,
            EXAMPLES / "out" / "hydraulic_rod_assembly",
        )

    def test_every_formal_example_has_one_scadpkg_contract(self):
        runner = runpy.run_path(str(ROOT / "tools" / "run_examples.py"))
        cases = runner["CASES"]
        actual = {case.path: case.package_path for case in cases}

        self.assertEqual(actual, FORMAL_EXAMPLE_PACKAGES)
        self.assertEqual(len(set(actual.values())), len(actual))
        self.assertTrue(all(path.endswith(".scadpkg") for path in actual.values()))
        self.assertTrue(all(case.step_path.endswith(".step") for case in cases))
        self.assertTrue(all(case.fcstd_path.endswith(".FCStd") for case in cases))
        self.assertTrue(
            all(
                Path(case.step_path).stem == Path(case.package_path).stem
                and Path(case.fcstd_path).stem == Path(case.package_path).stem
                for case in cases
            )
        )

    def test_examples_do_not_use_removed_decorator_api(self):
        for path in _source_files():
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("@scad.model", source, path)
            self.assertNotIn("scad.requires_session", source, path)
            self.assertNotIn("scad.capture_result", source, path)

    def test_bldc_bearing_decorative_balls_are_part_of_outer_ring(self):
        example_dir = EXAMPLES / "20_integrated_bldc_joint_actuator"
        sys.path.insert(0, str(example_dir))
        try:
            path = example_dir / "bearings.py"
            spec = importlib.util.spec_from_file_location(
                "bldc_bearings_contract", path
            )
            self.assertIsNotNone(spec)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            from dimensions import BearingSpec

            bearing_spec = BearingSpec(3.0, 6.0, 3.0, 0.7, 8)
            with scad.GraphSession():
                material = scad.make_material_rmaterial(
                    "bearing_contract_steel",
                    density=7.85e-6,
                    density_unit="kg/mm^3",
                )
                bearing = module.make_main_bearing_rassembly(
                    bearing_id="bearing_contract",
                    spec=bearing_spec,
                    material=material,
                )
                solved = scad.solve_assembly_constraints_rassembly(
                    scad.ground_component_rassembly(bearing, "outer_ring")
                )
                report = scad.inspect_assembly_constraints_rconstraintreport(solved)
        finally:
            sys.path.remove(str(example_dir))

        self.assertEqual(bearing.component_ids(), ("outer_ring", "inner_ring"))
        self.assertEqual(bearing.constraint_ids(), ("inner_outer_revolute",))
        self.assertEqual(report.unsolved_component_ids, ())
        outer = bearing.get_component("outer_ring").item.body
        outer_meta = bearing.get_metadata("std.bearing.ball_bearing")
        self.assertTrue(outer_meta["rolling_elements_fused"])
        self.assertEqual(outer_meta["rolling_element_fuse_mode"], "outer_ring_union")
        self.assertGreater(outer.get_volume(), 0.0)
        self.assertIn(
            "role.rolling_elements_fused_into_outer_ring", scad.list_tags(outer)
        )


if __name__ == "__main__":
    unittest.main()
