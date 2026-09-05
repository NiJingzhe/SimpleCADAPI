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

    def test_explicit_view_routes_through_the_grid_engine(self):
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
        grid.assert_called_once()
        # 单格：views 参数恰好一条
        self.assertEqual(len(grid.call_args.kwargs["views"]), 1)

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
            # the default is a 4-panel studio grid; rendering the same solid
            # as a single explicit panel must produce a different (non-grid)
            # image at the same size
            single = Path(tmp) / "single.png"
            scad.render_screenshot_rpath(
                solid, str(single), image_size=(800, 600), view="iso"
            )
            self.assertNotEqual(output.read_bytes(), single.read_bytes())

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

    def test_more_than_four_views_are_rejected(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(scad.SimpleCADError):
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "five-views.png"),
                    views=[
                        (30.0, 45.0, "a"),
                        (0.0, 0.0, "b"),
                        (90.0, 0.0, "c"),
                        (0.0, -90.0, "d"),
                        (20.0, 45.0, "e"),
                    ],
                )

    def test_unknown_style_is_rejected(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(scad.SimpleCADError):
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "unknown-style.png"),
                    view="iso",
                    style="cinematic",
                )

    def test_out_of_range_edge_width_scale_is_rejected(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(scad.SimpleCADError):
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "bad-edge-scale.png"),
                    view="iso",
                    style="studio",
                    edge_width_scale=0.5,
                )

    def test_supersample_writes_requested_image_size(self):
        import struct

        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            for supersample, expected in ((1, 1), (2, 1), (3, 1)):
                output = Path(tmp) / f"ss{supersample}.png"
                scad.render_screenshot_rpath(
                    solid,
                    str(output),
                    image_size=(640, 400),
                    view=(30.0, 45.0),
                    show_axes=False,
                    supersample=supersample,
                )
                width, height = struct.unpack(">II", output.read_bytes()[16:24])
                self.assertEqual((width, height), (640, 400))

    def test_out_of_range_supersample_is_rejected(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(scad.SimpleCADError):
                scad.render_screenshot_rpath(
                    solid,
                    str(Path(tmp) / "bad-ss.png"),
                    view="iso",
                    supersample=4,
                )

    def test_default_style_is_studio(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            default = Path(tmp) / "default.png"
            standard = Path(tmp) / "standard.png"
            common = dict(image_size=(320, 240), view="iso")
            scad.render_screenshot_rpath(solid, str(default), **common)
            scad.render_screenshot_rpath(solid, str(standard), style="standard", **common)
            self.assertTrue(default.is_file())
            # 默认（studio）与显式诊断风格必须不同张图
            self.assertNotEqual(default.read_bytes(), standard.read_bytes())

    def test_studio_single_view_render_writes_image(self):
        solid = self._tagged_solid()
        with tempfile.TemporaryDirectory() as tmp:
            standard = Path(tmp) / "standard.png"
            studio = Path(tmp) / "studio.png"
            scad.render_screenshot_rpath(
                solid,
                str(standard),
                image_size=(640, 400),
                view=(30.0, 45.0),
                style="standard",
                show_axes=False,
            )
            scad.render_screenshot_rpath(
                solid,
                str(studio),
                image_size=(640, 400),
                view=(30.0, 45.0),
                style="studio",
                show_axes=False,
            )
            self.assertTrue(studio.is_file())
            # studio must actually change the picture, not just be accepted:
            # lighting, backdrop and tubed edges all differ from the flat
            # inspection look produced by the same view
            self.assertNotEqual(standard.read_bytes(), studio.read_bytes())


if __name__ == "__main__":
    unittest.main()
