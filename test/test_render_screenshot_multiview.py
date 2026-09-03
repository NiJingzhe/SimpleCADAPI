"""Multi-view screenshot rendering contract tests.

render_screenshot_rpath defaults to a multi-view grid (SCREENSHOT_VIEWS)
carrying highlight-tag groups, callouts, legend and per-panel axis triads;
an explicit ``view`` keeps the legacy single-view path; ``views`` selects a
custom view set.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import simplecadapi as scad
from simplecadapi.inspect.brep import render as brep_render


class TestRenderScreenshotMultiView(unittest.TestCase):
    def _tagged_solid(self):
        box = scad.make_box_rsolid(4.0, 3.0, 2.0)
        return scad.apply_tag(box, "role.body")

    def test_screenshot_views_constant_shape(self):
        views = scad.operators.features.SCREENSHOT_VIEWS
        self.assertEqual(len(views), 4)
        for entry in views:
            self.assertEqual(len(entry), 3)
            self.assertIsInstance(entry[2], str)
        labels = [entry[2] for entry in views]
        self.assertEqual(labels, ["isometric", "top / X-Y", "front / X-Z", "side / Y-Z"])

    def test_default_routes_to_multiview_engine_with_annotations(self):
        solid = self._tagged_solid()
        with mock.patch.object(
            brep_render, "_render_polydata_views", wraps=brep_render._render_polydata_views
        ) as grid:
            with tempfile.TemporaryDirectory() as tmp:
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "default.png"),
                    highlight_tags=["role.body"],
                    tag_labels={"role.body": "Body"},
                    image_size=(640, 480),
                )
        grid.assert_called_once()
        kwargs = grid.call_args.kwargs
        self.assertEqual(
            tuple(kwargs["views"]), scad.operators.features.SCREENSHOT_VIEWS
        )
        self.assertTrue(kwargs["show_axes"])
        self.assertEqual(len(kwargs["highlighted_groups"]), 1)
        self.assertEqual(kwargs["legend"][0][0], "Body")
        self.assertEqual(kwargs["callouts"][0][0], "Body")

    def test_custom_views_reach_the_grid_engine(self):
        solid = self._tagged_solid()
        custom = [(30.0, -60.0, "custom-iso"), (0.0, -90.0, "front")]
        with mock.patch.object(
            brep_render, "_render_polydata_views", wraps=brep_render._render_polydata_views
        ) as grid:
            with tempfile.TemporaryDirectory() as tmp:
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "custom.png"),
                    highlight_tags=["role.body"],
                    image_size=(640, 480),
                    views=custom,
                )
        grid.assert_called_once()
        self.assertEqual(tuple(kwargs_views := grid.call_args.kwargs["views"]), tuple(custom))

    def test_explicit_view_keeps_legacy_single_view_path(self):
        solid = self._tagged_solid()
        with mock.patch.object(
            brep_render, "_render_polydata_views", wraps=brep_render._render_polydata_views
        ) as grid:
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "single.png"
                scad.render_screenshot_rpath(
                    solid,
                    str(output),
                    highlight_tags=["role.body"],
                    image_size=(320, 240),
                    view="iso",
                )
                self.assertTrue(output.is_file())
        grid.assert_not_called()

    def test_real_multiview_render_writes_grid_image(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "real.png"
            result = scad.render_screenshot_rpath(
                solid,
                str(output),
                highlight_tags=["role.body"],
                image_size=(800, 600),
            )
            self.assertEqual(result, str(output))
            self.assertTrue(output.is_file())
            # a 4-panel shaded grid renders substantially more content than a
            # single small view; single-view renders at this size stay < 40 KiB
            self.assertGreater(output.stat().st_size, 40_000)

    def test_real_custom_views_render_writes_image(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "custom_real.png"
            scad.render_screenshot_rpath(
                solid,
                str(output),
                highlight_tags=["role.body"],
                image_size=(800, 600),
                views=[(30.0, -60.0, "custom-iso"), (0.0, -90.0, "front")],
            )
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 20_000)

    def test_empty_views_are_rejected(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(scad.SimpleCADError):
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "empty.png"),
                    views=[],
                )


if __name__ == "__main__":
    unittest.main()
