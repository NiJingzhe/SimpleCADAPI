"""
SimpleCAD API核心类定义
基于README中的API设计，使用CADQuery作为底层实现
"""

from typing import List, Tuple, Union, Any, Dict, Set
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
    Compound as CQCompound
)


class CoordinateSystem:
    """三维坐标系
    
    SimpleCAD使用Z向上的右手坐标系，原点在(0, 0, 0)，X轴向前，Y轴向右，Z轴向上
    """
    
    def __init__(self, 
                 origin: Tuple[float, float, float] = (0, 0, 0),
                 x_axis: Tuple[float, float, float] = (1, 0, 0),
                 y_axis: Tuple[float, float, float] = (0, 1, 0)):
        """初始化坐标系
        
        Args:
            origin: 坐标系原点
            x_axis: X轴方向向量
            y_axis: Y轴方向向量
        """
        try:
            self.origin = np.array(origin, dtype=float)
            self.x_axis = self._normalize(x_axis)
            self.y_axis = self._normalize(y_axis)
            self.z_axis = self._normalize(np.cross(self.x_axis, self.y_axis))
        except Exception as e:
            raise ValueError(f"初始化坐标系失败: {e}. 请检查输入的坐标和方向向量是否有效。")
        
    def _normalize(self, vector) -> np.ndarray:
        """归一化向量"""
        v = np.array(vector, dtype=float)
        norm = np.linalg.norm(v)
        if norm == 0:
            raise ValueError("不能归一化零向量")
        return v / norm
    
    def transform_point(self, point: np.ndarray) -> np.ndarray:
        """将局部坐标转换为全局坐标"""
        try:
            return self.origin + point[0]*self.x_axis + point[1]*self.y_axis + point[2]*self.z_axis
        except Exception as e:
            raise ValueError(f"坐标转换失败: {e}. 请检查输入点的格式是否正确。")
    
    def transform_vector(self, vector: np.ndarray) -> np.ndarray:
        """将局部方向向量转换为全局方向向量（不包含平移）"""
        try:
            v = np.array(vector, dtype=float)
            return v[0]*self.x_axis + v[1]*self.y_axis + v[2]*self.z_axis
        except Exception as e:
            raise ValueError(f"向量转换失败: {e}. 请检查输入向量的格式是否正确。")
    
    def to_cq_plane(self) -> Plane:
        """转换为CADQuery的Plane对象
        
        SimpleCAD使用Z向上坐标系 (X前, Y右, Z上)
        CadQuery使用Y向上坐标系 (X右, Y上, Z前)
        
        转换规则：
        - SimpleCAD的X轴(前) -> CadQuery的Z轴(前)
        - SimpleCAD的Y轴(右) -> CadQuery的X轴(右)
        - SimpleCAD的Z轴(上) -> CadQuery的Y轴(上)
        """
        try:
            # 坐标系转换
            cq_origin = Vector(self.origin[1], self.origin[2], self.origin[0])  # Y,Z,X
            cq_x_dir = Vector(self.x_axis[1], self.x_axis[2], self.x_axis[0])  # Y,Z,X
            cq_normal = Vector(self.z_axis[1], self.z_axis[2], self.z_axis[0])  # Y,Z,X
            
            return Plane(
                origin=cq_origin,
                xDir=cq_x_dir,
                normal=cq_normal
            )
        except Exception as e:
            raise ValueError(f"转换为CADQuery平面失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        return f"CoordinateSystem(origin={tuple(self.origin)}, x_axis={tuple(self.x_axis)}, y_axis={tuple(self.y_axis)})"
    
    def _format_string(self, indent: int = 0) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
        """
        spaces = "  " * indent
        result = []
        result.append(f"{spaces}CoordinateSystem:")
        result.append(f"{spaces}  origin: [{self.origin[0]:.3f}, {self.origin[1]:.3f}, {self.origin[2]:.3f}]")
        result.append(f"{spaces}  x_axis: [{self.x_axis[0]:.3f}, {self.x_axis[1]:.3f}, {self.x_axis[2]:.3f}]")
        result.append(f"{spaces}  y_axis: [{self.y_axis[0]:.3f}, {self.y_axis[1]:.3f}, {self.y_axis[2]:.3f}]")
        result.append(f"{spaces}  z_axis: [{self.z_axis[0]:.3f}, {self.z_axis[1]:.3f}, {self.z_axis[2]:.3f}]")
        return "\n".join(result)


# 全局世界坐标系（Z向上的右手坐标系）
WORLD_CS = CoordinateSystem()


class SimpleWorkplane:
    """工作平面上下文管理器
    
    用于定义局部坐标系，支持嵌套使用
    """
    
    def __init__(self, 
                 origin: Tuple[float, float, float] = (0, 0, 0),
                 normal: Tuple[float, float, float] = (0, 0, 1),
                 x_dir: Tuple[float, float, float] = (1, 0, 0)):
        """初始化工作平面
        
        Args:
            origin: 工作平面原点
            normal: 工作平面法向量
            x_dir: 工作平面X轴方向
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
            tuple(global_origin), 
            tuple(global_x_dir), 
            tuple(global_y_dir)
        )
        self.cq_workplane = None
    
    def to_cq_workplane(self) -> cq.Workplane:
        """转换为CADQuery的Workplane对象"""
        if self.cq_workplane is None:
            try:
                self.cq_workplane = cq.Workplane(self.cs.to_cq_plane())
            except Exception as e:
                raise ValueError(f"创建CADQuery工作平面失败: {e}")
        return self.cq_workplane
    
    def __enter__(self):
        _current_cs.append(self.cs)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        _current_cs.pop()
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        return f"SimpleWorkplane(origin={tuple(self.cs.origin)}, normal={tuple(self.cs.z_axis)})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = True) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
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
    """获取当前坐标系"""
    return _current_cs[-1]


class TaggedMixin:
    """标签混入类，为几何体提供标签功能"""
    
    def __init__(self):
        self._tags: Set[str] = set()
        self._metadata: Dict[str, Any] = {}
    
    def add_tag(self, tag: str) -> None:
        """添加标签
        
        Args:
            tag: 标签名称
        """
        if not isinstance(tag, str):
            raise TypeError("标签必须是字符串类型")
        self._tags.add(tag)
    
    def remove_tag(self, tag: str) -> None:
        """移除标签
        
        Args:
            tag: 标签名称
        """
        self._tags.discard(tag)
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签
        
        Args:
            tag: 标签名称
            
        Returns:
            是否有该标签
        """
        return tag in self._tags
    
    def get_tags(self) -> Set[str]:
        """获取所有标签"""
        return self._tags.copy()
    
    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据
        
        Args:
            key: 键
            value: 值
        """
        self._metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            元数据值
        """
        return self._metadata.get(key, default)
    
    def _format_tags_and_metadata(self, indent: int = 0) -> str:
        """格式化标签和元数据
        
        Args:
            indent: 缩进级别
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


class Vertex(TaggedMixin):
    """顶点类，包装CADQuery的Vertex，添加标签功能"""
    
    def __init__(self, cq_vertex: CQVertex):
        """初始化顶点
        
        Args:
            cq_vertex: CADQuery的顶点对象
        """
        try:
            self.cq_vertex = cq_vertex
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化顶点失败: {e}. 请检查输入的顶点对象是否有效。")
    
    def get_coordinates(self) -> Tuple[float, float, float]:
        """获取顶点坐标
        
        Returns:
            顶点坐标 (x, y, z)
        """
        try:
            center = self.cq_vertex.Center()
            return (center.x, center.y, center.z)
        except Exception as e:
            raise ValueError(f"获取顶点坐标失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        coords = self.get_coordinates()
        return f"Vertex(coordinates={coords})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
        """
        spaces = "  " * indent
        result = []
        
        # 基本信息
        coords = self.get_coordinates()
        result.append(f"{spaces}Vertex:")
        result.append(f"{spaces}  coordinates: [{coords[0]:.3f}, {coords[1]:.3f}, {coords[2]:.3f}]")
        
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


class Edge(TaggedMixin):
    """边类，包装CADQuery的Edge，添加标签功能"""
    
    def __init__(self, cq_edge: CQEdge):
        """初始化边
        
        Args:
            cq_edge: CADQuery的边对象
        """
        try:
            self.cq_edge = cq_edge
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化边失败: {e}. 请检查输入的边对象是否有效。")
    
    def get_length(self) -> float:
        """获取边长度
        
        Returns:
            边长度
        """
        try:
            # 使用CADQuery的方法获取边长度
            return float(self.cq_edge.Length())
        except Exception as e:
            raise ValueError(f"获取边长度失败: {e}")
    
    def get_start_vertex(self) -> Vertex:
        """获取起始顶点
        
        Returns:
            起始顶点
        """
        try:
            vertices = self.cq_edge.Vertices()
            if len(vertices) < 1:
                raise ValueError("边没有顶点")
            return Vertex(vertices[0])
        except Exception as e:
            raise ValueError(f"获取起始顶点失败: {e}")
    
    def get_end_vertex(self) -> Vertex:
        """获取结束顶点
        
        Returns:
            结束顶点
        """
        try:
            vertices = self.cq_edge.Vertices()
            if len(vertices) < 2:
                raise ValueError("边没有足够的顶点")
            return Vertex(vertices[-1])
        except Exception as e:
            raise ValueError(f"获取结束顶点失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        length = self.get_length()
        return f"Edge(length={length:.3f})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
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
            result.append(f"{spaces}  vertices: [unable to retrieve]")
        
        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        
        return "\n".join(result)


class Wire(TaggedMixin):
    """线类，包装CADQuery的Wire，添加标签功能"""
    
    def __init__(self, cq_wire: CQWire):
        """初始化线
        
        Args:
            cq_wire: CADQuery的线对象
        """
        try:
            self.cq_wire = cq_wire
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化线失败: {e}. 请检查输入的线对象是否有效。")
    
    def get_edges(self) -> List[Edge]:
        """获取组成线的边
        
        Returns:
            边列表
        """
        try:
            edges = self.cq_wire.Edges()
            return [Edge(edge) for edge in edges]
        except Exception as e:
            raise ValueError(f"获取边列表失败: {e}")
    
    def is_closed(self) -> bool:
        """检查线是否闭合
        
        Returns:
            是否闭合
        """
        try:
            # 使用CADQuery的方法检查线是否闭合
            return bool(self.cq_wire.IsClosed())
        except Exception as e:
            raise ValueError(f"检查线闭合性失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        is_closed = self.is_closed()
        edge_count = len(self.get_edges())
        return f"Wire(edges={edge_count}, closed={is_closed})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
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


class Face(TaggedMixin):
    """面类，包装CADQuery的Face，添加标签功能"""
    
    def __init__(self, cq_face: CQFace):
        """初始化面
        
        Args:
            cq_face: CADQuery的面对象
        """
        try:
            self.cq_face = cq_face
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化面失败: {e}. 请检查输入的面对象是否有效。")
    
    def get_area(self) -> float:
        """获取面积
        
        Returns:
            面积
        """
        try:
            return self.cq_face.Area()
        except Exception as e:
            raise ValueError(f"获取面积失败: {e}")
    
    def get_normal_at(self, u: float = 0.5, v: float = 0.5) -> Vector:
        """获取面在指定参数处的法向量
        
        Args:
            u: U参数
            v: V参数
            
        Returns:
            法向量
        """
        try:
            normal, _ = self.cq_face.normalAt(u, v)
            return normal
        except Exception as e:
            raise ValueError(f"获取法向量失败: {e}")
    
    def get_outer_wire(self) -> Wire:
        """获取外边界线
        
        Returns:
            外边界线
        """
        try:
            outer_wire = self.cq_face.outerWire()
            return Wire(outer_wire)
        except Exception as e:
            raise ValueError(f"获取外边界线失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        area = self.get_area()
        return f"Face(area={area:.3f})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
        """
        spaces = "  " * indent
        result = []
        
        # 基本信息
        area = self.get_area()
        result.append(f"{spaces}Face:")
        result.append(f"{spaces}  area: {area:.3f}")
        
        # 法向量信息
        try:
            normal = self.get_normal_at()
            result.append(f"{spaces}  normal: [{normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f}]")
        except Exception:
            result.append(f"{spaces}  normal: [unable to retrieve]")
        
        # 外边界线信息（不传递坐标系显示参数，因为Face层级会统一显示）
        try:
            outer_wire = self.get_outer_wire()
            result.append(f"{spaces}  outer_wire:")
            result.append(outer_wire._format_string(indent + 2, False))
        except Exception:
            result.append(f"{spaces}  outer_wire: [unable to retrieve]")
        
        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        
        return "\n".join(result)


class Shell(TaggedMixin):
    """壳类，包装CADQuery的Shell，添加标签功能"""
    
    def __init__(self, cq_shell: Union[CQShell, Any]):
        """初始化壳
        
        Args:
            cq_shell: CADQuery的壳对象或其他Shape对象
        """
        try:
            # 如果是CADQuery的Shape，检查是否为Shell或可转换为Shell
            if hasattr(cq_shell, 'ShapeType'):
                if cq_shell.ShapeType() == 'Shell':
                    self.cq_shell = cq_shell
                elif hasattr(cq_shell, 'Shells') and cq_shell.Shells():
                    # 如果是复合体，取第一个Shell
                    self.cq_shell = cq_shell.Shells()[0]
                else:
                    self.cq_shell = cq_shell
            else:
                self.cq_shell = cq_shell
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化壳失败: {e}. 请检查输入的壳对象是否有效。")
    
    def get_faces(self) -> List[Face]:
        """获取组成壳的面
        
        Returns:
            面列表
        """
        try:
            faces = self.cq_shell.Faces()
            return [Face(face) for face in faces]
        except Exception as e:
            raise ValueError(f"获取面列表失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        face_count = len(self.get_faces())
        return f"Shell(faces={face_count})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
        """
        spaces = "  " * indent
        result = []
        
        # 基本信息
        faces = self.get_faces()
        result.append(f"{spaces}Shell:")
        result.append(f"{spaces}  face_count: {len(faces)}")
        
        # 坐标系信息（在Shell层级显示，子级Face不再显示）
        if show_coordinate_system:
            current_cs = get_current_cs()
            if current_cs != WORLD_CS:
                result.append(f"{spaces}  coordinate_system:")
                result.append(current_cs._format_string(indent + 2))
        
        # 面信息（不传递坐标系显示参数，因为Shell层级已经显示了）
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


class Solid(TaggedMixin):
    """实体类，包装CADQuery的Solid，添加标签功能"""
    
    def __init__(self, cq_solid: Union[CQSolid, Any]):
        """初始化实体
        
        Args:
            cq_solid: CADQuery的实体对象
        """
        try:
            # 如果是CADQuery的Shape，检查是否为Solid
            if hasattr(cq_solid, 'ShapeType') and cq_solid.ShapeType() == 'Solid':
                self.cq_solid = cq_solid
            elif hasattr(cq_solid, 'Solids') and cq_solid.Solids():
                # 如果是复合体，取第一个Solid
                self.cq_solid = cq_solid.Solids()[0]
            else:
                self.cq_solid = cq_solid
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化实体失败: {e}. 请检查输入的实体对象是否有效。")
    
    def get_volume(self) -> float:
        """获取体积
        
        Returns:
            体积
        """
        try:
            return self.cq_solid.Volume()
        except Exception as e:
            raise ValueError(f"获取体积失败: {e}")
    
    def get_faces(self) -> List[Face]:
        """获取组成实体的面
        
        Returns:
            面列表
        """
        try:
            faces = self.cq_solid.Faces()
            face_objects = []
            
            for i, face in enumerate(faces):
                face_obj = Face(face)
                
                # 恢复之前保存的标签
                if hasattr(self, '_face_tags') and i in self._face_tags:
                    for tag in self._face_tags[i]:
                        face_obj.add_tag(tag)
                
                face_objects.append(face_obj)
            
            return face_objects
        except Exception as e:
            raise ValueError(f"获取面列表失败: {e}")
    
    def get_edges(self) -> List[Edge]:
        """获取组成实体的边
        
        Returns:
            边列表
        """
        try:
            edges = self.cq_solid.Edges()
            return [Edge(edge) for edge in edges]
        except Exception as e:
            raise ValueError(f"获取边列表失败: {e}")
    
    def auto_tag_faces(self, geometry_type: str = "unknown") -> None:
        """自动为面添加标签
        
        Args:
            geometry_type: 几何体类型 ('box', 'cylinder', 'sphere', 'unknown')
        """
        try:
            # 确保有面标签字典
            if not hasattr(self, '_face_tags'):
                self._face_tags = {}
            
            faces = self.get_faces()
            
            # 清除之前的标签
            self._face_tags.clear()
            
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
        """为立方体面自动添加标签"""
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
        """为圆柱体面自动添加标签"""
        try:
            for i, face in enumerate(faces):
                # 简化实现：根据面的位置添加标签
                center = face.cq_face.Center()
                if abs(center.z) > 0.1:  # 假设是顶面或底面
                    if center.z > 0:
                        tag = "top"
                    else:
                        tag = "bottom"
                else:
                    tag = "side"
                
                self._tag_face(face, tag)
        except Exception as e:
            print(f"警告: 自动标记圆柱体面失败: {e}")
    
    def _tag_face(self, face: Face, tag: str) -> None:
        """为面添加标签并保存到实体
        
        Args:
            face: 面对象
            tag: 标签名称
        """
        if not hasattr(self, '_face_tags'):
            self._face_tags = {}
        
        # 使用面的索引作为键
        face_index = len(self._face_tags)
        self._face_tags[face_index] = {tag}
        
        # 同时也添加到面对象本身
        face.add_tag(tag)
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        volume = self.get_volume()
        face_count = len(self.get_faces())
        return f"Solid(volume={volume:.3f}, faces={face_count})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
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


class Compound(TaggedMixin):
    """复合体类，包装CADQuery的Compound，添加标签功能"""
    
    def __init__(self, cq_compound: CQCompound):
        """初始化复合体
        
        Args:
            cq_compound: CADQuery的复合体对象
        """
        try:
            self.cq_compound = cq_compound
            TaggedMixin.__init__(self)
        except Exception as e:
            raise ValueError(f"初始化复合体失败: {e}. 请检查输入的复合体对象是否有效。")
    
    def get_solids(self) -> List[Solid]:
        """获取组成复合体的实体
        
        Returns:
            实体列表
        """
        try:
            solids = self.cq_compound.Solids()
            return [Solid(solid) for solid in solids]
        except Exception as e:
            raise ValueError(f"获取实体列表失败: {e}")
    
    def __str__(self) -> str:
        """字符串表示"""
        return self._format_string(indent=0)
    
    def __repr__(self) -> str:
        """调试表示"""
        solid_count = len(self.get_solids())
        return f"Compound(solids={solid_count})"
    
    def _format_string(self, indent: int = 0, show_coordinate_system: bool = False) -> str:
        """格式化字符串表示
        
        Args:
            indent: 缩进级别
            show_coordinate_system: 是否显示坐标系信息
        """
        spaces = "  " * indent
        result = []
        
        # 基本信息
        solids = self.get_solids()
        result.append(f"{spaces}Compound:")
        result.append(f"{spaces}  solid_count: {len(solids)}")
        
        # 坐标系信息（在Compound层级显示，子级Solid不再显示）
        if show_coordinate_system:
            current_cs = get_current_cs()
            if current_cs != WORLD_CS:
                result.append(f"{spaces}  coordinate_system:")
                result.append(current_cs._format_string(indent + 2))
        
        # 实体信息（不传递坐标系显示参数，因为Compound层级已经显示了）
        if solids:
            result.append(f"{spaces}  solids:")
            for i, solid in enumerate(solids):
                result.append(f"{spaces}    solid_{i}:")
                result.append(solid._format_string(indent + 3, False))
        
        # 标签和元数据
        tags_metadata = self._format_tags_and_metadata(indent + 1)
        if tags_metadata:
            result.append(tags_metadata)
        
        return "\n".join(result)

AnyShape = Union[Vertex, Edge, Wire, Face, Shell, Solid, Compound]