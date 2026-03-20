"""
Core class definitions for the SimpleCAD API.
Based on the API design in the README and implemented on top of CADQuery.
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Union, Any, Dict, Set, cast
import numpy as np
import cadquery as cq
from cadquery import Vector, Plane
from cadquery.occ_impl.shapes import (
    Vertex as CQVertex,
    Edge as CQEdge,
    Wire as CQWire,
    Face as CQFace,
    Shell as CQShell,
    Solid as CQSolid,
    Compound as CQCompound,
)

from .tagging import DEFAULT_TAG_POLICY, normalize_tag


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
        """Initialize the coordinate system.

        Args:
            origin: Coordinate system origin.
            x_axis: X-axis direction vector.
            y_axis: Y-axis direction vector.
        """
        try:
            self.origin = np.array(origin, dtype=float)
            self.x_axis = self._normalize(x_axis)
            self.y_axis = self._normalize(y_axis)
            self.z_axis = self._normalize(np.cross(self.x_axis, self.y_axis))
        except Exception as e:
            raise ValueError(
                f"初始化坐标系失败: {e}. 请检查输入的坐标和方向向量是否有效。"
            )

    def _normalize(self, vector) -> np.ndarray:
        """Normalize a vector."""
        v = np.array(vector, dtype=float)
        norm = np.linalg.norm(v)
        if norm == 0:
            raise ValueError("不能归一化零向量")
        return v / norm

    def transform_point(self, point: np.ndarray) -> np.ndarray:
        """Transform a local point into global coordinates."""
        try:
            return (
                self.origin
                + point[0] * self.x_axis
                + point[1] * self.y_axis
                + point[2] * self.z_axis
            )
        except Exception as e:
            raise ValueError(f"坐标转换失败: {e}. 请检查输入点的格式是否正确。")

    def transform_vector(self, vector: np.ndarray) -> np.ndarray:
        """Transform a local direction vector into a global direction vector without translation."""
        try:
            v = np.array(vector, dtype=float)
            return v[0] * self.x_axis + v[1] * self.y_axis + v[2] * self.z_axis
        except Exception as e:
            raise ValueError(f"向量转换失败: {e}. 请检查输入向量的格式是否正确。")

    def to_cq_plane(self) -> Plane:
        """Convert to a CADQuery Plane object."""
        try:
            # 坐标系转换
            cq_origin = Vector(self.origin[0], self.origin[1], self.origin[2])
            cq_x_dir = Vector(self.x_axis[0], self.x_axis[1], self.x_axis[2])
            cq_normal = Vector(self.z_axis[0], self.z_axis[1], self.z_axis[2])

            return Plane(origin=cq_origin, xDir=cq_x_dir, normal=cq_normal)
        except Exception as e:
            raise ValueError(f"转换为CADQuery平面失败: {e}")

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        return f"CoordinateSystem(origin={tuple(self.origin)}, x_axis={tuple(self.x_axis)}, y_axis={tuple(self.y_axis)})"

    def _format_string(self, indent: int = 0) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
        """
        spaces = "  " * indent
        result = []
        result.append(f"{spaces}CoordinateSystem:")
        result.append(
            f"{spaces}  origin: [{self.origin[0]:.3f}, {self.origin[1]:.3f}, {self.origin[2]:.3f}]"
        )
        result.append(
            f"{spaces}  x_axis: [{self.x_axis[0]:.3f}, {self.x_axis[1]:.3f}, {self.x_axis[2]:.3f}]"
        )
        result.append(
            f"{spaces}  y_axis: [{self.y_axis[0]:.3f}, {self.y_axis[1]:.3f}, {self.y_axis[2]:.3f}]"
        )
        result.append(
            f"{spaces}  z_axis: [{self.z_axis[0]:.3f}, {self.z_axis[1]:.3f}, {self.z_axis[2]:.3f}]"
        )
        return "\n".join(result)


# 全局世界坐标系（Z向上的右手坐标系）
WORLD_CS = CoordinateSystem()


class SimpleWorkplane:
    """Workplane context manager.

    Defines a local coordinate system and supports nesting.
    """

    def __init__(
        self,
        origin: Tuple[float, float, float] = (0, 0, 0),
        normal: Tuple[float, float, float] = (0, 0, 1),
        x_dir: Tuple[float, float, float] = (1, 0, 0),
    ):
        """Initialize the workplane.

        Args:
            origin: Workplane origin.
            normal: Workplane normal vector.
            x_dir: Workplane X-axis direction.
        """
        # 获取当前坐标系
        current_cs = get_current_cs()

        # 将给定的origin从当前坐标系转换到全局坐标系
        local_origin = np.array(origin)
        global_origin = current_cs.transform_point(local_origin)

        # 将给定的方向向量从当前坐标系转换到全局坐标系
        local_x_dir = np.array(x_dir)
        global_x_dir = current_cs.transform_vector(local_x_dir)

        local_normal = np.array(normal)
        global_normal = current_cs.transform_vector(local_normal)

        # 重新正交化以确保坐标系的正确性
        global_normal = global_normal / np.linalg.norm(global_normal)

        # 计算Y轴以确保右手坐标系
        global_y_dir = np.cross(global_normal, global_x_dir)
        y_norm = np.linalg.norm(global_y_dir)

        if y_norm < 1e-10:  # 如果叉积接近零，说明normal和x_dir平行
            # 选择一个不平行的向量作为临时X轴
            if abs(global_normal[0]) < 0.9:
                temp_x = np.array([1, 0, 0])
            else:
                temp_x = np.array([0, 1, 0])

            # 重新计算Y轴
            global_y_dir = np.cross(global_normal, temp_x)
            global_y_dir = global_y_dir / np.linalg.norm(global_y_dir)

            # 重新计算X轴
            global_x_dir = np.cross(global_y_dir, global_normal)
            global_x_dir = global_x_dir / np.linalg.norm(global_x_dir)
        else:
            global_y_dir = global_y_dir / y_norm

            # 重新计算X轴以确保正交性
            global_x_dir = np.cross(global_y_dir, global_normal)
            global_x_dir = global_x_dir / np.linalg.norm(global_x_dir)

        self.cs = CoordinateSystem(
            tuple(global_origin), tuple(global_x_dir), tuple(global_y_dir)
        )
        self.cq_workplane = None

    def to_cq_workplane(self) -> cq.Workplane:
        """Convert to a CADQuery Workplane object."""
        if self.cq_workplane is None:
            try:
                self.cq_workplane = cq.Workplane(self.cs.to_cq_plane())
            except Exception as e:
                raise ValueError(f"创建CADQuery工作平面失败: {e}")
        return self.cq_workplane

    def __enter__(self):
        global _current_cs
        _current_cs.append(self.cs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _current_cs
        _current_cs.pop()

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        return f"SimpleWorkplane(origin={tuple(self.cs.origin)}, normal={tuple(self.cs.z_axis)})"

    def _format_string(
        self, indent: int = 0, show_coordinate_system: bool = True
    ) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
            show_coordinate_system: Whether to show coordinate system information.
        """
        spaces = "  " * indent
        result = []

        result.append(f"{spaces}SimpleWorkplane:")

        # 坐标系信息
        if show_coordinate_system:
            result.append(f"{spaces}  coordinate_system:")
            result.append(self.cs._format_string(indent + 2))

        return "\n".join(result)


# 当前坐标系上下文管理器
_current_cs = [WORLD_CS]


def get_current_cs() -> CoordinateSystem:
    """Get the current coordinate system."""
    global _current_cs
    return _current_cs[-1]


class TaggedMixin:
    """Tag mixin that provides tagging support for geometry objects."""

    def __init__(self):
        self._tags: Set[str] = set()
        self._metadata: Dict[str, Any] = {}

    def add_tag(self, tag: str) -> None:
        """Add a tag.

        Args:
            tag: Tag name.
        """
        if not isinstance(tag, str):
            raise TypeError("标签必须是字符串类型")
        self._tags.add(tag)

    def apply_tag(
        self,
        tag: str,
        *,
        normalize: bool = True,
        propagate: Optional[bool] = None,
    ) -> None:
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
        """Remove a tag.

        Args:
            tag: Tag name.
        """
        self._tags.discard(tag)

    def has_tag(self, tag: str) -> bool:
        """Check whether a given tag exists.

        Args:
            tag: Tag name.

        Returns:
            Whether the tag is present.
        """
        return tag in self._tags

    def get_tags(self) -> list[str]:
        """Get all tags."""
        return list(set(self._tags.copy()))

    def set_metadata(self, key: str, value: Any) -> None:
        """Set metadata.

        Args:
            key: Key.
            value: Value.
        """
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata.

        Args:
            key: Key.
            default: Default value.

        Returns:
            Metadata value.
        """
        return self._metadata.get(key, default)

    def _format_tags_and_metadata(self, indent: int = 0) -> str:
        """Format tags and metadata.

        Args:
            indent: Indentation level.
        """
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

    def __init__(self, level: int, self_shape_ref: AnyShape) -> None:

        self.level: int = level
        self.self_shape_ref: AnyShape = self_shape_ref
        self.children: List[AnyShape] = []
        self.parent: Optional[AnyShape] = None

    def set_parent(self, parent: AnyShape) -> None:
        """Set the parent geometry.

        Args:
            parent: Parent geometry.
        """
        self.parent = parent

    def add_child(self, child: AnyShape) -> None:
        """Add a child geometry.

        Args:
            child: Child geometry.
        """
        if child not in self.children:
            self.children.append(child)
            child.set_parent(self.self_shape_ref)

    def get_children(self) -> List[AnyShape]:
        """Get all child geometry.

        Returns:
            List of child geometry.
        """
        return self.children

    def get_parent(self) -> Optional[AnyShape]:
        """Get the parent geometry.

        Returns:
            Parent geometry or None.
        """
        return self.parent


class Vertex(TaggedMixin, TopoMixein):
    """Vertex wrapper around CADQuery Vertex with tag support."""

    def __init__(self, cq_vertex: CQVertex):
        """Initialize a vertex.

        Args:
            cq_vertex: CADQuery vertex object.
        """
        try:
            self.cq_vertex = cq_vertex
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=0, self_shape_ref=self)
        except Exception as e:
            raise ValueError(f"初始化顶点失败: {e}. 请检查输入的顶点对象是否有效。")

    def get_coordinates(self) -> Tuple[float, float, float]:
        """Get vertex coordinates.

        Returns:
            Vertex coordinates `(x, y, z)`.
        """
        try:
            center = self.cq_vertex.Center()
            return (center.x, center.y, center.z)
        except Exception as e:
            raise ValueError(f"获取顶点坐标失败: {e}")

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        coords = self.get_coordinates()
        return f"Vertex(coordinates={coords})"

    def _format_string(
        self, indent: int = 0, show_coordinate_system: bool = False
    ) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
            show_coordinate_system: Whether to show coordinate system information.
        """
        spaces = "  " * indent
        result = []

        # 基本信息
        coords = self.get_coordinates()
        result.append(f"{spaces}Vertex:")
        result.append(
            f"{spaces}  coordinates: [{coords[0]:.3f}, {coords[1]:.3f}, {coords[2]:.3f}]"
        )

        # 坐标系信息
        if show_coordinate_system:
            current_cs = get_current_cs()
            if current_cs != WORLD_CS:
                result.append(f"{spaces}  coordinate_system:")
                result.append(current_cs._format_string(indent + 2))

        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)

        return "\n".join(result)


class Edge(TaggedMixin, TopoMixein):
    """Edge wrapper around CADQuery Edge with tag support."""

    def __init__(self, cq_edge: CQEdge):
        """Initialize an edge.

        Args:
            cq_edge: CADQuery edge object.
        """
        try:
            self.cq_edge = cq_edge
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=1, self_shape_ref=self)

            for v in self.cq_edge.Vertices():
                vertex = Vertex(v)
                self.add_child(vertex)

        except Exception as e:
            raise ValueError(f"初始化边失败: {e}. 请检查输入的边对象是否有效。")

    def get_length(self) -> float:
        """Get edge length.

        Returns:
            Edge length.
        """
        try:
            # 使用CADQuery的方法获取边长度
            return float(self.cq_edge.Length())
        except Exception as e:
            raise ValueError(f"获取边长度失败: {e}")

    def get_start_vertex(self) -> Vertex:
        """Get the start vertex.

        Returns:
            Start vertex.
        """
        try:
            if len(self.get_children()) < 1:
                raise ValueError("边没有顶点")

            return cast(Vertex, self.get_children()[0])
        except Exception as e:
            raise ValueError(f"获取起始顶点失败: {e}")

    def get_end_vertex(self) -> Vertex:
        """Get the end vertex.

        Returns:
            End vertex.
        """
        try:
            if len(self.get_children()) < 2:
                raise ValueError("边没有足够的顶点")

            return cast(Vertex, self.get_children()[-1])
        except Exception as e:
            raise ValueError(f"获取结束顶点失败: {e}")

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        length = self.get_length()

        try:
            start_coord = self.get_start_vertex().get_coordinates()
            end_coord = self.get_end_vertex().get_coordinates()
            part1 = f"from: {start_coord}, to: {end_coord}"
        except Exception:
            part1 = "from: [unable to retrieve], to: [unable to retrieve], ususally this is a circle"

        return f"Edge({part1}, length={length:.3f}, tags={self.get_tags()})"

    def _format_string(
        self, indent: int = 0, show_coordinate_system: bool = False
    ) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
            show_coordinate_system: Whether to show coordinate system information.
        """
        spaces = "  " * indent
        result = []

        # 基本信息
        length = self.get_length()
        result.append(f"{spaces}Edge:")
        result.append(f"{spaces}  length: {length:.3f}")

        # 顶点信息
        try:
            start_vertex = self.get_start_vertex()
            end_vertex = self.get_end_vertex()
            result.append(f"{spaces}  vertices:")
            result.append(f"{spaces}    start: {start_vertex.get_coordinates()}")
            result.append(f"{spaces}    end: {end_vertex.get_coordinates()}")
        except Exception:
            result.append(f"{spaces}  vertices: [unable to retrieve, usually a circle]")

        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)

        return "\n".join(result)


class Wire(TaggedMixin, TopoMixein):
    """Wire wrapper around CADQuery Wire with tag support."""

    def __init__(self, cq_wire: CQWire):
        """Initialize a wire.

        Args:
            cq_wire: CADQuery wire object.
        """
        try:
            self.cq_wire = cq_wire
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=2, self_shape_ref=self)

            for e in self.cq_wire.Edges():
                self.add_child(Edge(e))

        except Exception as e:
            raise ValueError(f"初始化线失败: {e}. 请检查输入的线对象是否有效。")

    def get_edges(self) -> List[Edge]:
        """Get the edges that make up this wire.

        Returns:
            Edge list.
        """
        try:
            return cast(List[Edge], self.get_children())
        except Exception as e:
            raise ValueError(f"获取边列表失败: {e}")

    def is_closed(self) -> bool:
        """Check whether the wire is closed.

        Returns:
            Whether it is closed.
        """
        try:
            # 使用CADQuery的方法检查线是否闭合
            return bool(self.cq_wire.IsClosed())
        except Exception as e:
            raise ValueError(f"检查线闭合性失败: {e}")

    def _tag_edges(self) -> None:
        """Tag the edges that make up this wire."""
        policy = DEFAULT_TAG_POLICY
        for i, edge in enumerate(self.get_edges()):
            for tag in self.get_tags():
                if policy.should_propagate(tag):
                    edge.add_tag(tag)

            edge.add_tag("edge")
            edge.add_tag(f"{i}")

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        is_closed = self.is_closed()
        edge_count = len(self.get_edges())

        return (
            f"Wire(edge_count={edge_count}, closed={is_closed}, tags={self.get_tags()})"
        )

    def _format_string(
        self, indent: int = 0, show_coordinate_system: bool = False
    ) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
            show_coordinate_system: Whether to show coordinate system information.
        """
        spaces = "  " * indent
        result = []

        # 基本信息
        edges = self.get_edges()
        is_closed = self.is_closed()
        result.append(f"{spaces}Wire:")
        result.append(f"{spaces}  edge_count: {len(edges)}")
        result.append(f"{spaces}  closed: {is_closed}")

        # 边信息（不传递坐标系显示参数，因为Wire层级会统一显示）
        if edges:
            result.append(f"{spaces}  edges:")
            for i, edge in enumerate(edges):
                result.append(f"{spaces}    edge_{i}:")
                result.append(edge._format_string(indent + 3, False))

        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)

        return "\n".join(result)


class Face(TaggedMixin, TopoMixein):
    """Face wrapper around CADQuery Face with tag support."""

    def __init__(self, cq_face: CQFace):
        """Initialize a face.

        Args:
            cq_face: CADQuery face object.
        """
        try:
            self.cq_face = cq_face
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=3, self_shape_ref=self)

            outer_wire = Wire(self.cq_face.outerWire())
            outer_wire.add_tag("outer_wire")
            outer_wire.apply_tag("wire.outer", propagate=False)
            self.add_child(outer_wire)

            for w in self.cq_face.innerWires():
                iw = Wire(w)
                iw.add_tag("inner_wire")
                iw.apply_tag("wire.inner", propagate=False)
                self.add_child(iw)

        except Exception as e:
            raise ValueError(f"初始化面失败: {e}. 请检查输入的面对象是否有效。")

    def get_area(self) -> float:
        """Get area.

        Returns:
            Area.
        """
        try:
            return self.cq_face.Area()
        except Exception as e:
            raise ValueError(f"获取面积失败: {e}")

    def get_normal_at(self, u: float = 0.5, v: float = 0.5) -> Vector:
        """Get the face normal at the given parameters.

        Args:
            u: U parameter.
            v: V parameter.

        Returns:
            Normal vector.
        """
        try:
            normal, _ = self.cq_face.normalAt(u, v)
            return normal
        except Exception as e:
            raise ValueError(f"获取法向量失败: {e}")

    def _tag_wires(self) -> None:
        """Add tags to the wires on the face."""
        policy = DEFAULT_TAG_POLICY
        outer_wire = self.get_outer_wire()
        for tag in self.get_tags():
            if policy.should_propagate(tag):
                outer_wire.add_tag(tag)
        outer_wire.add_tag("outer_wire")
        outer_wire.apply_tag("wire.outer", propagate=False)
        outer_wire._tag_edges()
        for i, iw in enumerate(self.get_inner_wires()):
            for tag in self.get_tags():
                if policy.should_propagate(tag):
                    iw.add_tag(tag)

            iw.add_tag("inner_wire")
            iw.apply_tag("wire.inner", propagate=False)
            iw.add_tag(f"{i}")
            iw._tag_edges()

    def get_outer_wire(self) -> Wire:
        """Get the outer boundary wire.

        Returns:
            Outer boundary wire.
        """
        try:
            return [
                w
                for w in cast(List[Wire], self.get_children())
                if w.is_closed()
                and (w.has_tag("outer_wire") or w.has_tag("wire.outer"))
            ][0]
        except Exception as e:
            raise ValueError(f"获取外边界线失败: {e}")

    def get_inner_wires(self) -> List[Wire]:
        """Get the inner boundary wires.

        Returns:
            List of inner boundary wires.
        """
        try:
            return [
                w
                for w in cast(List[Wire], self.get_children())
                if w.is_closed()
                and (w.has_tag("inner_wire") or w.has_tag("wire.inner"))
            ]
        except Exception as e:
            raise ValueError(f"获取内边界线失败: {e}")

    def get_center(self) -> Vector:
        return self.cq_face.Center()

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        area = self.get_area()
        return f"Face(area={area:.3f}, normal={self.get_normal_at()}, center={self.get_center()}, tags={self.get_tags()})"

    def _format_string(
        self, indent: int = 0, show_coordinate_system: bool = False
    ) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
            show_coordinate_system: Whether to show coordinate system information.
        """
        spaces = "  " * indent
        result = []

        # 基本信息
        area = self.get_area()
        result.append(f"{spaces}Face:")
        result.append(f"{spaces}  area: {area:.3f}, center: {self.get_center()}")

        # 法向量信息
        try:
            normal = self.get_normal_at()
            result.append(
                f"{spaces}  normal: [{normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f}]"
            )
        except Exception:
            result.append(f"{spaces}  normal: [unable to retrieve]")

        # 外边界线信息（不传递坐标系显示参数，因为Face层级会统一显示）
        try:
            outer_wire = self.get_outer_wire()
            result.append(f"{spaces}  outer_wire:")
            result.append(outer_wire._format_string(indent + 2, False))
        except Exception:
            result.append(f"{spaces}  outer_wire: [unable to retrieve]")

        try:
            inner_wires = self.get_inner_wires()
            for inner_wire in inner_wires:
                result.append(f"{spaces}  inner_wire:")
                result.append(inner_wire._format_string(indent + 2, False))
        except Exception:
            result.append(f"{spaces}  inner_wires: [unable to retrieve]")

        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)

        return "\n".join(result)


class Solid(TaggedMixin, TopoMixein):
    """Solid wrapper around CADQuery Solid with tag support."""

    def __init__(self, cq_solid: Union[CQSolid, Any]):
        """Initialize a solid.

        Args:
            cq_solid: CADQuery solid object.
        """
        try:
            # 如果是CADQuery的Shape，检查是否为Solid
            if hasattr(cq_solid, "ShapeType") and cq_solid.ShapeType() == "Solid":
                self.cq_solid = cq_solid
            elif hasattr(cq_solid, "Solids") and cq_solid.Solids():
                # 如果是复合体，取第一个Solid
                self.cq_solid = cq_solid.Solids()[0]
            else:
                self.cq_solid = cq_solid
            TaggedMixin.__init__(self)
            TopoMixein.__init__(self, level=4, self_shape_ref=self)

            for f in self.cq_solid.Faces():
                self.add_child(Face(f))

        except Exception as e:
            raise ValueError(f"初始化实体失败: {e}. 请检查输入的实体对象是否有效。")

    def get_volume(self) -> float:
        """Get volume.

        Returns:
            Volume.
        """
        try:
            return self.cq_solid.Volume()
        except Exception as e:
            raise ValueError(f"获取体积失败: {e}")

    def get_faces(self) -> List[Face]:
        """Get the faces that make up this solid.

        Returns:
            Face list.
        """
        try:
            return [
                f for f in cast(List[Face], self.get_children()) if isinstance(f, Face)
            ]
        except Exception as e:
            raise ValueError(f"获取面列表失败: {e}")

    def get_edges(self) -> List[Edge]:
        """Get the edges that make up this solid.

        Returns:
            Edge list.
        """
        try:
            edges = []
            for face in self.get_faces():
                edges.extend(face.get_outer_wire().get_edges())
                for inner_wire in face.get_inner_wires():
                    edges.extend(inner_wire.get_edges())

            return edges
        except Exception as e:
            raise ValueError(f"获取边列表失败: {e}")

    def auto_tag_faces(self, geometry_type: str = "unknown") -> None:
        """Automatically add tags to faces.

        Args:
            geometry_type: Geometry type (`box`, `cylinder`, `sphere`, or `unknown`).
        """
        try:
            # 确保有面标签字典
            if not hasattr(self, "_face_tags"):
                self._face_tags = {}

            faces = self.get_faces()

            if geometry_type == "box" and len(faces) == 6:
                self._auto_tag_box_faces(faces)
            elif geometry_type == "cylinder" and len(faces) == 3:
                self._auto_tag_cylinder_faces(faces)
            elif geometry_type == "sphere" and len(faces) == 1:
                self._tag_face(faces[0], "surface")
            else:
                # 通用标签策略
                for i, face in enumerate(faces):
                    self._tag_face(face, f"face_{i}")
        except Exception as e:
            raise ValueError(f"自动标记面失败: {e}")

    def _auto_tag_box_faces(self, faces: List[Face]) -> None:
        """Automatically tag box faces."""
        try:
            for i, face in enumerate(faces):
                normal = face.get_normal_at()

                # 根据法向量判断面的位置
                if abs(normal.z) > 0.9:
                    if normal.z > 0:
                        tag = "top"
                    else:
                        tag = "bottom"
                elif abs(normal.y) > 0.9:
                    if normal.y > 0:
                        tag = "front"
                    else:
                        tag = "back"
                elif abs(normal.x) > 0.9:
                    if normal.x > 0:
                        tag = "right"
                    else:
                        tag = "left"
                else:
                    # 如果不能确定方向，给一个通用标签
                    tag = f"face_{i}"

                self._tag_face(face, tag)
        except Exception as e:
            print(f"警告: 自动标记立方体面失败: {e}")

    def _auto_tag_cylinder_faces(self, faces: List[Face]) -> None:
        """Automatically tag cylinder faces using edge count to distinguish side and planar faces."""
        try:
            plane_faces = []
            side_faces = []

            for face in faces:
                if len(face.get_outer_wire().get_edges()) == 3:
                    side_faces.append(face)
                else:
                    plane_faces.append(face)

            # 对 plane_faces 按照 z 坐标排序
            if len(plane_faces) != 2:
                raise ValueError(f"预期找到2个平面面，但找到了 {len(plane_faces)} 个")

            # 按中心点 z 坐标排序
            plane_faces.sort(key=lambda f: f.cq_face.Center().z)
            bottom_face, top_face = plane_faces

            self._tag_face(bottom_face, "bottom")
            self._tag_face(top_face, "top")

            for face in side_faces:
                self._tag_face(face, "side")

        except Exception as e:
            print(f"警告: 自动标记圆柱体面失败: {e}")

    def _tag_face(self, face: Face, tag: str) -> None:
        """Add a tag to a face and store it on the solid.

        Args:
            face: Face object.
            tag: Tag name.
        """
        # 同时也添加到面对象本身
        face.add_tag(tag)
        face.apply_tag(f"face.{tag}", propagate=False)
        face._tag_wires()

    def __str__(self) -> str:
        """String representation."""
        return self._format_string(indent=0)

    def __repr__(self) -> str:
        """Debug representation."""
        volume = self.get_volume()
        face_count = len(self.get_faces())
        return f"Solid(volume={volume:.3f}, faces={face_count}, tags={self.get_tags()})"

    def _format_string(
        self, indent: int = 0, show_coordinate_system: bool = True
    ) -> str:
        """Format as a string.

        Args:
            indent: Indentation level.
            show_coordinate_system: Whether to show coordinate system information.
        """
        spaces = "  " * indent
        result = []

        # 基本信息
        volume = self.get_volume()
        faces = self.get_faces()
        edges = self.get_edges()
        result.append(f"{spaces}Solid:")
        result.append(f"{spaces}  volume: {volume:.3f}")
        result.append(f"{spaces}  face_count: {len(faces)}")
        result.append(f"{spaces}  edge_count: {len(edges)}")

        # 坐标系信息（在Solid层级显示，子级Face不再显示）
        if show_coordinate_system:
            current_cs = get_current_cs()
            if current_cs != WORLD_CS:
                result.append(f"{spaces}  coordinate_system:")
                result.append(current_cs._format_string(indent + 2))

        # 面信息（不传递坐标系显示参数，因为Solid层级已经显示了）
        if faces:
            result.append(f"{spaces}  faces:")
            for i, face in enumerate(faces):
                result.append(f"{spaces}    face_{i}:")
                result.append(face._format_string(indent + 3, False))

        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)

        return "\n".join(result)


AnyShape = Union[Vertex, Edge, Wire, Face, Solid]
