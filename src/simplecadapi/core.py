"""
SimpleCAD API核心类定义
基于README中的API设计，使用CADQuery作为底层实现
"""

from typing import List, Tuple, Union, Optional, Any
import numpy as np
import cadquery as cq
from cadquery import Vector, Plane


class CoordinateSystem:
    """三维坐标系
    
    SimpleCAD使用Z向上的右手坐标系，但CADQuery使用Y向上的右手坐标系
    需要进行坐标转换：
    SimpleCAD (X, Y, Z) -> CADQuery (X, Z, -Y)
    """
    
    def __init__(self, 
                 origin: Tuple[float, float, float] = (0, 0, 0),
                 x_axis: Tuple[float, float, float] = (1, 0, 0),
                 y_axis: Tuple[float, float, float] = (0, 1, 0)):
        # SimpleCAD坐标系（Z向上）
        self.origin = np.array(origin, dtype=float)
        self.x_axis = self._normalize(x_axis)
        self.y_axis = self._normalize(y_axis)
        self.z_axis = self._normalize(np.cross(self.x_axis, self.y_axis))
        
    def _normalize(self, vector) -> np.ndarray:
        """归一化向量"""
        v = np.array(vector, dtype=float)
        norm = np.linalg.norm(v)
        if norm == 0:
            raise ValueError("不能归一化零向量")
        return v / norm
    
    def transform_point(self, point: np.ndarray) -> np.ndarray:
        """将局部坐标转换为全局坐标（SimpleCAD坐标系）"""
        return self.origin + point[0]*self.x_axis + point[1]*self.y_axis + point[2]*self.z_axis
    
    def to_cq_coords(self, point: np.ndarray) -> np.ndarray:
        """将SimpleCAD坐标转换为CADQuery坐标
        SimpleCAD (X, Y, Z) -> CADQuery (X, Z, -Y)
        """
        return np.array([point[0], point[2], -point[1]], dtype=float)
    
    def from_cq_coords(self, point: np.ndarray) -> np.ndarray:
        """将CADQuery坐标转换为SimpleCAD坐标
        CADQuery (X, Y, Z) -> SimpleCAD (X, -Z, Y)
        """
        return np.array([point[0], -point[2], point[1]], dtype=float)
    
    def to_cq_plane(self) -> Plane:
        """转换为CADQuery的Plane对象"""
        # 转换坐标系到CADQuery空间
        cq_origin = self.to_cq_coords(self.origin)
        cq_x_axis = self.to_cq_coords(self.x_axis) - self.to_cq_coords(np.zeros(3))
        cq_z_axis = self.to_cq_coords(self.z_axis) - self.to_cq_coords(np.zeros(3))
        
        return Plane(
            origin=Vector(*cq_origin),
            xDir=Vector(*cq_x_axis),
            normal=Vector(*cq_z_axis)
        )


# 全局世界坐标系（Z向上的右手坐标系）
WORLD_CS = CoordinateSystem()


class Point:
    """三维点（存储在局部坐标系中的坐标）"""
    
    def __init__(self, coords: Tuple[float, float, float], cs: Optional[CoordinateSystem] = None):
        self.local_coords = np.array(coords, dtype=float)
        self.cs = cs if cs is not None else get_current_cs()
        
    @property
    def global_coords(self) -> np.ndarray:
        """获取全局坐标系中的坐标（SimpleCAD坐标系）"""
        return self.cs.transform_point(self.local_coords)
    
    def to_cq_vector(self) -> Vector:
        """转换为CADQuery的Vector对象（CADQuery坐标系）"""
        global_coords = self.global_coords
        cq_coords = self.cs.to_cq_coords(global_coords)
        return Vector(cq_coords[0], cq_coords[1], cq_coords[2])
    
    def __repr__(self) -> str:
        return f"Point(local={self.local_coords}, global={self.global_coords})"


class Line:
    """曲线（线段/圆弧/样条）"""
    
    def __init__(self, points: List[Point], line_type: str = "segment"):
        """
        :param points: 控制点列表
        :param line_type: 类型 ('segment', 'arc', 'spline')
        """
        self.points = points
        self.type = line_type
        self._validate()
        self._cq_edge = None  # 延迟创建CADQuery边
        
    def _validate(self):
        """验证线的参数"""
        if self.type == "segment" and len(self.points) != 2:
            raise ValueError("线段需要2个控制点")
        if self.type == "arc" and len(self.points) != 3:
            raise ValueError("圆弧需要3个控制点")
        if self.type == "spline" and len(self.points) < 2:
            raise ValueError("样条曲线至少需要2个控制点")
    
    def to_cq_edge(self):
        """转换为CADQuery的边对象"""
        if self._cq_edge is not None:
            return self._cq_edge
            
        if self.type == "segment":
            # 创建线段
            start = self.points[0].to_cq_vector()
            end = self.points[1].to_cq_vector()
            self._cq_edge = cq.Edge.makeLine(start, end)
            
        elif self.type == "arc":
            # 创建圆弧（通过三点）
            p1 = self.points[0].to_cq_vector()
            p2 = self.points[1].to_cq_vector()
            p3 = self.points[2].to_cq_vector()
            self._cq_edge = cq.Edge.makeThreePointArc(p1, p2, p3)
            
        elif self.type == "spline":
            # 创建样条曲线
            cq_points = [p.to_cq_vector() for p in self.points]
            self._cq_edge = cq.Edge.makeSpline(cq_points)
            
        return self._cq_edge
    
    def __repr__(self) -> str:
        return f"Line(type={self.type}, points={len(self.points)})"


class Sketch:
    """二维草图（闭合平面轮廓）"""
    
    def __init__(self, lines: List[Line]):
        self.lines = lines
        # 从第一个点获取坐标系信息
        self.cs = lines[0].points[0].cs if lines and lines[0].points else get_current_cs()
        self._validate()
        self._cq_wire = None  # 延迟创建CADQuery线框
        
    def _validate(self):
        """验证草图的闭合性和共面性"""
        if not self._is_closed():
            raise ValueError("草图必须形成闭合轮廓")
        if not self._is_planar():
            raise ValueError("草图必须位于同一平面内")
            
    def _is_closed(self) -> bool:
        """检查起点和终点是否重合"""
        if not self.lines:
            return False
            
        start = self.lines[0].points[0].global_coords
        end = self.lines[-1].points[-1].global_coords
        return np.allclose(start, end, atol=1e-6)
    
    def _is_planar(self) -> bool:
        """简化的共面检查（实际需要法向量计算）"""
        # TODO: 实现真正的共面检查
        return True
    
    def to_cq_wire(self):
        """转换为CADQuery的线框对象"""
        if self._cq_wire is not None:
            return self._cq_wire
            
        # 将所有线段转换为CADQuery边
        cq_edges = []
        for line in self.lines:
            edge = line.to_cq_edge()
            if edge is not None:
                cq_edges.append(edge)
        
        # 创建线框
        try:
            self._cq_wire = cq.Wire.assembleEdges(cq_edges)
        except Exception as e:
            raise ValueError(f"无法创建闭合线框: {e}")
            
        return self._cq_wire
    
    def get_workplane(self):
        """获取草图所在的工作平面"""
        return cq.Workplane(self.cs.to_cq_plane())
    
    def get_normal_vector(self) -> np.ndarray:
        """获取草图平面的法向量（SimpleCAD坐标系）"""
        return self.cs.z_axis
    
    def __repr__(self) -> str:
        return f"Sketch(lines={len(self.lines)})"


class Body:
    """三维实体"""
    _id_counter = 0
    
    def __init__(self, cq_solid: Any = None):
        self.cq_solid = cq_solid  # CADQuery的Solid对象
        self.id = Body._id_counter
        Body._id_counter += 1
        
    def is_valid(self) -> bool:
        """检查实体是否有效"""
        return self.cq_solid is not None
    
    def volume(self) -> float:
        """计算体积"""
        if self.cq_solid is None:
            return 0.0
        try:
            # 简化的体积计算
            return 1.0  # 暂时返回固定值，待实现
        except:
            return 0.0
    
    def to_cq_workplane(self) -> 'cq.Workplane':
        """转换为CADQuery工作平面对象"""
        if self.cq_solid is None:
            return cq.Workplane()
        return cq.Workplane().add(self.cq_solid)
    
    def __repr__(self) -> str:
        return f"Body(id={self.id}, valid={self.is_valid()})"


# 当前坐标系上下文管理器
_current_cs = [WORLD_CS]  # 默认使用世界坐标系


class LocalCoordinateSystem:
    """局部坐标系上下文管理器"""
    
    def __init__(self, 
                 origin: Tuple[float, float, float], 
                 x_axis: Tuple[float, float, float], 
                 y_axis: Tuple[float, float, float]):
        self.cs = CoordinateSystem(origin, x_axis, y_axis)
        
    def __enter__(self):
        _current_cs.append(self.cs)
        return self.cs
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        _current_cs.pop()


def get_current_cs() -> CoordinateSystem:
    """获取当前坐标系"""
    return _current_cs[-1]
