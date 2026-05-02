"""OCP-native core class definitions for the SimpleCAD API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

import numpy as np
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopoDS import TopoDS, TopoDS_Shape

from ._vendor_warning_filters import suppress_vendor_deprecation_warnings
from .errors import raise_harness_error
from .kernel.ocp_cast import as_edge, as_face, as_solid, as_vertex, as_wire, shape_type_name
from .kernel.ocp_properties import Vec3, center_of_mass, face_normal_at, linear_length, surface_area, volume
from .kernel.ocp_topology import edges_of, faces_of, inner_wires_of, is_wire_closed, outer_wire_of, vertex_point, vertices_of
from .tagging import DEFAULT_TAG_POLICY, normalize_tag

suppress_vendor_deprecation_warnings()


class CoordinateSystem:
    """Three-dimensional coordinate system.

    SimpleCAD uses a right-handed Z-up coordinate system with the origin at
    (0, 0, 0): X forward, Y right, Z up.
    """

    def __init__(
        self,
        origin: Tuple[float, float, float] = (0, 0, 0),
        x_axis: Tuple[float, float, float] = (1, 0, 0),
        y_axis: Tuple[float, float, float] = (0, 1, 0),
    ):
        try:
            self.origin = np.array(origin, dtype=float)
            self.x_axis = self._normalize(x_axis)
            self.y_axis = self._normalize(y_axis)
            self.z_axis = self._normalize(np.cross(self.x_axis, self.y_axis))
        except Exception as e:
            raise_harness_error(
                operation="CoordinateSystem.__init__",
                what_happened="Failed to create a coordinate system.",
                possible_causes=[
                    "One of the origin or axis values is not a valid 3D numeric vector.",
                    "One of the axis vectors is zero-length or cannot be normalized.",
                    "The axis inputs are malformed or contain non-numeric values.",
                ],
                how_to_fix=[
                    "Pass origin, x_axis, and y_axis as 3-element numeric tuples or arrays.",
                    "Make sure x_axis and y_axis are non-zero vectors.",
                    "If you build axes dynamically, print the vectors before constructing the coordinate system.",
                ],
                error=e,
            )

    def _normalize(self, vector) -> np.ndarray:
        v = np.array(vector, dtype=float)
        norm = np.linalg.norm(v)
        if norm == 0:
            raise_harness_error(
                operation="CoordinateSystem._normalize",
                what_happened="A zero-length vector cannot be normalized.",
                possible_causes=[
                    "The input vector is exactly (0, 0, 0).",
                    "The input values collapsed to zero after numeric conversion.",
                ],
                how_to_fix=[
                    "Provide a non-zero direction vector.",
                    "Check upstream calculations that produce this vector.",
                ],
                technical_details=f"vector={tuple(v.tolist())}",
            )
        return v / norm

    def transform_point(self, point: np.ndarray) -> np.ndarray:
        try:
            local_point = np.asarray(point, dtype=float)
            if local_point.shape != (3,):
                raise_harness_error(
                    operation="CoordinateSystem.transform_point",
                    what_happened="The point could not be interpreted as a 3D coordinate.",
                    possible_causes=[
                        "The point does not contain exactly three numeric components.",
                        "The point contains NaN or non-numeric values.",
                    ],
                    how_to_fix=[
                        "Pass the point as a 3-element tuple, list, or NumPy array.",
                        "Validate the point values before calling transform_point().",
                    ],
                    technical_details=f"point_shape={local_point.shape}",
                )
            if not np.all(np.isfinite(local_point)):
                raise_harness_error(
                    operation="CoordinateSystem.transform_point",
                    what_happened="The point contains non-finite numeric values.",
                    possible_causes=[
                        "A previous computation produced NaN or infinity.",
                        "The point was assembled from invalid expression results.",
                    ],
                    how_to_fix=[
                        "Inspect the upstream values used to build the point.",
                        "Replace NaN or infinity with finite numeric coordinates before calling this API.",
                    ],
                    technical_details=f"point={tuple(local_point.tolist())}",
                )
            return (
                self.origin
                + local_point[0] * self.x_axis
                + local_point[1] * self.y_axis
                + local_point[2] * self.z_axis
            )
        except Exception as e:
            raise_harness_error(
                operation="CoordinateSystem.transform_point",
                what_happened="Failed to transform the point into global coordinates.",
                possible_causes=[
                    "The point is not a valid finite 3D vector.",
                    "The coordinate system axes are invalid or inconsistent.",
                ],
                how_to_fix=[
                    "Pass a finite 3D point.",
                    "Validate the coordinate system before transforming points.",
                ],
                error=e,
            )

    def transform_vector(self, vector: np.ndarray) -> np.ndarray:
        try:
            v = np.array(vector, dtype=float)
            if v.shape != (3,):
                raise_harness_error(
                    operation="CoordinateSystem.transform_vector",
                    what_happened="The vector could not be interpreted as a 3D direction.",
                    possible_causes=[
                        "The input does not contain exactly three numeric components.",
                        "The input was passed as a malformed nested structure.",
                    ],
                    how_to_fix=[
                        "Pass the vector as a 3-element tuple, list, or NumPy array.",
                        "Validate the vector shape before calling transform_vector().",
                    ],
                    technical_details=f"vector_shape={v.shape}",
                )
            if not np.all(np.isfinite(v)):
                raise_harness_error(
                    operation="CoordinateSystem.transform_vector",
                    what_happened="The vector contains non-finite numeric values.",
                    possible_causes=[
                        "A previous computation produced NaN or infinity.",
                        "The direction vector was derived from invalid geometry.",
                    ],
                    how_to_fix=[
                        "Inspect the upstream direction calculation.",
                        "Ensure all vector components are finite numbers before calling this API.",
                    ],
                    technical_details=f"vector={tuple(v.tolist())}",
                )
            return v[0] * self.x_axis + v[1] * self.y_axis + v[2] * self.z_axis
        except Exception as e:
            raise_harness_error(
                operation="CoordinateSystem.transform_vector",
                what_happened="Failed to transform the vector into global coordinates.",
                possible_causes=[
                    "The vector is not a valid finite 3D direction.",
                    "The coordinate system axes are invalid or inconsistent.",
                ],
                how_to_fix=[
                    "Pass a finite 3D direction vector.",
                    "Validate the coordinate system before transforming vectors.",
                ],
                error=e,
            )

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        return f"CoordinateSystem(origin={tuple(self.origin)}, x_axis={tuple(self.x_axis)}, y_axis={tuple(self.y_axis)})"

    def _format_string(self, indent: int = 0) -> str:
        spaces = "  " * indent
        result = []
        result.append(f"{spaces}CoordinateSystem:")
        result.append(f"{spaces}  origin: [{self.origin[0]:.3f}, {self.origin[1]:.3f}, {self.origin[2]:.3f}]")
        result.append(f"{spaces}  x_axis: [{self.x_axis[0]:.3f}, {self.x_axis[1]:.3f}, {self.x_axis[2]:.3f}]")
        result.append(f"{spaces}  y_axis: [{self.y_axis[0]:.3f}, {self.y_axis[1]:.3f}, {self.y_axis[2]:.3f}]")
        result.append(f"{spaces}  z_axis: [{self.z_axis[0]:.3f}, {self.z_axis[1]:.3f}, {self.z_axis[2]:.3f}]")
        return "\n".join(result)


WORLD_CS = CoordinateSystem()


class SimpleWorkplane:
    """Workplane context manager defining a local coordinate system."""

    def __init__(
        self,
        origin: Tuple[float, float, float] = (0, 0, 0),
        normal: Tuple[float, float, float] = (0, 0, 1),
        x_dir: Tuple[float, float, float] = (1, 0, 0),
    ):
        current_cs = get_current_cs()
        global_origin = current_cs.transform_point(np.array(origin))
        global_x_dir = current_cs.transform_vector(np.array(x_dir))
        global_normal = current_cs.transform_vector(np.array(normal))
        global_normal = global_normal / np.linalg.norm(global_normal)
        global_y_dir = np.cross(global_normal, global_x_dir)
        y_norm = np.linalg.norm(global_y_dir)
        if y_norm < 1e-10:
            temp_x = np.array([1, 0, 0]) if abs(global_normal[0]) < 0.9 else np.array([0, 1, 0])
            global_y_dir = np.cross(global_normal, temp_x)
            global_y_dir = global_y_dir / np.linalg.norm(global_y_dir)
            global_x_dir = np.cross(global_y_dir, global_normal)
            global_x_dir = global_x_dir / np.linalg.norm(global_x_dir)
        else:
            global_y_dir = global_y_dir / y_norm
            global_x_dir = np.cross(global_y_dir, global_normal)
            global_x_dir = global_x_dir / np.linalg.norm(global_x_dir)
        self.cs = CoordinateSystem(tuple(global_origin), tuple(global_x_dir), tuple(global_y_dir))

    def __enter__(self):
        _current_cs.append(self.cs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _current_cs.pop()

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        return f"SimpleWorkplane(origin={tuple(self.cs.origin)}, normal={tuple(self.cs.z_axis)})"

    def _format_string(self, indent: int = 0, show_coordinate_system: bool = True) -> str:
        spaces = "  " * indent
        result = [f"{spaces}SimpleWorkplane:"]
        if show_coordinate_system:
            result.append(f"{spaces}  coordinate_system:")
            result.append(self.cs._format_string(indent + 2))
        return "\n".join(result)


_current_cs = [WORLD_CS]


def get_current_cs() -> CoordinateSystem:
    return _current_cs[-1]


class TaggedMixin:
    """Tag mixin that provides tagging support for geometry objects."""

    def __init__(self):
        self._tags: Set[str] = set()
        self._metadata: Dict[str, Any] = {}
        self._runtime: Dict[str, Any] = {}

    def add_tag(self, tag: str) -> None:
        if not isinstance(tag, str):
            raise TypeError("标签必须是字符串类型")
        self._tags.add(tag)

    def apply_tag(self, tag: str, *, normalize: bool = True, propagate: Optional[bool] = None) -> None:
        if normalize:
            tag = normalize_tag(tag, strict=True)
        self._tags.add(tag)
        if propagate is None:
            propagate = DEFAULT_TAG_POLICY.should_propagate(tag)
        if propagate:
            self._propagate_tag_down(tag)

    def _propagate_tag_down(self, tag: str) -> None:
        if not isinstance(self, TopoMixein):
            return
        try:
            children = self.get_children()
        except Exception:
            return
        for child in children:
            if isinstance(child, TaggedMixin):
                child._tags.add(tag)
                child._propagate_tag_down(tag)

    def remove_tag(self, tag: str) -> None:
        self._tags.discard(tag)

    def has_tag(self, tag: str) -> bool:
        return tag in self._tags

    def get_tags(self) -> list[str]:
        return list(set(self._tags.copy()))

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        return self._metadata.get(key, default)

    def _set_runtime(self, key: str, value: Any) -> None:
        self._runtime[key] = value

    def _get_runtime(self, key: str, default: Any = None) -> Any:
        return self._runtime.get(key, default)

    def _format_tags_and_metadata(self, indent: int = 0) -> str:
        spaces = "  " * indent
        result = []
        if self._tags:
            result.append(f"{spaces}tags: [{', '.join(sorted(self._tags))}]")
        if self._metadata:
            result.append(f"{spaces}metadata:")
            for key, value in sorted(self._metadata.items()):
                result.append(f"{spaces}  {key}: {value}")
        return "\n".join(result)


class TopoMixein:
    """Topology management mixin."""

    def __init__(self, level: int, self_shape_ref: "AnyShape") -> None:
        self.level: int = level
        self.self_shape_ref: AnyShape = self_shape_ref
        self.children: List[AnyShape] = []
        self.parent: Optional[AnyShape] = None

    def set_parent(self, parent: "AnyShape") -> None:
        self.parent = parent

    def add_child(self, child: "AnyShape") -> None:
        if child not in self.children:
            self.children.append(child)
            child.set_parent(self.self_shape_ref)

    def get_children(self) -> List["AnyShape"]:
        return self.children

    def get_parent(self) -> Optional["AnyShape"]:
        return self.parent


class Vertex(TaggedMixin, TopoMixein):
    """OCP-native vertex wrapper with tag support."""

    def __init__(self, vertex: Any):
        try:
            self.wrapped = as_vertex(vertex)
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=0, self_shape_ref=self)
        except Exception as e:
            raise ValueError(f"初始化顶点失败: {e}. 请检查输入的顶点对象是否有效。")

    def get_coordinates(self) -> Tuple[float, float, float]:
        try:
            return vertex_point(self.wrapped)
        except Exception as e:
            raise ValueError(f"获取顶点坐标失败: {e}")

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        return f"Vertex(coordinates={self.get_coordinates()})"

    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        spaces = "  " * indent
        coords = self.get_coordinates()
        result = [f"{spaces}Vertex:", f"{spaces}  coordinates: [{coords[0]:.3f}, {coords[1]:.3f}, {coords[2]:.3f}]"]
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        return "\n".join(result)


class Edge(TaggedMixin, TopoMixein):
    """OCP-native edge wrapper with tag support."""

    def __init__(self, edge: Any):
        try:
            self.wrapped = as_edge(edge)
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=1, self_shape_ref=self)
            for vertex in vertices_of(self.wrapped):
                self.add_child(Vertex(vertex))
        except Exception as e:
            raise ValueError(f"初始化边失败: {e}. 请检查输入的边对象是否有效。")

    def get_length(self) -> float:
        try:
            return float(linear_length(self.wrapped))
        except Exception as e:
            raise ValueError(f"获取边长度失败: {e}")

    def get_start_vertex(self) -> Vertex:
        try:
            if len(self.get_children()) < 1:
                raise ValueError("边没有顶点")
            return cast(Vertex, self.get_children()[0])
        except Exception as e:
            raise ValueError(f"获取起始顶点失败: {e}")

    def get_end_vertex(self) -> Vertex:
        try:
            if len(self.get_children()) < 2:
                raise ValueError("边没有足够的顶点")
            return cast(Vertex, self.get_children()[-1])
        except Exception as e:
            raise ValueError(f"获取结束顶点失败: {e}")

    def get_center(self) -> Vec3:
        return center_of_mass(self.wrapped)

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        length = self.get_length()
        try:
            part1 = f"from: {self.get_start_vertex().get_coordinates()}, to: {self.get_end_vertex().get_coordinates()}"
        except Exception:
            part1 = "from: [unable to retrieve], to: [unable to retrieve], usually this is a closed edge"
        return f"Edge({part1}, length={length:.3f}, tags={self.get_tags()})"

    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        spaces = "  " * indent
        result = [f"{spaces}Edge:", f"{spaces}  length: {self.get_length():.3f}"]
        try:
            result.append(f"{spaces}  vertices:")
            result.append(f"{spaces}    start: {self.get_start_vertex().get_coordinates()}")
            result.append(f"{spaces}    end: {self.get_end_vertex().get_coordinates()}")
        except Exception:
            result.append(f"{spaces}  vertices: [unable to retrieve, usually a closed edge]")
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        return "\n".join(result)


class Wire(TaggedMixin, TopoMixein):
    """OCP-native wire wrapper with tag support."""

    def __init__(self, wire: Any):
        try:
            self.wrapped = as_wire(wire)
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=2, self_shape_ref=self)
            for edge in edges_of(self.wrapped):
                self.add_child(Edge(edge))
        except Exception as e:
            raise ValueError(f"初始化线失败: {e}. 请检查输入的线对象是否有效。")

    def get_edges(self) -> List[Edge]:
        try:
            return cast(List[Edge], self.get_children())
        except Exception as e:
            raise ValueError(f"获取边列表失败: {e}")

    def is_closed(self) -> bool:
        try:
            return bool(is_wire_closed(self.wrapped))
        except Exception as e:
            raise ValueError(f"检查线闭合性失败: {e}")

    def _tag_edges(self) -> None:
        policy = DEFAULT_TAG_POLICY
        for i, edge in enumerate(self.get_edges()):
            for tag in self.get_tags():
                if policy.should_propagate(tag):
                    edge.add_tag(tag)
            edge.add_tag("edge")
            edge.add_tag(f"{i}")

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        return f"Wire(edge_count={len(self.get_edges())}, closed={self.is_closed()}, tags={self.get_tags()})"

    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        spaces = "  " * indent
        edges = self.get_edges()
        result = [f"{spaces}Wire:", f"{spaces}  edge_count: {len(edges)}", f"{spaces}  closed: {self.is_closed()}"]
        if edges:
            result.append(f"{spaces}  edges:")
            for i, edge in enumerate(edges):
                result.append(f"{spaces}    edge_{i}:")
                result.append(edge._format_string(indent + 3, False))
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        return "\n".join(result)


class Face(TaggedMixin, TopoMixein):
    """OCP-native face wrapper with tag support."""

    def __init__(self, face: Any):
        try:
            self.wrapped = as_face(face)
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=3, self_shape_ref=self)
            outer_wire = Wire(outer_wire_of(self.wrapped))
            outer_wire.add_tag("outer_wire")
            outer_wire.apply_tag("wire.outer", propagate=False)
            self.add_child(outer_wire)
            for wire in inner_wires_of(self.wrapped):
                inner = Wire(wire)
                inner.add_tag("inner_wire")
                inner.apply_tag("wire.inner", propagate=False)
                self.add_child(inner)
        except Exception as e:
            raise ValueError(f"初始化面失败: {e}. 请检查输入的面对象是否有效。")

    def get_area(self) -> float:
        try:
            return float(surface_area(self.wrapped))
        except Exception as e:
            raise ValueError(f"获取面积失败: {e}")

    def get_normal_at(self, u: float = 0.5, v: float = 0.5) -> Vec3:
        try:
            return face_normal_at(self.wrapped, u, v)
        except Exception as e:
            raise ValueError(f"获取法向量失败: {e}")

    def _tag_wires(self) -> None:
        policy = DEFAULT_TAG_POLICY
        outer_wire = self.get_outer_wire()
        for tag in self.get_tags():
            if policy.should_propagate(tag):
                outer_wire.add_tag(tag)
        outer_wire.add_tag("outer_wire")
        outer_wire.apply_tag("wire.outer", propagate=False)
        outer_wire._tag_edges()
        for i, inner in enumerate(self.get_inner_wires()):
            for tag in self.get_tags():
                if policy.should_propagate(tag):
                    inner.add_tag(tag)
            inner.add_tag("inner_wire")
            inner.apply_tag("wire.inner", propagate=False)
            inner.add_tag(f"{i}")
            inner._tag_edges()

    def get_outer_wire(self) -> Wire:
        try:
            return [w for w in cast(List[Wire], self.get_children()) if w.is_closed() and (w.has_tag("outer_wire") or w.has_tag("wire.outer"))][0]
        except Exception as e:
            raise ValueError(f"获取外边界线失败: {e}")

    def get_inner_wires(self) -> List[Wire]:
        try:
            return [w for w in cast(List[Wire], self.get_children()) if w.is_closed() and (w.has_tag("inner_wire") or w.has_tag("wire.inner"))]
        except Exception as e:
            raise ValueError(f"获取内边界线失败: {e}")

    def get_center(self) -> Vec3:
        return center_of_mass(self.wrapped)

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        return f"Face(area={self.get_area():.3f}, normal={self.get_normal_at()}, center={self.get_center()}, tags={self.get_tags()})"

    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        spaces = "  " * indent
        result = [f"{spaces}Face:", f"{spaces}  area: {self.get_area():.3f}, center: {self.get_center()}"]
        try:
            normal = self.get_normal_at()
            result.append(f"{spaces}  normal: [{normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f}]")
        except Exception:
            result.append(f"{spaces}  normal: [unable to retrieve]")
        try:
            result.append(f"{spaces}  outer_wire:")
            result.append(self.get_outer_wire()._format_string(indent + 2, False))
        except Exception:
            result.append(f"{spaces}  outer_wire: [unable to retrieve]")
        try:
            for inner in self.get_inner_wires():
                result.append(f"{spaces}  inner_wire:")
                result.append(inner._format_string(indent + 2, False))
        except Exception:
            result.append(f"{spaces}  inner_wires: [unable to retrieve]")
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        return "\n".join(result)


class Solid(TaggedMixin, TopoMixein):
    """OCP-native solid wrapper with tag support."""

    def __init__(self, solid: Any):
        try:
            self.wrapped = as_solid(solid)
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=4, self_shape_ref=self)
            for face in faces_of(self.wrapped):
                self.add_child(Face(face))
        except Exception as e:
            raise ValueError(f"初始化实体失败: {e}. 请检查输入的实体对象是否有效。")

    def get_volume(self) -> float:
        try:
            return float(volume(self.wrapped))
        except Exception as e:
            raise ValueError(f"获取体积失败: {e}")

    def get_faces(self) -> List[Face]:
        try:
            return [f for f in cast(List[Face], self.get_children()) if isinstance(f, Face)]
        except Exception as e:
            raise ValueError(f"获取面列表失败: {e}")

    def get_edges(self) -> List[Edge]:
        try:
            edges: List[Edge] = []
            for face in self.get_faces():
                edges.extend(face.get_outer_wire().get_edges())
                for inner in face.get_inner_wires():
                    edges.extend(inner.get_edges())
            return edges
        except Exception as e:
            raise ValueError(f"获取边列表失败: {e}")

    def auto_tag_faces(self, geometry_type: str = "unknown") -> None:
        try:
            faces = self.get_faces()
            if geometry_type == "box" and len(faces) == 6:
                self._auto_tag_box_faces(faces)
            elif geometry_type == "cylinder" and len(faces) == 3:
                self._auto_tag_cylinder_faces(faces)
            elif geometry_type == "sphere" and len(faces) == 1:
                self._tag_face(faces[0], "surface")
            else:
                for i, face in enumerate(faces):
                    self._tag_face(face, f"face_{i}")
        except Exception as e:
            raise ValueError(f"自动标记面失败: {e}")

    def _auto_tag_box_faces(self, faces: List[Face]) -> None:
        try:
            for i, face in enumerate(faces):
                normal = face.get_normal_at()
                if abs(normal.z) > 0.9:
                    tag = "top" if normal.z > 0 else "bottom"
                elif abs(normal.y) > 0.9:
                    tag = "front" if normal.y > 0 else "back"
                elif abs(normal.x) > 0.9:
                    tag = "right" if normal.x > 0 else "left"
                else:
                    tag = f"face_{i}"
                self._tag_face(face, tag)
        except Exception as e:
            print(f"警告: 自动标记立方体面失败: {e}")

    def _auto_tag_cylinder_faces(self, faces: List[Face]) -> None:
        try:
            plane_faces = []
            side_faces = []
            for face in faces:
                normal = face.get_normal_at()
                if abs(normal.z) > 0.9:
                    plane_faces.append(face)
                else:
                    side_faces.append(face)
            if len(plane_faces) != 2:
                raise ValueError(f"预期找到2个平面面，但找到了 {len(plane_faces)} 个")
            plane_faces.sort(key=lambda f: f.get_center().z)
            bottom_face, top_face = plane_faces
            self._tag_face(bottom_face, "bottom")
            self._tag_face(top_face, "top")
            for face in side_faces:
                self._tag_face(face, "side")
        except Exception as e:
            print(f"警告: 自动标记圆柱体面失败: {e}")

    def _tag_face(self, face: Face, tag: str) -> None:
        face.add_tag(tag)
        face.apply_tag(f"face.{tag}", propagate=False)
        face._tag_wires()

    def __str__(self) -> str:
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        return f"Solid(volume={self.get_volume():.3f}, faces={len(self.get_faces())}, tags={self.get_tags()})"

    def _format_string(self, indent: int = 0, show_coordinate_system: bool = True) -> str:
        spaces = "  " * indent
        faces = self.get_faces()
        edges = self.get_edges()
        result = [f"{spaces}Solid:", f"{spaces}  volume: {self.get_volume():.3f}", f"{spaces}  face_count: {len(faces)}", f"{spaces}  edge_count: {len(edges)}"]
        if show_coordinate_system:
            current_cs = get_current_cs()
            if current_cs != WORLD_CS:
                result.append(f"{spaces}  coordinate_system:")
                result.append(current_cs._format_string(indent + 2))
        if faces:
            result.append(f"{spaces}  faces:")
            for i, face in enumerate(faces):
                result.append(f"{spaces}    face_{i}:")
                result.append(face._format_string(indent + 3, False))
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        return "\n".join(result)


AnyShape = Union[Vertex, Edge, Wire, Face, Solid]
