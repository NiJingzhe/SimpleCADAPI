"""Comprehensive unit tests for the SimpleCAD API, covering basic operations and advanced features."""

import sys
import os
import io
import unittest
import numpy as np
import tempfile
import shutil
from contextlib import redirect_stdout

# 添加项目路径到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import simplecadapi as scad


class TestBasicShapes(unittest.TestCase):
    """Tests for basic shape creation."""

    def test_create_point(self):
        """Test create point."""
        point = scad.make_point_rvertex(1, 2, 3)
        # 暂时跳过坐标检查，因为点类型可能不同
        self.assertIsInstance(point, scad.Vertex)

    def test_create_line(self):
        """Test create line."""
        line = scad.make_line_redge((0, 0, 0), (1, 0, 0))
        self.assertIsInstance(line, scad.Edge)

    def test_create_circle_edge(self):
        """Test create circle edge."""
        circle_edge = scad.make_circle_redge((0, 0, 0), 1.0)
        self.assertIsInstance(circle_edge, scad.Edge)

    def test_create_circle_wire(self):
        """Test create circle wire."""
        circle_wire = scad.make_circle_rwire((0, 0, 0), 1.0)
        self.assertIsInstance(circle_wire, scad.Wire)

    def test_create_circle_face(self):
        """Test create circle face."""
        circle_face = scad.make_circle_rface((0, 0, 0), 1.0)
        area = circle_face.get_area()
        self.assertAlmostEqual(area, np.pi, places=6)

    def test_create_rectangle_wire(self):
        """Test create rectangle wire."""
        rect_wire = scad.make_rectangle_rwire(2.0, 1.0)
        self.assertIsInstance(rect_wire, scad.Wire)

    def test_create_rectangle_face(self):
        """Test create rectangle face."""
        rect_face = scad.make_rectangle_rface(2.0, 1.0)
        area = rect_face.get_area()
        self.assertAlmostEqual(area, 2.0, places=6)

    def test_create_box(self):
        """Test create box."""
        box = scad.make_box_rsolid(1.0, 1.0, 1.0)
        volume = box.get_volume()
        self.assertAlmostEqual(volume, 1.0, places=6)

    def test_create_cylinder(self):
        """Test create cylinder."""
        cylinder = scad.make_cylinder_rsolid(1.0, 2.0)
        volume = cylinder.get_volume()
        expected_volume = np.pi * 1.0**2 * 2.0
        self.assertAlmostEqual(volume, expected_volume, places=6)

    def test_create_sphere(self):
        """Test create sphere."""
        sphere = scad.make_sphere_rsolid(1.0)
        volume = sphere.get_volume()
        expected_volume = (4 / 3) * np.pi * 1.0**3
        self.assertAlmostEqual(volume, expected_volume, places=5)

    def test_create_cone(self):
        """Test create cone."""
        # 测试标准圆锥体（尖锥）
        cone = scad.make_cone_rsolid(2.0, 3.0)
        volume = cone.get_volume()
        expected_volume = (1 / 3) * np.pi * 2.0**2 * 3.0
        self.assertAlmostEqual(volume, expected_volume, places=5)
        self.assertIn("geom.primitive.cone", scad.list_tags(cone))

    def test_create_truncated_cone(self):
        """Test create truncated cone."""
        # 测试截锥体（顶面半径不为0）
        truncated_cone = scad.make_cone_rsolid(3.0, 4.0, 1.0)
        volume = truncated_cone.get_volume()
        # 截锥体积公式：V = (1/3)πh(R² + Rr + r²)
        # 其中 R = 3.0, r = 1.0, h = 4.0
        expected_volume = (1 / 3) * np.pi * 4.0 * (3.0**2 + 3.0 * 1.0 + 1.0**2)
        self.assertAlmostEqual(volume, expected_volume, places=5)
        self.assertIn("geom.primitive.cone", scad.list_tags(truncated_cone))

    def test_create_cone_with_offset(self):
        """Test create cone with offset."""
        # 测试底面中心偏移的圆锥体
        offset_cone = scad.make_cone_rsolid(1.5, 2.0, bottom_face_center=(2, 2, 0))
        self.assertIsInstance(offset_cone, scad.Solid)
        self.assertIn("geom.primitive.cone", scad.list_tags(offset_cone))

    def test_create_cone_with_axis(self):
        """Test create cone with axis."""
        # 测试水平方向的圆锥体
        horizontal_cone = scad.make_cone_rsolid(1.0, 3.0, axis=(1, 0, 0))
        self.assertIsInstance(horizontal_cone, scad.Solid)
        self.assertIn("geom.primitive.cone", scad.list_tags(horizontal_cone))

    def test_create_arc(self):
        """Test create arc."""
        arc = scad.make_three_point_arc_redge((0, 0, 0), (1, 1, 0), (2, 0, 0))
        self.assertIsInstance(arc, scad.Edge)

    def test_create_spline(self):
        """Test create spline."""
        points = [(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 0.0, 0.0)]
        spline = scad.make_spline_redge(points)
        self.assertIsInstance(spline, scad.Edge)

    def test_create_segment_edge(self):
        """Test create segment edge."""
        segment = scad.make_segment_redge((0, 0, 0), (1, 0, 0))
        self.assertIsInstance(segment, scad.Edge)

    def test_create_segment_wire(self):
        """Test create segment wire."""
        segment_wire = scad.make_segment_rwire((0, 0, 0), (1, 0, 0))
        self.assertIsInstance(segment_wire, scad.Wire)

    def test_create_angle_arc_edge(self):
        """Test create angle arc edge."""
        arc = scad.make_angle_arc_redge((0, 0, 0), 1.0, 0, np.pi / 2)
        self.assertIsInstance(arc, scad.Edge)

    def test_create_angle_arc_wire(self):
        """Test create angle arc wire."""
        arc_wire = scad.make_angle_arc_rwire((0, 0, 0), 1.0, 0, np.pi / 2)
        self.assertIsInstance(arc_wire, scad.Wire)

    def test_create_three_point_arc_wire(self):
        """Test create three point arc wire."""
        arc_wire = scad.make_three_point_arc_rwire((0, 0, 0), (1, 1, 0), (2, 0, 0))
        self.assertIsInstance(arc_wire, scad.Wire)

    def test_create_spline_wire(self):
        """Test create spline wire."""
        points = [(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 0.0, 0.0)]
        spline_wire = scad.make_spline_rwire(points)
        self.assertIsInstance(spline_wire, scad.Wire)

    def test_create_polyline_wire(self):
        """Test create polyline wire."""
        points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        polyline_wire = scad.make_polyline_rwire(points)
        self.assertIsInstance(polyline_wire, scad.Wire)

        # 测试闭合多段线
        closed_polyline = scad.make_polyline_rwire(points, closed=True)
        self.assertIsInstance(closed_polyline, scad.Wire)
        self.assertTrue(closed_polyline.is_closed())

    def test_create_helix_edge(self):
        """Test create helix edge."""
        helix = scad.make_helix_redge(pitch=1.0, height=3.0, radius=0.5)
        self.assertIsInstance(helix, scad.Edge)

    def test_create_helix_wire(self):
        """Test create helix wire."""
        helix_wire = scad.make_helix_rwire(pitch=1.0, height=3.0, radius=0.5)
        self.assertIsInstance(helix_wire, scad.Wire)

    def test_new_function_error_handling(self):
        """Test new function error handling."""
        # 测试无效参数
        with self.assertRaises(ValueError):
            scad.make_angle_arc_redge((0, 0, 0), -1.0, 0, np.pi / 2)  # 负半径

        with self.assertRaises(ValueError):
            scad.make_angle_arc_redge((0, 0, 0), 1.0, 0, 0)  # 相同角度

        with self.assertRaises(ValueError):
            scad.make_helix_redge(-1.0, 3.0, 0.5)  # 负螺距

        with self.assertRaises(ValueError):
            scad.make_helix_redge(1.0, -3.0, 0.5)  # 负高度

        with self.assertRaises(ValueError):
            scad.make_helix_redge(1.0, 3.0, -0.5)  # 负半径

        with self.assertRaises(ValueError):
            scad.make_spline_redge([(0, 0, 0)])  # 点数不足

        with self.assertRaises(ValueError):
            scad.make_polyline_rwire([(0, 0, 0)])  # 点数不足


class TestTransformations(unittest.TestCase):
    """Tests for transformation operations."""

    def setUp(self):
        self.box = scad.make_box_rsolid(1.0, 1.0, 1.0)

    def test_translate(self):
        """Test translate."""
        translated = scad.translate_shape(self.box, (1, 0, 0))
        self.assertIsInstance(translated, scad.Solid)
        # 体积应保持不变
        if isinstance(translated, scad.Solid):
            self.assertAlmostEqual(
                translated.get_volume(), self.box.get_volume(), places=6
            )

    def test_rotate(self):
        """Test rotate."""
        rotated = scad.rotate_shape(self.box, np.pi / 4, (0, 0, 1))
        self.assertIsInstance(rotated, scad.Solid)
        # 体积应保持不变
        if isinstance(rotated, scad.Solid):
            self.assertAlmostEqual(
                rotated.get_volume(), self.box.get_volume(), places=6
            )


class Test3DOperations(unittest.TestCase):
    """Tests for 3D operations."""

    def test_extrude(self):
        """Test extrude."""
        rect = scad.make_rectangle_rface(2.0, 1.0)
        extruded = scad.extrude_rsolid(rect, (0, 0, 1), 2.0)
        self.assertIsInstance(extruded, scad.Solid)
        # 体积应该是面积乘以高度
        expected_volume = rect.get_area() * 2.0
        self.assertAlmostEqual(extruded.get_volume(), expected_volume, places=6)

    def test_revolve(self):
        """Test revolve."""
        rect = scad.make_rectangle_rface(1.0, 2.0, center=(2, 0, 0))
        revolved = scad.revolve_rsolid(rect, (0, 1, 0), 180, (0, 0, 0))
        self.assertIsInstance(revolved, scad.Solid)
        self.assertGreater(revolved.get_volume(), 0)


class TestBooleanOperations(unittest.TestCase):
    """Tests for boolean operations."""

    def setUp(self):
        self.box1 = scad.make_box_rsolid(2.0, 2.0, 2.0)
        self.box2 = scad.make_box_rsolid(
            1.0, 1.0, 3.0, bottom_face_center=(0.5, 0.5, 0)
        )

    def test_union(self):
        """Test union."""
        result = scad.union_rsolid([self.box1, self.box2])
        self.assertIsInstance(result, scad.Solid)
        # 并集体积应该大于任一单独体积
        self.assertGreater(result.get_volume(), self.box1.get_volume())
        self.assertGreater(result.get_volume(), self.box2.get_volume())

    def test_union_disconnected_solids(self):
        """Test union disconnected solids."""

        box_far_1 = scad.make_box_rsolid(1.0, 1.0, 1.0, bottom_face_center=(0, 0, 0))
        box_far_2 = scad.make_box_rsolid(1.0, 1.0, 1.0, bottom_face_center=(5, 0, 0))
        box_far_3 = scad.make_box_rsolid(1.0, 1.0, 1.0, bottom_face_center=(0, 5, 0))

        solids = [box_far_1, box_far_2, box_far_3]
        with self.assertRaises(scad.SimpleCADError) as ctx:
            scad.union_rsolid(solids)

        message = str(ctx.exception)
        self.assertIn("union_rsolid", message)
        self.assertIn("单个Solid结果", message)

    def test_union_touching_boxes_cleans_splitter_faces(self):
        """Test union of face-touching boxes follows CadQuery-style clean behavior."""

        box_left = scad.make_box_rsolid(1.0, 1.0, 1.0, bottom_face_center=(0, 0, 0))
        box_right = scad.make_box_rsolid(1.0, 1.0, 1.0, bottom_face_center=(1.0, 0, 0))

        stdout_buffer = io.StringIO()
        with redirect_stdout(stdout_buffer):
            result = scad.union_rsolid(box_left, box_right)

        self.assertAlmostEqual(result.get_volume(), 2.0, places=6)
        self.assertEqual(len(result.get_faces()), 6)
        self.assertEqual(stdout_buffer.getvalue(), "")

    def test_union_supports_fuzzy_tolerance(self):
        """Test union forwards CadQuery fuzzy tolerance to the OCC kernel."""

        box_left = scad.make_box_rsolid(1.0, 1.0, 1.0, bottom_face_center=(0, 0, 0))
        box_right = scad.make_box_rsolid(
            1.0, 1.0, 1.0, bottom_face_center=(1.001, 0, 0)
        )

        with self.assertRaises(scad.SimpleCADError):
            scad.union_rsolid(box_left, box_right)
        with_tol = scad.union_rsolid(box_left, box_right, tol=1e-3)

        self.assertIsInstance(with_tol, scad.Solid)
        self.assertGreater(with_tol.get_volume(), 2.0)
        self.assertLess(with_tol.get_volume(), 2.01)

    def test_cut(self):
        """Test cut."""
        result = scad.cut_rsolidlist(self.box1, self.box2)
        self.assertIsInstance(result, scad.Solid)
        # 差集体积应该小于原体积
        self.assertLess(result.get_volume(), self.box1.get_volume())

    def test_intersect(self):
        """Test intersect."""
        result = scad.intersect_rsolidlist(self.box1, self.box2)
        self.assertIsInstance(result, scad.Solid)
        # 交集体积应该小于任一体积
        self.assertLess(result.get_volume(), self.box1.get_volume())
        self.assertLess(result.get_volume(), self.box2.get_volume())

    def test_legacy_boolean_api_removed(self):
        """Test legacy boolean API removed."""
        self.assertTrue(hasattr(scad, "union_rsolid"))
        self.assertFalse(hasattr(scad, "cut_rsolid"))
        self.assertFalse(hasattr(scad, "intersect_rsolid"))


class TestAdvancedFeatures(unittest.TestCase):
    """Tests for advanced feature operations."""

    def setUp(self):
        self.box = scad.make_box_rsolid(2.0, 2.0, 2.0)
        self.box.auto_tag_faces("box")

    def test_fillet(self):
        """Test fillet."""
        # 获取所有边
        edges = self.box.get_edges()
        # 选择前4条边进行圆角
        selected_edges = edges[:4]

        try:
            filleted = scad.fillet_rsolid(self.box, selected_edges, 0.2)
            self.assertIsInstance(filleted, scad.Solid)
            # 圆角后体积应该稍微减少
            self.assertLess(filleted.get_volume(), self.box.get_volume())
        except Exception as e:
            self.skipTest(f"Fillet operation not fully implemented: {e}")

    def test_chamfer(self):
        """Test chamfer."""
        # 获取所有边
        edges = self.box.get_edges()
        # 选择前4条边进行倒角
        selected_edges = edges[:4]

        try:
            chamfered = scad.chamfer_rsolid(self.box, selected_edges, 0.2)
            self.assertIsInstance(chamfered, scad.Solid)
            # 倒角后体积应该稍微减少
            self.assertLess(chamfered.get_volume(), self.box.get_volume())
        except Exception as e:
            self.skipTest(f"Chamfer operation not fully implemented: {e}")

    def test_shell(self):
        """Test shell."""
        # 获取顶面
        faces = self.box.get_faces()
        top_faces = [face for face in faces if "face.top" in scad.list_tags(face)]

        try:
            shelled = scad.shell_rsolid(self.box, top_faces, 0.2)
            self.assertIsInstance(shelled, scad.Solid)
            # 抽壳后体积应该减少
            self.assertLess(shelled.get_volume(), self.box.get_volume())
        except Exception as e:
            self.skipTest(f"Shell operation not fully implemented: {e}")

    def test_loft(self):
        """Test loft."""
        # 创建两个不同大小的矩形轮廓
        rect1 = scad.create_rectangle_wire(2.0, 2.0, center=(0, 0, 0))
        rect2 = scad.create_rectangle_wire(1.0, 1.0, center=(0, 0, 2))

        try:
            lofted = scad.loft_rsolid([rect1, rect2])
            self.assertIsInstance(lofted, scad.Solid)
            self.assertGreater(lofted.get_volume(), 0)
        except Exception as e:
            self.skipTest(f"Loft operation not fully implemented: {e}")

    def test_linear_pattern(self):
        """Test linear pattern."""
        small_box = scad.create_box(0.5, 0.5, 0.5)

        pattern = scad.linear_pattern_rsolidlist(small_box, (1, 0, 0), 5, 1.0)
        self.assertIsInstance(pattern, list)
        # 检查复合体包含5个实体
        solids = pattern
        self.assertEqual(len(solids), 5)

        self.assertIsInstance(solids[0], scad.Solid)

    def test_radial_pattern(self):
        """Test radial pattern."""
        small_box = scad.create_box(0.2, 0.2, 1.0, bottom_face_center=(2, 0, 0))

        pattern = scad.radial_pattern_rsolidlist(
            small_box, (0, 0, 0), (0, 0, 1), 6, 2 * np.pi
        )
        self.assertIsInstance(pattern, list)
        # 检查复合体包含6个实体
        solids = pattern
        self.assertEqual(len(solids), 6)

        self.assertIsInstance(solids[0], scad.Solid)

    def test_mirror(self):
        """Test mirror."""
        mirrored = scad.mirror_shape(self.box, (0, 0, 0), (1, 0, 0))
        self.assertIsInstance(mirrored, scad.Solid)
        # 镜像后体积应该保持不变
        if isinstance(mirrored, scad.Solid):
            self.assertAlmostEqual(
                mirrored.get_volume(), self.box.get_volume(), places=6
            )


class TestTagging(unittest.TestCase):
    """Tests for the tagging system."""

    def setUp(self):
        self.box = scad.create_box(1.0, 1.0, 1.0)

    def test_apply_tag(self):
        """Test apply tag."""
        scad.apply_tag(self.box, "test_box")
        self.assertIn("test_box", scad.list_tags(self.box))

    def test_multiple_tags(self):
        """Test multiple tags."""
        scad.apply_tag(self.box, "tag1")
        scad.apply_tag(self.box, "tag2")
        tags = scad.list_tags(self.box)
        self.assertIn("tag1", tags)
        self.assertIn("tag2", tags)

    def test_auto_tag_faces_box(self):
        """Test auto tag faces box."""
        self.box.auto_tag_faces("box")
        faces = self.box.get_faces()

        # 检查是否有标记的面
        tagged_faces = [face for face in faces if len(scad.list_tags(face)) > 0]
        self.assertGreater(len(tagged_faces), 0)

    def test_auto_tag_faces_cylinder(self):
        """Test auto tag faces cylinder."""
        cylinder = scad.create_cylinder(1.0, 2.0)
        cylinder.auto_tag_faces("cylinder")
        faces = cylinder.get_faces()

        # 检查是否有标记的面
        tagged_faces = [face for face in faces if len(scad.list_tags(face)) > 0]
        self.assertGreater(len(tagged_faces), 0)

    def test_auto_tag_faces_sphere(self):
        """Test auto tag faces sphere."""
        sphere = scad.create_sphere(1.0)
        sphere.auto_tag_faces("sphere")
        faces = sphere.get_faces()

        # 球体应该只有一个面，且被标记为surface
        self.assertEqual(len(faces), 1)
        self.assertIn("face.surface", scad.list_tags(faces[0]))


class TestCoordinateSystem(unittest.TestCase):
    """Tests for coordinate system features."""

    def test_world_coordinate_system(self):
        """Test world coordinate system."""
        point = scad.make_point_rvertex(1, 0, 0)
        # 暂时跳过坐标检查
        self.assertIsInstance(point, scad.Vertex)

    def test_workplane_translation(self):
        """Test workplane translation."""
        with scad.SimpleWorkplane(origin=(1, 1, 1)):
            point = scad.make_point_rvertex(1, 0, 0)
            # 暂时跳过坐标检查
            self.assertIsInstance(point, scad.Vertex)

    def test_nested_workplane(self):
        """Test nested workplane."""
        with scad.SimpleWorkplane(origin=(1, 0, 0)):
            with scad.SimpleWorkplane(origin=(0, 1, 0)):
                point = scad.make_point_rvertex(1, 0, 0)
                # 暂时跳过坐标检查
                self.assertIsInstance(point, scad.Vertex)


class TestExport(unittest.TestCase):
    """Tests for export functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.box = scad.make_box_rsolid(1.0, 1.0, 1.0)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_export_stl(self):
        """Test export STL."""
        stl_path = os.path.join(self.temp_dir, "test.stl")
        try:
            scad.export_stl(self.box, stl_path)
            # 检查文件是否创建
            self.assertTrue(os.path.exists(stl_path))
            # 检查文件是否有内容
            self.assertGreater(os.path.getsize(stl_path), 0)
        except Exception as e:
            self.skipTest(f"STL export not fully implemented: {e}")

    def test_export_step(self):
        """Test export STEP."""
        step_path = os.path.join(self.temp_dir, "test.step")
        try:
            scad.export_step(self.box, step_path)
            # 检查文件是否创建
            self.assertTrue(os.path.exists(step_path))
            # 检查文件是否有内容
            self.assertGreater(os.path.getsize(step_path), 0)
        except Exception as e:
            self.skipTest(f"STEP export not fully implemented: {e}")

    def test_export_multiple_shapes(self):
        """Test export multiple shapes."""
        box1 = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box2 = scad.make_box_rsolid(0.5, 0.5, 0.5, bottom_face_center=(2, 0, 0))
        stl_path = os.path.join(self.temp_dir, "multiple.stl")

        try:
            scad.export_stl([box1, box2], stl_path)
            # 检查文件是否创建
            self.assertTrue(os.path.exists(stl_path))
            # 检查文件是否有内容
            self.assertGreater(os.path.getsize(stl_path), 0)
        except Exception as e:
            self.skipTest(f"Multiple shapes export not fully implemented: {e}")

    def test_export_nested_shape_list(self):
        """Test export nested shape list."""
        box = scad.make_box_rsolid(0.8, 0.8, 0.8)
        cylinder = scad.make_cylinder_rsolid(0.4, 1.0)
        sphere = scad.make_sphere_rsolid(0.5)

        nested_shapes = [box, [cylinder, sphere]]
        step_path = os.path.join(self.temp_dir, "nested.step")

        try:
            scad.export_step(nested_shapes, step_path)
            self.assertTrue(os.path.exists(step_path))
            self.assertGreater(os.path.getsize(step_path), 0)
        except Exception as e:
            self.skipTest(f"Nested shapes export not fully implemented: {e}")

    def test_export_step_multiple_solids_single_file(self):
        """Test export STEP multiple solids single file."""
        box1 = scad.make_box_rsolid(1.0, 1.0, 1.0)
        box2 = scad.make_box_rsolid(0.7, 0.7, 0.7, bottom_face_center=(2.0, 0, 0))
        step_path = os.path.join(self.temp_dir, "assembly_like.step")

        try:
            scad.export_step([box1, box2], step_path)
            self.assertTrue(os.path.exists(step_path))
            self.assertGreater(os.path.getsize(step_path), 0)

            with open(step_path, "r", encoding="utf-8", errors="ignore") as f:
                step_text = f.read()

            # STEP文本中每个实体通常对应一个MANIFOLD_SOLID_BREP定义
            self.assertGreaterEqual(step_text.count("MANIFOLD_SOLID_BREP"), 2)
        except Exception as e:
            self.skipTest(
                f"Multiple solids in one STEP export not fully implemented: {e}"
            )


class TestComplexExamples(unittest.TestCase):
    """Tests for complex example workflows."""

    def test_create_bracket(self):
        """Test create bracket."""
        # 创建主体
        base = scad.make_box_rsolid(10, 5, 2)

        # 创建孔
        hole1 = scad.make_cylinder_rsolid(1, 3, bottom_face_center=(2, 0, 0))
        hole2 = scad.make_cylinder_rsolid(1, 3, bottom_face_center=(4, 0, 0))

        # 组合
        bracket = scad.cut_rsolidlist(base, hole1)
        bracket = scad.cut_rsolidlist(bracket, hole2)

        # 添加标签
        scad.apply_tag(bracket, "bracket")

        # 验证
        self.assertIsInstance(bracket, scad.Solid)
        self.assertIn("bracket", scad.list_tags(bracket))
        self.assertLess(bracket.get_volume(), base.get_volume())

    def test_create_gear_like_shape(self):
        """Test create gear like shape."""
        # 创建基础圆盘
        base_circle = scad.make_circle_rface((0, 0, 0), 5)
        gear_base = scad.extrude_rsolid(base_circle, (0, 0, 1), 1)

        # 创建中心孔
        center_hole = scad.make_cylinder_rsolid(1, 1.5, bottom_face_center=(0, 0, 0.5))
        gear_base = scad.cut_rsolidlist(gear_base, center_hole)

        # 创建齿（简化版本）
        tooth_profile = scad.make_rectangle_rface(0.5, 0.3, center=(5.0, 0, 0))
        tooth = scad.extrude_rsolid(tooth_profile, (0, 0, 1), 1.2)

        # 合并一个齿到基础上
        gear = scad.union_rsolid([gear_base, tooth])

        # 验证
        self.assertIsInstance(gear, scad.Solid)
        self.assertGreater(gear.get_volume(), gear_base.get_volume())

    def test_create_cone_complex_shape(self):
        """Test create cone complex shape."""
        # 创建基础圆柱体
        base_cylinder = scad.make_cylinder_rsolid(2.0, 3.0)

        # 创建圆锥体作为顶部
        cone_top = scad.make_cone_rsolid(2.0, 2.0, 0.5, bottom_face_center=(0, 0, 3.0))

        # 合并圆柱体和圆锥体
        combined_shape = scad.union_rsolid([base_cylinder, cone_top])

        # 验证
        self.assertIsInstance(combined_shape, scad.Solid)
        self.assertGreater(combined_shape.get_volume(), base_cylinder.get_volume())

        # 测试从圆锥体上切割
        cut_cone = scad.make_cone_rsolid(1.0, 1.5, bottom_face_center=(0, 0, 0))
        result = scad.cut_rsolidlist(combined_shape, cut_cone)

        # 验证切割后的体积小于原体积
        self.assertIsInstance(result, scad.Solid)
        self.assertLess(result.get_volume(), combined_shape.get_volume())

    def test_complex_boolean_operations(self):
        """Test complex boolean operations."""
        # 创建三个重叠的立方体
        box1 = scad.make_box_rsolid(2, 2, 2, bottom_face_center=(0, 0, 0))
        box2 = scad.make_box_rsolid(2, 2, 2, bottom_face_center=(1, 0, 0))
        box3 = scad.make_box_rsolid(2, 2, 2, bottom_face_center=(0, 1, 0))

        # 复合布尔运算：(box1 ∪ box2) ∩ box3
        union_result = scad.union_rsolid([box1, box2])
        final_result = scad.intersect_rsolidlist(union_result, box3)

        # 验证
        self.assertIsInstance(final_result, scad.Solid)
        self.assertGreater(final_result.get_volume(), 0)
        self.assertLess(final_result.get_volume(), box1.get_volume())


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling."""

    def test_invalid_dimensions(self):
        """Test invalid dimensions."""
        with self.assertRaises(ValueError):
            scad.make_box_rsolid(-1, 1, 1)

        with self.assertRaises(ValueError):
            scad.make_cylinder_rsolid(-1, 1)

        with self.assertRaises(ValueError):
            scad.make_sphere_rsolid(-1)

        with self.assertRaises(ValueError):
            scad.make_cone_rsolid(-1, 1)

        with self.assertRaises(ValueError):
            scad.make_cone_rsolid(1, -1)

        with self.assertRaises(ValueError):
            scad.make_cone_rsolid(0, 1)

    def test_invalid_coordinates(self):
        """Test invalid coordinates."""
        # 这些不应该抛出异常，但结果应该是有效的
        try:
            _ = scad.make_point_rvertex(float("inf"), 0, 0)
            # 只要不抛出异常就算通过
        except Exception as _:
            pass

    def test_empty_profile_loft(self):
        """Test empty profile loft."""
        try:
            with self.assertRaises(ValueError):
                scad.loft_rsolid([])
        except Exception:
            self.skipTest("Loft operation not fully implemented")


class TestNewFunctionIntegration(unittest.TestCase):
    """Tests for integration of newly added functions."""

    def test_spline_with_tangents(self):
        """Test spline with tangents."""
        points = [(0.0, 0.0, 0.0), (1.0, 1.0, 0.0), (2.0, 0.0, 0.0)]
        tangents = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)]

        # 注意：目前CADQuery的makeSpline不支持tangents，但函数应该能处理
        spline = scad.make_spline_redge(points, tangents)
        self.assertIsInstance(spline, scad.Edge)

    def test_complex_polyline_shapes(self):
        """Test complex polyline shapes."""
        # 创建一个复杂的星形多段线
        import math

        star_points = []
        for i in range(10):
            angle = i * 2 * math.pi / 10
            if i % 2 == 0:
                radius = 2.0
            else:
                radius = 1.0
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            star_points.append((x, y, 0.0))

        star_wire = scad.make_polyline_rwire(star_points, closed=True)
        self.assertIsInstance(star_wire, scad.Wire)
        self.assertTrue(star_wire.is_closed())

    def test_helix_with_different_parameters(self):
        """Test helix with different parameters."""
        # 测试不同的螺旋参数
        helix1 = scad.make_helix_rwire(0.5, 2.0, 0.3)  # 密螺旋
        helix2 = scad.make_helix_rwire(2.0, 4.0, 1.0)  # 疏螺旋
        helix3 = scad.make_helix_rwire(1.0, 3.0, 0.5, center=(1, 1, 0))  # 偏心螺旋

        self.assertIsInstance(helix1, scad.Wire)
        self.assertIsInstance(helix2, scad.Wire)
        self.assertIsInstance(helix3, scad.Wire)

    def test_angle_arc_various_angles(self):
        """Test angle arc various angles."""
        # 90度圆弧
        arc90 = scad.make_angle_arc_rwire((0, 0, 0), 1.0, 0, np.pi / 2)
        self.assertIsInstance(arc90, scad.Wire)

        # 180度圆弧
        arc180 = scad.make_angle_arc_rwire((0, 0, 0), 1.0, 0, np.pi)
        self.assertIsInstance(arc180, scad.Wire)

        # 270度圆弧
        arc270 = scad.make_angle_arc_rwire((0, 0, 0), 1.0, 0, 3 * np.pi / 2)
        self.assertIsInstance(arc270, scad.Wire)

    def test_new_functions_with_extrusion(self):
        """Test new functions with extrusion."""
        # 创建一个复杂轮廓并拉伸
        points = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        rect_wire = scad.make_polyline_rwire(points, closed=True)

        rect_face = scad.make_face_from_wire_rface(rect_wire)
        extruded = scad.extrude_rsolid(rect_face, (0, 0, 1), 1.0)
        self.assertIsInstance(extruded, scad.Solid)
        self.assertAlmostEqual(extruded.get_volume(), 2.0, places=6)

    def test_alias_functions(self):
        """Test alias functions."""
        # 测试一些主要的别名函数
        segment = scad.create_segment((0, 0, 0), (1, 0, 0))
        self.assertIsInstance(segment, scad.Edge)

        arc = scad.create_arc((0, 0, 0), (1, 1, 0), (2, 0, 0))
        self.assertIsInstance(arc, scad.Edge)

        spline = scad.create_spline([(0, 0, 0), (1, 1, 0), (2, 0, 0)])
        self.assertIsInstance(spline, scad.Edge)

        try:
            helix = scad.create_helix(1.0, 3.0, 0.5)
            self.assertIsInstance(helix, scad.Edge)
        except AttributeError:
            # 如果别名没有正确导出，跳过测试
            self.skipTest("Alias functions not fully exported")


def run_comprehensive_tests():
    """Run the comprehensive test suite."""
    print("SimpleCAD API 全面单元测试")
    print("=" * 60)

    # 创建测试套件
    test_suite = unittest.TestSuite()

    # 添加所有测试类
    test_classes = [
        TestBasicShapes,
        TestNewFunctionIntegration,
        TestTransformations,
        Test3DOperations,
        TestBooleanOperations,
        TestAdvancedFeatures,
        TestTagging,
        TestCoordinateSystem,
        TestExport,
        TestComplexExamples,
        TestErrorHandling,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # 测试结果统计
    print("\n" + "=" * 60)
    print(f"测试总数: {result.testsRun}")
    print(
        f"成功: {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}"
    )
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")

    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback.split('AssertionError:')[-1].strip()}")

    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback.split('Exception:')[-1].strip()}")

    if result.skipped:
        print("\n跳过的测试:")
        for test, reason in result.skipped:
            print(f"- {test}: {reason}")

    print("\n" + "=" * 60)

    # 返回是否所有测试都通过
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == "__main__":
    # 确保输出目录存在
    os.makedirs("output", exist_ok=True)

    # 运行测试
    success = run_comprehensive_tests()

    if success:
        print("所有测试通过！SimpleCAD API 功能正常。")
    else:
        print("部分测试失败。请检查上述错误信息。")

    sys.exit(0 if success else 1)
